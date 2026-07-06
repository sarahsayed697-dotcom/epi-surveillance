"""
scripts/demo.py
Quick end-to-end demo — no Docker required.
Tests the full pipeline on a sample text using your ANTHROPIC_API_KEY.

Usage:
    export ANTHROPIC_API_KEY=your_key_here
    python scripts/demo.py
"""
import asyncio
import json
import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Minimal env for demo (no DB, no Redis needed)
os.environ.setdefault("SECRET_KEY", "demo-secret-key")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://epi:epi@localhost:5432/episurveillance")

from core.processors.text_processor import TextProcessor, keyword_density_score
from core.extractors.llm_extractor import extract_epi_data

SAMPLE_SIGNALS = [
    {
        "name": "High-risk H5N1 news article",
        "source_type": "news",
        "text": (
            "BREAKING: Egyptian health authorities confirmed three human cases of H5N1 avian influenza "
            "in Alexandria governorate. All three patients are poultry workers with direct exposure "
            "to infected birds. One 52-year-old man has died. Patients presented with high fever "
            "(39.5°C), severe respiratory distress, and pneumonia. Millions of poultry have been "
            "culled in affected farms. WHO investigators have deployed to assess spillover risk. "
            "Officials urge heightened biosecurity on farms across the Delta region."
        ),
    },
    {
        "name": "Low-risk social media rumor",
        "source_type": "twitter",
        "text": (
            "Heard from a friend that there's some weird new disease going around in the village. "
            "People getting sick. Not sure what it is. No official word yet. Stay safe everyone."
        ),
    },
    {
        "name": "Official WHO report",
        "source_type": "who",
        "text": (
            "Disease Outbreak News — Nipah virus infection, India. "
            "As of 15 September 2023, a total of 6 cases of Nipah virus infection including 2 deaths "
            "have been reported from Kozhikode district of Kerala State, India. "
            "Of the 6 cases, 2 have died, 4 remain hospitalized. "
            "Fruit bats (Pteropus medius) are the natural reservoir of Nipah virus in India. "
            "Contact tracing is ongoing. No evidence of sustained human-to-human transmission."
        ),
    },
]


async def run_demo():
    print("\n" + "=" * 70)
    print("  EpiSurveillance — Pipeline Demo")
    print("=" * 70)

    processor = TextProcessor()

    for i, signal in enumerate(SAMPLE_SIGNALS, 1):
        print(f"\n[{i}/3] {signal['name']}")
        print("-" * 50)
        print(f"Text preview: {signal['text'][:100]}...")

        # Step 1: Keyword density (fast, no API)
        density = keyword_density_score(signal["text"])
        print(f"Keyword density: {density:.2%}")

        # Step 2: Text processing (language detection + translation)
        print("Processing text...")
        processed = await processor.process(signal["text"], signal["source_type"])

        if processed.get("skip"):
            print(f"⚡ Skipped: {processed.get('reason')}")
            continue

        print(f"Language: {processed.get('language_detected', 'unknown')}")
        print(f"Bot: {processed.get('is_bot', False)} | Satire: {processed.get('is_satire', False)}")

        # Step 3: LLM extraction
        print("Running LLM extraction (Claude)...")
        result = await extract_epi_data(
            text=processed.get("text_translated") or signal["text"],
            source_type=signal["source_type"],
            collection_date=datetime.now(timezone.utc).isoformat(),
        )

        # Display results
        print(f"\n  {'✓' if result.is_epi_relevant else '✗'} Epi relevant: {result.is_epi_relevant}")
        if result.is_epi_relevant:
            print(f"  Disease:      {result.disease_name}")
            print(f"  Location:     {result.country}, {result.province}")
            print(f"  Cases:        {result.human_cases_confirmed} confirmed / {result.human_cases_suspected} suspected")
            print(f"  Deaths:       {result.deaths}")
            print(f"  Risk level:   {result.risk_level.upper()} (score: {result.risk_score:.2f})")
            print(f"  Credibility:  {result.credibility_label} ({result.credibility_score:.0%})")
            print(f"  Confidence:   {result.confidence:.0%}")
            if result.r0_estimate:
                print(f"  R0 estimate:  {result.r0_estimate}")
            if result.spillover_probability:
                print(f"  Spillover Pr: {result.spillover_probability:.0%}")
            print(f"  Reasoning:    {result.llm_reasoning[:150]}...")
        print()

    print("=" * 70)
    print("Demo complete. Run 'make up && make init-db' for full stack.")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: Set ANTHROPIC_API_KEY environment variable first.")
        print("       export ANTHROPIC_API_KEY=your_key_here")
        sys.exit(1)
    asyncio.run(run_demo())
