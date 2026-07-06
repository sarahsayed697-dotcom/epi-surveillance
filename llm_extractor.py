"""
EpiSurveillance — LLM Extraction Engine
Uses Claude to extract structured epidemiological data from raw text.
Implements: disease NER, host extraction, risk scoring, credibility, XAI.
"""
import json
import logging
from typing import Optional
import anthropic
from pydantic import BaseModel, Field
from config.settings import settings

logger = logging.getLogger(__name__)

client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)


# ── Output schema ─────────────────────────────────────────────────────────────

class ExtractedEpiData(BaseModel):
    # Disease
    disease_name: Optional[str] = None
    disease_synonyms: list[str] = []
    pathogen_type: Optional[str] = None
    is_novel_pathogen: bool = False

    # Cases
    human_cases_suspected: Optional[int] = None
    human_cases_confirmed: Optional[int] = None
    deaths: Optional[int] = None
    hospitalizations: Optional[int] = None
    symptoms: list[str] = []
    transmission_route: Optional[str] = None

    # Hosts & vectors
    animal_species: list[str] = []
    suspected_reservoir: list[str] = []
    suspected_vector: list[str] = []

    # Location
    country: Optional[str] = None
    province: Optional[str] = None
    city: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    geo_confidence: float = Field(0.0, ge=0, le=1)

    # Temporal
    event_date_raw: Optional[str] = None

    # Credibility
    credibility_label: str = "unknown"
    credibility_score: float = Field(0.5, ge=0, le=1)
    source_reliability: float = Field(0.5, ge=0, le=1)

    # Risk
    risk_level: str = "very_low"
    risk_score: float = Field(0.0, ge=0, le=1)
    risk_factors: dict = {}

    # Epi estimates
    r0_estimate: Optional[float] = None
    rt_estimate: Optional[float] = None
    cfr_estimate: Optional[float] = None
    attack_rate: Optional[float] = None
    doubling_time_days: Optional[float] = None
    spillover_probability: Optional[float] = None

    # XAI
    llm_reasoning: str = ""
    supporting_evidence: list[str] = []
    contradictory_evidence: list[str] = []
    confidence: float = Field(0.5, ge=0, le=1)
    is_epi_relevant: bool = False


EXTRACTION_SYSTEM_PROMPT = """You are a senior epidemiologist and infectious disease expert with 20+ years
of experience in outbreak surveillance, zoonotic disease detection, and One Health frameworks.

Your task is to analyze text from social media, news articles, and public health reports to extract
structured epidemiological information about potential zoonotic disease events.

You must respond ONLY with a valid JSON object matching the schema provided. No preamble, no markdown.

Key responsibilities:
1. Extract disease names, synonyms, and pathogen types
2. Identify affected animal species, reservoirs, and vectors
3. Extract case counts, deaths, symptoms, and transmission routes
4. Geolocate events with confidence scores
5. Assess credibility (verified, rumor, misinformation, satire, bot-generated)
6. Score risk level (very_low/low/moderate/high/critical) using:
   - Number of independent reports
   - Official confirmation status
   - Severity and mortality
   - Geographic spread
   - Novel pathogen probability
   - Animal-human interface risk
7. Estimate epidemiological parameters when data permits (R0, Rt, CFR)
8. Provide explainable reasoning for all scores
9. Flag texts irrelevant to disease surveillance (is_epi_relevant: false)

Risk scoring rubric:
- critical (0.8-1.0): Novel pathogen, human-to-human transmission, multi-country, official confirmed
- high (0.6-0.8): Known dangerous pathogen, human cases, verified multiple sources
- moderate (0.4-0.6): Animal cases only, or unconfirmed human exposure, credible source
- low (0.2-0.4): Vague reports, single low-credibility source, no human cases
- very_low (0.0-0.2): Unlikely epi relevance, rumor/satire, no disease specifics

Credibility labels:
- verified: Official source or confirmed by ≥3 independent credible sources
- rumor: Unverified, single source, lacks specifics
- duplicate: Same event already reported elsewhere
- satire: Clearly satirical content
- misinformation: Contradicts scientific consensus
- conspiracy: Unfounded conspiracy claims
- bot_generated: Likely AI/bot-generated content
- unknown: Cannot determine"""


EXTRACTION_USER_TEMPLATE = """Analyze this text for epidemiological relevance and extract structured data.

TEXT TO ANALYZE:
---
{text}
---

SOURCE: {source_type}
COLLECTION DATE: {collection_date}
KNOWN DISEASES TO WATCH: {disease_list}

Respond with a JSON object matching this exact schema:
{{
  "disease_name": string or null,
  "disease_synonyms": [string],
  "pathogen_type": string or null,
  "is_novel_pathogen": boolean,
  "human_cases_suspected": integer or null,
  "human_cases_confirmed": integer or null,
  "deaths": integer or null,
  "hospitalizations": integer or null,
  "symptoms": [string],
  "transmission_route": string or null,
  "animal_species": [string],
  "suspected_reservoir": [string],
  "suspected_vector": [string],
  "country": string or null,
  "province": string or null,
  "city": string or null,
  "latitude": float or null,
  "longitude": float or null,
  "geo_confidence": float 0-1,
  "event_date_raw": string or null,
  "credibility_label": "verified"|"rumor"|"duplicate"|"satire"|"misinformation"|"conspiracy"|"bot_generated"|"unknown",
  "credibility_score": float 0-1,
  "source_reliability": float 0-1,
  "risk_level": "very_low"|"low"|"moderate"|"high"|"critical",
  "risk_score": float 0-1,
  "risk_factors": {{
    "multi_source_confirmation": float,
    "official_confirmation": float,
    "human_involvement": float,
    "animal_involvement": float,
    "novel_pathogen": float,
    "severity": float,
    "geographic_spread": float
  }},
  "r0_estimate": float or null,
  "rt_estimate": float or null,
  "cfr_estimate": float or null,
  "attack_rate": float or null,
  "doubling_time_days": float or null,
  "spillover_probability": float or null,
  "llm_reasoning": string (detailed step-by-step reasoning),
  "supporting_evidence": [string],
  "contradictory_evidence": [string],
  "confidence": float 0-1,
  "is_epi_relevant": boolean
}}"""


async def extract_epi_data(
    text: str,
    source_type: str,
    collection_date: str,
    use_fast_model: bool = False,
) -> ExtractedEpiData:
    """
    Main extraction function. Calls Claude to extract structured epi data from raw text.

    Args:
        text: Raw text content (translated to English if needed)
        source_type: Where the text came from (twitter, news, who, etc.)
        collection_date: ISO datetime string of collection
        use_fast_model: Use faster/cheaper model for low-priority signals

    Returns:
        ExtractedEpiData Pydantic model
    """
    model = settings.FAST_LLM if use_fast_model else settings.PRIMARY_LLM

    user_message = EXTRACTION_USER_TEMPLATE.format(
        text=text[:8000],  # Truncate to avoid token limits
        source_type=source_type,
        collection_date=collection_date,
        disease_list=", ".join(settings.ZOONOTIC_DISEASES[:20]),
    )

    try:
        response = client.messages.create(
            model=model,
            max_tokens=settings.LLM_MAX_TOKENS,
            temperature=settings.LLM_TEMPERATURE,
            system=EXTRACTION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

        raw_json = response.content[0].text.strip()

        # Strip markdown fences if present (defensive)
        if raw_json.startswith("```"):
            raw_json = raw_json.split("```")[1]
            if raw_json.startswith("json"):
                raw_json = raw_json[4:]
            raw_json = raw_json.strip()

        data = json.loads(raw_json)
        result = ExtractedEpiData(**data)

        logger.info(
            "Extraction complete",
            extra={
                "disease": result.disease_name,
                "risk": result.risk_level,
                "relevant": result.is_epi_relevant,
                "model": model,
            },
        )
        return result

    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error in LLM response: {e}")
        return ExtractedEpiData(is_epi_relevant=False, llm_reasoning=f"Parse error: {e}")

    except anthropic.APIError as e:
        logger.error(f"Anthropic API error: {e}")
        raise


# ── Batch extraction ──────────────────────────────────────────────────────────

async def extract_batch(items: list[dict]) -> list[ExtractedEpiData]:
    """
    Process a batch of signals. Uses fast model for items with low keyword density.
    """
    import asyncio
    from core.processors.text_processor import keyword_density_score

    tasks = []
    for item in items:
        density = keyword_density_score(item["text"])
        use_fast = density < 0.3
        tasks.append(
            extract_epi_data(
                text=item["text"],
                source_type=item["source_type"],
                collection_date=item["collected_at"],
                use_fast_model=use_fast,
            )
        )

    results = await asyncio.gather(*tasks, return_exceptions=True)
    valid = [r for r in results if isinstance(r, ExtractedEpiData)]
    logger.info(f"Batch extraction: {len(valid)}/{len(items)} succeeded")
    return valid
