"""
EpiSurveillance — Test Suite
Unit tests for extraction pipeline, text processing, and risk scoring.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from core.processors.text_processor import (
    clean_text, compute_content_hash, keyword_density_score,
    is_likely_bot, detect_satire, TextProcessor
)
from core.extractors.llm_extractor import ExtractedEpiData


# ── Text processor tests ──────────────────────────────────────────────────────

class TestCleanText:
    def test_removes_urls(self):
        text = "Outbreak reported https://example.com/article see more"
        cleaned = clean_text(text)
        assert "https://" not in cleaned
        assert "Outbreak reported" in cleaned

    def test_removes_mentions(self):
        text = "Rabies case reported @WHO @CDC please see this"
        cleaned = clean_text(text)
        assert "@WHO" not in cleaned
        assert "Rabies case reported" in cleaned

    def test_expands_hashtags(self):
        text = "New #H5N1 outbreak in Vietnam"
        cleaned = clean_text(text)
        assert "H5N1" in cleaned
        assert "#H5N1" not in cleaned

    def test_removes_retweet_markers(self):
        text = "RT: Major outbreak detected in Egypt"
        cleaned = clean_text(text)
        assert "RT" not in cleaned
        assert "Major outbreak" in cleaned


class TestKeywordDensity:
    def test_high_density_epi_text(self):
        text = "Rabies outbreak kills 5 people. Cases spreading. WHO investigating."
        score = keyword_density_score(text)
        assert score > 0.2

    def test_low_density_unrelated_text(self):
        text = "The weather is nice today. I had coffee this morning."
        score = keyword_density_score(text)
        assert score < 0.05

    def test_official_disease_names(self):
        text = "H5N1 avian influenza spillover event confirmed"
        score = keyword_density_score(text)
        assert score > 0.3


class TestBotDetection:
    def test_excessive_urls_flagged(self):
        text = " ".join([f"http://spam.com/{i}" for i in range(10)])
        assert is_likely_bot(text) is True

    def test_normal_text_not_flagged(self):
        text = "New rabies outbreak reported in rural Kenya. Officials investigating."
        assert is_likely_bot(text) is False

    def test_repetitive_content_flagged(self):
        text = "Buy now. Buy now. Buy now. Buy now. Buy now."
        assert is_likely_bot(text) is True


class TestSatireDetection:
    def test_babylon_bee_detected(self):
        text = "Babylon Bee: CDC announces new disease only affects people who listen to NPR"
        assert detect_satire(text) is True

    def test_real_news_not_satire(self):
        text = "WHO reports 3 confirmed cases of H5N1 in Vietnam"
        assert detect_satire(text) is False


class TestContentHash:
    def test_same_text_same_hash(self):
        text = "Rabies cases reported in Egypt"
        assert compute_content_hash(text) == compute_content_hash(text)

    def test_normalized_text_same_hash(self):
        text1 = "Rabies cases reported in Egypt"
        text2 = "rabies  cases  reported  in  egypt"  # Extra spaces, lowercase
        assert compute_content_hash(text1) == compute_content_hash(text2)

    def test_different_text_different_hash(self):
        assert compute_content_hash("Rabies") != compute_content_hash("H5N1")


# ── ExtractedEpiData validation ───────────────────────────────────────────────

class TestExtractedEpiData:
    def test_valid_high_risk_event(self):
        data = ExtractedEpiData(
            disease_name="H5N1 Avian Influenza",
            country="Egypt",
            human_cases_confirmed=3,
            deaths=1,
            risk_level="high",
            risk_score=0.75,
            credibility_label="verified",
            credibility_score=0.9,
            confidence=0.85,
            is_epi_relevant=True,
            llm_reasoning="Multiple credible sources confirm H5N1 human cases.",
        )
        assert data.risk_level == "high"
        assert data.is_epi_relevant is True
        assert 0 <= data.risk_score <= 1

    def test_score_bounds_enforced(self):
        with pytest.raises(Exception):
            ExtractedEpiData(risk_score=1.5)  # > 1.0 should fail

    def test_default_values(self):
        data = ExtractedEpiData()
        assert data.risk_level == "very_low"
        assert data.is_epi_relevant is False
        assert data.symptoms == []
        assert data.animal_species == []


# ── Async tests ───────────────────────────────────────────────────────────────

class TestTextProcessor:
    @pytest.mark.asyncio
    async def test_skips_short_text(self):
        processor = TextProcessor()
        result = await processor.process("Hi", "twitter")
        assert result.get("skip") is True

    @pytest.mark.asyncio
    async def test_processes_epi_text(self):
        processor = TextProcessor()
        text = (
            "BREAKING: H5N1 avian influenza outbreak confirmed in Egypt. "
            "3 human cases, 1 death. WHO investigating transmission. "
            "Poultry farms in Alexandria affected. Officials report animal-human spillover."
        )
        with patch.object(processor, "__class__") as _:
            # Patch language detection to avoid API call in tests
            with patch(
                "core.processors.text_processor.detect_language",
                new=AsyncMock(return_value="en"),
            ):
                result = await processor.process(text, "news")
                assert result.get("skip") is not True
                assert result.get("keyword_density", 0) > 0.1

    @pytest.mark.asyncio
    async def test_skips_low_density_social_text(self):
        processor = TextProcessor()
        text = (
            "Just had the most amazing burger at this new restaurant downtown! "
            "The fries were crispy and the shake was incredible. Totally recommend!"
        )
        result = await processor.process(text, "twitter")
        assert result.get("skip") is True


# ── Risk scoring integration ──────────────────────────────────────────────────

class TestRiskScoring:
    """Validate that risk scores align with epidemiological expectations."""

    def test_novel_pathogen_is_highest_risk(self):
        """A novel pathogen with human transmission should be critical."""
        event = ExtractedEpiData(
            disease_name="Unknown novel pathogen",
            is_novel_pathogen=True,
            human_cases_confirmed=10,
            deaths=3,
            risk_level="critical",
            risk_score=0.95,
            credibility_label="verified",
            confidence=0.8,
            is_epi_relevant=True,
        )
        assert event.risk_level == "critical"
        assert event.risk_score >= 0.8

    def test_rumor_without_cases_is_low_risk(self):
        """An unverified rumor with no case numbers should be low risk."""
        event = ExtractedEpiData(
            disease_name="Rabies",
            credibility_label="rumor",
            credibility_score=0.2,
            human_cases_confirmed=None,
            human_cases_suspected=None,
            risk_level="very_low",
            risk_score=0.1,
            is_epi_relevant=True,
        )
        assert event.risk_level in ("very_low", "low")
        assert event.risk_score < 0.4


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_h5n1_text():
    return (
        "URGENT: WHO confirms human cases of H5N1 avian influenza in Egypt. "
        "Three poultry workers in Alexandria have tested positive. One death reported. "
        "Patients presented with high fever, respiratory distress, and pneumonia. "
        "Egyptian Ministry of Health and WHO teams deployed. "
        "Millions of birds culled in affected farms. "
        "Investigation into human-to-human transmission ongoing."
    )


@pytest.fixture
def sample_rumor_text():
    return (
        "Unconfirmed reports on social media claim there's some new virus spreading "
        "in rural areas. No official sources have commented. Take with a grain of salt."
    )
