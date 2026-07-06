"""
EpiSurveillance — Supervisor Agent
Orchestrates all sub-agents, manages memory, handles failures,
aggregates confidence, and triggers alerts.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional
import anthropic
from pydantic import BaseModel
from config.settings import settings
from core.collectors.collectors import CollectorRegistry, RawSignalInput
from core.processors.text_processor import TextProcessor
from core.extractors.llm_extractor import extract_epi_data, ExtractedEpiData

logger = logging.getLogger(__name__)
client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)


class AgentMemory(BaseModel):
    """Shared memory state across agent calls in one surveillance cycle."""
    cycle_id: str
    started_at: datetime
    total_signals: int = 0
    processed_signals: int = 0
    epi_relevant: int = 0
    high_risk_events: int = 0
    errors: list[str] = []
    summary: str = ""


class SupervisorAgent:
    """
    Top-level orchestrator. Runs one full surveillance cycle:

    1. Collect → 2. Process → 3. Extract → 4. Cluster →
    5. Risk-score → 6. Alert → 7. Dashboard update → 8. Summarize
    """

    def __init__(self):
        self.collector_registry = CollectorRegistry()
        self.text_processor = TextProcessor()
        self.memory = None

    async def run_cycle(self) -> AgentMemory:
        """Execute one full surveillance cycle."""
        cycle_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        self.memory = AgentMemory(
            cycle_id=cycle_id,
            started_at=datetime.now(timezone.utc),
        )
        logger.info(f"Surveillance cycle {cycle_id} started")

        try:
            # ── Phase 1: Collection ──────────────────────────────────────────
            signals = await self._run_collection()
            self.memory.total_signals = len(signals)

            # ── Phase 2: Text processing (parallel, chunked) ─────────────────
            processed = await self._run_processing(signals)
            self.memory.processed_signals = len(processed)

            # ── Phase 3: LLM extraction (batched) ───────────────────────────
            extractions = await self._run_extraction(processed)
            relevant = [e for e in extractions if e.is_epi_relevant]
            self.memory.epi_relevant = len(relevant)

            # ── Phase 4: Risk filtering & alerts ────────────────────────────
            high_risk = await self._run_risk_triage(relevant)
            self.memory.high_risk_events = len(high_risk)

            # ── Phase 5: Cycle summary via LLM ──────────────────────────────
            self.memory.summary = await self._generate_cycle_summary(relevant, high_risk)

            logger.info(
                f"Cycle {cycle_id} complete: "
                f"{self.memory.total_signals} signals → "
                f"{self.memory.epi_relevant} relevant → "
                f"{self.memory.high_risk_events} high-risk"
            )

        except Exception as e:
            logger.error(f"Cycle {cycle_id} failed: {e}", exc_info=True)
            self.memory.errors.append(str(e))

        return self.memory

    async def _run_collection(self) -> list[RawSignalInput]:
        """Phase 1: Run all collectors with error isolation."""
        try:
            return await self.collector_registry.collect_all()
        except Exception as e:
            logger.error(f"Collection phase failed: {e}")
            self.memory.errors.append(f"collection: {e}")
            return []

    async def _run_processing(self, signals: list[RawSignalInput]) -> list[dict]:
        """Phase 2: Text processing in parallel chunks of 50."""
        processed = []
        chunk_size = 50

        for i in range(0, len(signals), chunk_size):
            chunk = signals[i:i + chunk_size]
            tasks = [
                self.text_processor.process(s.text_original, s.source_type)
                for s in chunk
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for signal, result in zip(chunk, results):
                if isinstance(result, Exception):
                    logger.warning(f"Processing error: {result}")
                    continue
                if result.get("skip"):
                    continue

                processed.append({
                    **result,
                    "source_type": signal.source_type,
                    "source_url": signal.source_url,
                    "source_id": signal.source_id,
                    "published_at": signal.published_at,
                    "author": signal.author,
                    "engagement_score": signal.engagement_score,
                    "collected_at": datetime.now(timezone.utc).isoformat(),
                })

        logger.info(f"Processing: {len(signals)} → {len(processed)} after filtering")
        return processed

    async def _run_extraction(self, processed: list[dict]) -> list[ExtractedEpiData]:
        """Phase 3: LLM extraction with concurrency limit."""
        semaphore = asyncio.Semaphore(10)  # Max 10 concurrent LLM calls

        async def _extract_one(item: dict) -> Optional[ExtractedEpiData]:
            async with semaphore:
                try:
                    return await extract_epi_data(
                        text=item.get("text_translated") or item.get("text_cleaned", ""),
                        source_type=item["source_type"],
                        collection_date=item["collected_at"],
                    )
                except Exception as e:
                    logger.warning(f"Extraction failed: {e}")
                    return None

        tasks = [_extract_one(item) for item in processed]
        results = await asyncio.gather(*tasks)
        return [r for r in results if r is not None]

    async def _run_risk_triage(self, events: list[ExtractedEpiData]) -> list[ExtractedEpiData]:
        """Phase 4: Filter high/critical risk events and trigger alerts."""
        high_risk = [
            e for e in events
            if e.risk_level in ("high", "critical")
            and e.credibility_label not in ("satire", "conspiracy", "misinformation")
        ]

        for event in high_risk:
            await self._trigger_alert(event)

        return high_risk

    async def _trigger_alert(self, event: ExtractedEpiData) -> None:
        """Generate and dispatch an alert for a high-risk event."""
        logger.warning(
            f"ALERT [{event.risk_level.upper()}] {event.disease_name} "
            f"in {event.country} (confidence: {event.confidence:.0%})"
        )
        # In production: send email, Slack webhook, push to dashboard
        # Implementation in agents/alert/alert_agent.py

    async def _generate_cycle_summary(
        self,
        all_relevant: list[ExtractedEpiData],
        high_risk: list[ExtractedEpiData],
    ) -> str:
        """Generate an executive summary of the surveillance cycle using Claude."""
        if not all_relevant:
            return "No epidemiologically relevant signals detected in this cycle."

        # Build context
        diseases = list({e.disease_name for e in all_relevant if e.disease_name})
        countries = list({e.country for e in all_relevant if e.country})
        high_risk_summary = [
            f"- {e.disease_name} in {e.country} (risk: {e.risk_level}, "
            f"cases: {e.human_cases_confirmed or e.human_cases_suspected or 'unknown'})"
            for e in high_risk[:10]
        ]

        prompt = f"""You are an epidemiologist writing a brief surveillance bulletin.
Summarize the following surveillance cycle findings in 3–4 concise paragraphs.
Focus on: key diseases detected, geographic hotspots, risk level, and recommended actions.

Diseases detected: {', '.join(diseases[:15])}
Countries affected: {', '.join(countries[:15])}
Total relevant signals: {len(all_relevant)}
High/critical risk events:
{chr(10).join(high_risk_summary) if high_risk_summary else 'None'}

Write a professional epidemiological bulletin summary."""

        try:
            response = client.messages.create(
                model=settings.PRIMARY_LLM,
                max_tokens=500,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text.strip()
        except Exception as e:
            logger.error(f"Summary generation failed: {e}")
            return f"Summary unavailable. {len(all_relevant)} relevant signals, {len(high_risk)} high-risk events."


class EpidemiologistAgent:
    """
    Specialist agent for epidemiological parameter estimation.
    Called when a cluster has sufficient data for Rt/CFR/R0 estimation.
    """

    async def estimate_parameters(self, cluster_data: dict) -> dict:
        """Estimate R0, Rt, CFR, doubling time from aggregated cluster data."""
        prompt = f"""You are a mathematical epidemiologist.
Given the following outbreak data, estimate epidemiological parameters.
Respond ONLY with a JSON object.

Outbreak data:
{cluster_data}

Return:
{{
  "r0_estimate": float or null,
  "r0_confidence_interval": [float, float] or null,
  "rt_estimate": float or null,
  "rt_trend": "increasing" | "decreasing" | "stable" | "unknown",
  "cfr_estimate": float or null,
  "attack_rate": float or null,
  "doubling_time_days": float or null,
  "generation_time_estimate_days": float or null,
  "reasoning": string,
  "data_quality": "low" | "moderate" | "high"
}}"""

        try:
            response = client.messages.create(
                model=settings.PRIMARY_LLM,
                max_tokens=1024,
                temperature=0,
                messages=[{"role": "user", "content": prompt}],
            )
            import json
            return json.loads(response.content[0].text.strip())
        except Exception as e:
            logger.error(f"Parameter estimation failed: {e}")
            return {"reasoning": f"Estimation failed: {e}", "data_quality": "low"}


class FactCheckerAgent:
    """
    Specialist agent for cross-source validation and misinformation detection.
    """

    async def validate_event(
        self,
        event: ExtractedEpiData,
        related_signals: list[str],
    ) -> dict:
        """Cross-validate an event against multiple signals."""
        sources_text = "\n---\n".join(related_signals[:5])
        prompt = f"""You are a fact-checking epidemiologist.
Assess the credibility of the following disease outbreak claim by comparing it
against multiple source signals.

MAIN CLAIM:
Disease: {event.disease_name}
Location: {event.country}, {event.province}
Cases: {event.human_cases_suspected} suspected, {event.human_cases_confirmed} confirmed
Deaths: {event.deaths}

RELATED SIGNALS:
{sources_text}

Respond with JSON:
{{
  "final_credibility_label": string,
  "final_credibility_score": float,
  "independent_source_count": int,
  "contradictions_found": [string],
  "supporting_sources": [string],
  "verdict_reasoning": string
}}"""

        try:
            response = client.messages.create(
                model=settings.PRIMARY_LLM,
                max_tokens=1024,
                temperature=0,
                messages=[{"role": "user", "content": prompt}],
            )
            import json
            return json.loads(response.content[0].text.strip())
        except Exception as e:
            logger.error(f"Fact check failed: {e}")
            return {"verdict_reasoning": f"Fact check failed: {e}"}
