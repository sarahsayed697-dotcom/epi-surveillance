"""
EpiSurveillance — Scheduled Cycle Runner
Runs the surveillance cycle at configured intervals.
In production, replace with Airflow DAG or Kubernetes CronJob.
"""
import asyncio
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import settings
from agents.supervisor.supervisor import SupervisorAgent

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("surveillance_runner")


async def run_forever():
    """Run surveillance cycles at configured intervals."""
    logger.info(
        f"Surveillance runner started. "
        f"Cycle interval: {settings.COLLECTION_INTERVAL_SECONDS}s"
    )
    agent = SupervisorAgent()

    while True:
        try:
            logger.info("Starting surveillance cycle...")
            memory = await agent.run_cycle()
            logger.info(
                f"Cycle complete | "
                f"signals={memory.total_signals} | "
                f"relevant={memory.epi_relevant} | "
                f"high_risk={memory.high_risk_events} | "
                f"errors={len(memory.errors)}"
            )
            if memory.summary:
                logger.info(f"Summary: {memory.summary[:200]}...")

        except Exception as e:
            logger.error(f"Cycle failed with unhandled exception: {e}", exc_info=True)

        logger.info(f"Sleeping {settings.COLLECTION_INTERVAL_SECONDS}s until next cycle...")
        await asyncio.sleep(settings.COLLECTION_INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(run_forever())
