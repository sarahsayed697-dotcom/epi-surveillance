"""
EpiSurveillance — Database Models
SQLAlchemy 2.0 async ORM with full schema for outbreak surveillance.
"""
from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    Column, String, Float, Integer, Boolean, DateTime,
    ForeignKey, JSON, Text, Index, Enum as SAEnum
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.sql import func
import uuid
import enum


class Base(DeclarativeBase):
    pass


class RiskLevel(str, enum.Enum):
    VERY_LOW = "very_low"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class SourceType(str, enum.Enum):
    TWITTER = "twitter"
    REDDIT = "reddit"
    FACEBOOK = "facebook"
    TELEGRAM = "telegram"
    NEWS = "news"
    WHO = "who"
    CDC = "cdc"
    FAO = "fao"
    WOAH = "woah"
    PUBMED = "pubmed"
    GOVERNMENT = "government"
    RSS = "rss"


class CredibilityLabel(str, enum.Enum):
    VERIFIED = "verified"
    RUMOR = "rumor"
    DUPLICATE = "duplicate"
    SATIRE = "satire"
    MISINFORMATION = "misinformation"
    CONSPIRACY = "conspiracy"
    BOT_GENERATED = "bot_generated"
    UNKNOWN = "unknown"


# ── Raw signal (one row per collected post/article) ──────────────────────────

class RawSignal(Base):
    __tablename__ = "raw_signals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_type = Column(SAEnum(SourceType), nullable=False, index=True)
    source_url = Column(String(2048))
    source_id = Column(String(512))           # External ID from source
    collected_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    published_at = Column(DateTime(timezone=True), index=True)
    language_detected = Column(String(10))
    text_original = Column(Text, nullable=False)
    text_translated = Column(Text)            # English translation if needed
    author = Column(String(256))
    engagement_score = Column(Float, default=0)  # likes + shares + comments
    content_hash = Column(String(64), unique=True, index=True)  # for dedup

    # Processing status
    is_processed = Column(Boolean, default=False, index=True)
    processing_error = Column(Text)

    # Relationships
    extracted_events = relationship("EpiEvent", back_populates="raw_signal")

    __table_args__ = (
        Index("ix_raw_signals_source_published", "source_type", "published_at"),
    )


# ── Epidemiological event (structured extraction from signal) ─────────────────

class EpiEvent(Base):
    __tablename__ = "epi_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    raw_signal_id = Column(UUID(as_uuid=True), ForeignKey("raw_signals.id"), index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Disease information
    disease_name = Column(String(256), index=True)
    disease_synonyms = Column(ARRAY(String))
    pathogen_type = Column(String(64))        # virus, bacterium, prion, etc.
    is_novel_pathogen = Column(Boolean, default=False)

    # Host & transmission
    animal_species = Column(ARRAY(String))
    suspected_reservoir = Column(ARRAY(String))
    suspected_vector = Column(ARRAY(String))
    transmission_route = Column(String(256))
    human_cases_suspected = Column(Integer)
    human_cases_confirmed = Column(Integer)
    deaths = Column(Integer)
    hospitalizations = Column(Integer)
    symptoms = Column(ARRAY(String))

    # Location
    country = Column(String(128), index=True)
    province = Column(String(128))
    city = Column(String(128))
    latitude = Column(Float)
    longitude = Column(Float)
    geo_confidence = Column(Float)            # 0–1

    # Temporal
    event_date_start = Column(DateTime(timezone=True))
    event_date_end = Column(DateTime(timezone=True))

    # Credibility
    credibility_label = Column(SAEnum(CredibilityLabel), default=CredibilityLabel.UNKNOWN)
    credibility_score = Column(Float)         # 0–1
    source_reliability = Column(Float)        # 0–1
    cross_source_count = Column(Integer, default=1)

    # Risk
    risk_level = Column(SAEnum(RiskLevel), index=True)
    risk_score = Column(Float)               # 0–1
    risk_factors = Column(JSON)              # breakdown dict

    # Explainability
    llm_reasoning = Column(Text)
    supporting_evidence = Column(JSON)
    contradictory_evidence = Column(JSON)
    confidence = Column(Float)               # 0–1

    # Epidemiological estimates (may be null for unconfirmed events)
    r0_estimate = Column(Float)
    rt_estimate = Column(Float)
    cfr_estimate = Column(Float)
    attack_rate = Column(Float)
    doubling_time_days = Column(Float)

    # Relationships
    raw_signal = relationship("RawSignal", back_populates="extracted_events")
    cluster = relationship("OutbreakCluster", secondary="event_cluster_link", back_populates="events")
    alerts = relationship("Alert", back_populates="event")

    __table_args__ = (
        Index("ix_epi_events_disease_country", "disease_name", "country"),
        Index("ix_epi_events_risk_level", "risk_level"),
    )


# ── Outbreak cluster (group of related events) ───────────────────────────────

class OutbreakCluster(Base):
    __tablename__ = "outbreak_clusters"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    disease_name = Column(String(256), index=True)
    cluster_label = Column(String(512))       # Human-readable name
    status = Column(String(64), default="active")  # active, resolved, monitoring

    # Geography
    countries_affected = Column(ARRAY(String))
    bounding_box = Column(JSON)              # {min_lat, max_lat, min_lon, max_lon}

    # Epidemiology
    total_cases = Column(Integer, default=0)
    total_deaths = Column(Integer, default=0)
    peak_rt = Column(Float)
    current_rt = Column(Float)
    spillover_probability = Column(Float)    # animal→human

    # Risk
    risk_level = Column(SAEnum(RiskLevel), index=True)
    risk_score = Column(Float)
    is_official_confirmed = Column(Boolean, default=False)

    # Forecast
    forecast_7d = Column(JSON)               # {date: cases} predictions
    forecast_confidence_interval = Column(JSON)

    events = relationship("EpiEvent", secondary="event_cluster_link", back_populates="cluster")
    alerts = relationship("Alert", back_populates="cluster")


class EventClusterLink(Base):
    __tablename__ = "event_cluster_link"
    event_id = Column(UUID(as_uuid=True), ForeignKey("epi_events.id"), primary_key=True)
    cluster_id = Column(UUID(as_uuid=True), ForeignKey("outbreak_clusters.id"), primary_key=True)


# ── Alerts ───────────────────────────────────────────────────────────────────

class Alert(Base):
    __tablename__ = "alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    sent_at = Column(DateTime(timezone=True))

    event_id = Column(UUID(as_uuid=True), ForeignKey("epi_events.id"), nullable=True)
    cluster_id = Column(UUID(as_uuid=True), ForeignKey("outbreak_clusters.id"), nullable=True)

    risk_level = Column(SAEnum(RiskLevel), nullable=False)
    title = Column(String(512), nullable=False)
    summary = Column(Text, nullable=False)
    channels = Column(ARRAY(String))         # ["email", "slack", "webhook"]
    is_sent = Column(Boolean, default=False)
    recipients = Column(ARRAY(String))

    event = relationship("EpiEvent", back_populates="alerts")
    cluster = relationship("OutbreakCluster", back_populates="alerts")
