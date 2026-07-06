"""
Epidemiologist Agent
Estimates R0, Rt, CFR, doubling time, and other parameters from cluster data.
"""
import json
import logging
from typing import Optional
import anthropic
from config.settings import settings

logger = logging.getLogger(__name__)
client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)


class EpidemiologistAgent:
    """
    Specialist agent for epidemiological parameter estimation.
    Called when a cluster has sufficient data for Rt/CFR/R0 estimation.
    """

    async def estimate_parameters(self, cluster_data: dict) -> dict:
        """Estimate R0, Rt, CFR, doubling time from aggregated cluster data."""
        prompt = f"""You are a mathematical epidemiologist with expertise in outbreak analysis.
Given the following outbreak data, estimate epidemiological parameters.
Use established methods: exponential growth for R0, instantaneous Rt estimation,
naive CFR where data permits. Be conservative and acknowledge uncertainty.

Respond ONLY with a valid JSON object — no preamble, no markdown.

Outbreak data:
{json.dumps(cluster_data, indent=2)}

Return this exact schema:
{{
  "r0_estimate": float or null,
  "r0_confidence_interval": [float, float] or null,
  "r0_method": string,
  "rt_estimate": float or null,
  "rt_trend": "increasing" | "decreasing" | "stable" | "unknown",
  "cfr_estimate": float or null,
  "cfr_note": string,
  "attack_rate": float or null,
  "doubling_time_days": float or null,
  "generation_time_estimate_days": float or null,
  "serial_interval_estimate_days": float or null,
  "spillover_probability": float or null,
  "reasoning": string,
  "data_quality": "low" | "moderate" | "high",
  "caveats": [string]
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
            logger.error(f"Parameter estimation failed: {e}")
            return {
                "reasoning": f"Estimation failed: {e}",
                "data_quality": "low",
                "caveats": ["LLM estimation error — manual review required"],
            }

    async def assess_spillover_risk(self, event_data: dict) -> dict:
        """Assess animal-to-human spillover probability."""
        prompt = f"""You are a One Health expert specialising in zoonotic disease spillover.
Assess the animal-to-human spillover risk based on the following event data.

Event: {json.dumps(event_data, indent=2)}

Consider: pathogen characteristics, reservoir competence, exposure pathways,
human behaviour patterns, and environmental conditions.

Respond ONLY with JSON:
{{
  "spillover_probability": float 0-1,
  "risk_factors": [string],
  "protective_factors": [string],
  "recommended_actions": [string],
  "surveillance_priority": "routine" | "enhanced" | "urgent",
  "reasoning": string
}}"""

        try:
            response = client.messages.create(
                model=settings.PRIMARY_LLM,
                max_tokens=800,
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
            logger.error(f"Spillover assessment failed: {e}")
            return {"spillover_probability": None, "reasoning": str(e)}
