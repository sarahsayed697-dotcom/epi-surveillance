"""
EpiSurveillance Platform — Configuration
Centralised settings via pydantic-settings. Override with environment variables.
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List


class Settings(BaseSettings):
    # ── App ──────────────────────────────────────────────────────────────────
    APP_NAME: str = "EpiSurveillance"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # ── API Keys ─────────────────────────────────────────────────────────────
    ANTHROPIC_API_KEY: str = Field(..., env="ANTHROPIC_API_KEY")
    OPENAI_API_KEY: str = Field("", env="OPENAI_API_KEY")
    TWITTER_BEARER_TOKEN: str = Field("", env="TWITTER_BEARER_TOKEN")
    REDDIT_CLIENT_ID: str = Field("", env="REDDIT_CLIENT_ID")
    REDDIT_CLIENT_SECRET: str = Field("", env="REDDIT_CLIENT_SECRET")
    NEWSAPI_KEY: str = Field("", env="NEWSAPI_KEY")
    GOOGLE_MAPS_API_KEY: str = Field("", env="GOOGLE_MAPS_API_KEY")

    # ── Database ─────────────────────────────────────────────────────────────
    DATABASE_URL: str = Field(
        "postgresql+asyncpg://epi:epi@localhost:5432/episurveillance",
        env="DATABASE_URL",
    )
    REDIS_URL: str = Field("redis://localhost:6379/0", env="REDIS_URL")
    NEO4J_URI: str = Field("bolt://localhost:7687", env="NEO4J_URI")
    NEO4J_USER: str = Field("neo4j", env="NEO4J_USER")
    NEO4J_PASSWORD: str = Field("password", env="NEO4J_PASSWORD")
    ELASTICSEARCH_URL: str = Field("http://localhost:9200", env="ELASTICSEARCH_URL")
    KAFKA_BOOTSTRAP_SERVERS: str = Field("localhost:9092", env="KAFKA_BOOTSTRAP_SERVERS")

    # ── LLM ──────────────────────────────────────────────────────────────────
    PRIMARY_LLM: str = "claude-3-5-sonnet-20241022"
    FAST_LLM: str = "claude-3-haiku-20240307"
    LLM_MAX_TOKENS: int = 4096
    LLM_TEMPERATURE: float = 0.1  # Low temperature for analytical tasks

    # ── Collection ───────────────────────────────────────────────────────────
    COLLECTION_INTERVAL_SECONDS: int = 300  # 5 minutes
    MAX_ITEMS_PER_SOURCE: int = 500
    DEDUPLICATION_WINDOW_HOURS: int = 24

    # ── Risk Thresholds ──────────────────────────────────────────────────────
    RISK_THRESHOLDS: dict = {
        "very_low": 0.20,
        "low": 0.40,
        "moderate": 0.60,
        "high": 0.80,
        "critical": 1.00,
    }

    # ── Diseases of Interest ─────────────────────────────────────────────────
    ZOONOTIC_DISEASES: List[str] = [
        "rabies", "avian influenza", "H5N1", "H7N9", "mpox", "monkeypox",
        "anthrax", "leptospirosis", "brucellosis", "CCHF",
        "crimean-congo hemorrhagic fever", "ebola", "marburg", "nipah",
        "hendra", "west nile virus", "japanese encephalitis", "lyme disease",
        "plague", "q fever", "COVID-19", "SARS-CoV-2", "novel pathogen",
        "disease X", "unknown pathogen", "emerging infectious disease",
    ]

    # ── Alert channels ───────────────────────────────────────────────────────
    ALERT_EMAIL_RECIPIENTS: List[str] = []
    SLACK_WEBHOOK_URL: str = Field("", env="SLACK_WEBHOOK_URL")
    MIN_RISK_LEVEL_FOR_ALERT: str = "high"

    # ── Security ─────────────────────────────────────────────────────────────
    SECRET_KEY: str = Field(..., env="SECRET_KEY")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    ALLOWED_HOSTS: List[str] = ["*"]

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
