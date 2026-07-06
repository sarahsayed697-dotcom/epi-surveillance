"""
Alert Agent
Generates, formats, and dispatches alerts via email, Slack, and webhooks.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Optional
import httpx
import anthropic
from config.settings import settings

logger = logging.getLogger(__name__)
client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)


class AlertAgent:
    """
    Generates structured alerts for high and critical risk events.
    Dispatches via configured channels: Slack, email webhook, etc.
    """

    RISK_EMOJI = {
        "very_low": "🟢",
        "low": "🟡",
        "moderate": "🟠",
        "high": "🔴",
        "critical": "🚨",
    }

    async def generate_alert(self, event_data: dict) -> dict:
        """Use Claude to write a professional epidemiological alert bulletin."""
        prompt = f"""You are a senior epidemiologist writing an official outbreak alert.
Write a concise, professional alert bulletin for the following event.
The alert will be sent to public health professionals.

Event data:
{json.dumps(event_data, indent=2)}

Respond ONLY with JSON:
{{
  "title": string (max 80 chars, action-oriented),
  "executive_summary": string (2-3 sentences, key facts only),
  "situation_assessment": string (clinical/epidemiological detail),
  "risk_to_public": string,
  "recommended_actions": [string],
  "monitoring_indicators": [string],
  "alert_level": "INFORMATION"|"WATCH"|"WARNING"|"EMERGENCY"
}}"""

        try:
            response = client.messages.create(
                model=settings.PRIMARY_LLM,
                max_tokens=800,
                temperature=0.2,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            return json.loads(raw.strip())
        except Exception as e:
            logger.error(f"Alert generation failed: {e}")
            return {
                "title": f"Alert: {event_data.get('disease_name', 'Unknown disease')}",
                "executive_summary": "Alert generation failed — manual review required.",
                "alert_level": "WATCH",
            }

    async def send_slack_alert(self, alert: dict, event_data: dict) -> bool:
        """Send formatted alert to Slack webhook."""
        if not settings.SLACK_WEBHOOK_URL:
            logger.warning("Slack webhook not configured")
            return False

        risk_level = event_data.get("risk_level", "unknown")
        emoji = self.RISK_EMOJI.get(risk_level, "⚠️")

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{emoji} {alert.get('title', 'Outbreak Alert')}",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": alert.get("executive_summary", ""),
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Disease:*\n{event_data.get('disease_name', 'Unknown')}"},
                    {"type": "mrkdwn", "text": f"*Location:*\n{event_data.get('country', 'Unknown')}"},
                    {"type": "mrkdwn", "text": f"*Risk Level:*\n{risk_level.upper()}"},
                    {"type": "mrkdwn", "text": f"*Confidence:*\n{event_data.get('confidence', 0):.0%}"},
                ],
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"EpiSurveillance | {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
                    }
                ],
            },
        ]

        try:
            async with httpx.AsyncClient() as http_client:
                resp = await http_client.post(
                    settings.SLACK_WEBHOOK_URL,
                    json={"blocks": blocks},
                    timeout=10.0,
                )
                resp.raise_for_status()
                logger.info(f"Slack alert sent: {alert.get('title')}")
                return True
        except Exception as e:
            logger.error(f"Slack alert failed: {e}")
            return False

    async def dispatch_alert(self, event_data: dict) -> dict:
        """
        Full alert dispatch pipeline:
        1. Generate structured alert text via LLM
        2. Send to all configured channels
        3. Return dispatch result
        """
        alert = await self.generate_alert(event_data)

        results = {
            "alert": alert,
            "channels_attempted": [],
            "channels_succeeded": [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Slack
        if settings.SLACK_WEBHOOK_URL:
            results["channels_attempted"].append("slack")
            success = await self.send_slack_alert(alert, event_data)
            if success:
                results["channels_succeeded"].append("slack")

        # Log to stdout always (useful for Kubernetes log aggregation)
        logger.warning(
            f"[{alert.get('alert_level', 'WATCH')}] {alert.get('title')} | "
            f"Disease: {event_data.get('disease_name')} | "
            f"Location: {event_data.get('country')} | "
            f"Risk: {event_data.get('risk_level')}"
        )

        return results
