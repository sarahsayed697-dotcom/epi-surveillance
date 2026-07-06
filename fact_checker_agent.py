"""
Fact-Checker Agent
Cross-source validation, misinformation detection, and credibility scoring.
"""
import json
import logging
import anthropic
from config.settings import settings

logger = logging.getLogger(__name__)
client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)


class FactCheckerAgent:
    """
    Validates epidemiological claims by comparing multiple source signals.
    Detects: verified reports, rumors, duplicates, satire, misinformation,
    conspiracy theories, and bot-generated content.
    """

    async def validate_event(self, event_data: dict, related_signals: list[str]) -> dict:
        """Cross-validate an event against multiple signals."""
        sources_text = "\n---\n".join(related_signals[:5])

        prompt = f"""You are an expert fact-checker specialising in infectious disease reporting.
Assess the credibility of the following disease outbreak claim by comparing it
against multiple source signals. Look for corroboration, contradictions, and signs
of misinformation.

MAIN CLAIM:
Disease: {event_data.get('disease_name', 'Unknown')}
Location: {event_data.get('country')}, {event_data.get('province')}
Cases: {event_data.get('human_cases_suspected')} suspected, {event_data.get('human_cases_confirmed')} confirmed
Deaths: {event_data.get('deaths')}
Source type: {event_data.get('source_type')}

RELATED SIGNALS:
{sources_text if sources_text else 'No related signals found.'}

Respond ONLY with JSON:
{{
  "final_credibility_label": "verified"|"rumor"|"duplicate"|"satire"|"misinformation"|"conspiracy"|"bot_generated"|"unknown",
  "final_credibility_score": float 0-1,
  "independent_source_count": int,
  "contradictions_found": [string],
  "supporting_sources": [string],
  "red_flags": [string],
  "verdict_reasoning": string,
  "recommended_action": "monitor"|"alert"|"dismiss"|"escalate"
}}"""

        try:
            response = client.messages.create(
                model=settings.PRIMARY_LLM,
                max_tokens=1024,
                temperature=0,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            return json.loads(raw.strip())
        except Exception as e:
            logger.error(f"Fact check failed: {e}")
            return {
                "final_credibility_label": "unknown",
                "verdict_reasoning": f"Fact check failed: {e}",
                "recommended_action": "monitor",
            }

    async def detect_misinformation_patterns(self, text: str) -> dict:
        """Detect common misinformation patterns in disease reporting."""
        prompt = f"""Analyze the following text for misinformation patterns related to disease outbreaks.

TEXT:
{text[:3000]}

Look for:
- Exaggerated statistics (death counts, spread claims)
- False attribution to authoritative sources
- Conspiracy theory language
- Emotional manipulation tactics
- Contradictions with known scientific consensus
- Bot-like repetitive patterns

Respond ONLY with JSON:
{{
  "misinformation_probability": float 0-1,
  "patterns_detected": [string],
  "specific_claims_to_verify": [string],
  "overall_assessment": string
}}"""

        try:
            response = client.messages.create(
                model=settings.FAST_LLM,
                max_tokens=512,
                temperature=0,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            return json.loads(raw.strip())
        except Exception as e:
            logger.error(f"Misinformation detection failed: {e}")
            return {"misinformation_probability": 0.5, "overall_assessment": str(e)}
