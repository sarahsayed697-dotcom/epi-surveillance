"""
EpiSurveillance — FastAPI REST API
Endpoints: events, clusters, alerts, dashboard, search, status
"""
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Query, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from config.settings import settings

app = FastAPI(
    title="EpiSurveillance API",
    description="AI-powered zoonotic disease surveillance platform",
    version=settings.APP_VERSION,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_HOSTS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Response schemas ──────────────────────────────────────────────────────────

class EpiEventResponse(BaseModel):
    id: str
    disease_name: Optional[str]
    risk_level: str
    risk_score: float
    country: Optional[str]
    province: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    human_cases_confirmed: Optional[int]
    human_cases_suspected: Optional[int]
    deaths: Optional[int]
    credibility_label: str
    credibility_score: float
    confidence: float
    llm_reasoning: str
    supporting_evidence: List[str]
    source_type: str
    published_at: Optional[datetime]
    created_at: datetime


class ClusterResponse(BaseModel):
    id: str
    disease_name: str
    cluster_label: str
    status: str
    countries_affected: List[str]
    total_cases: int
    total_deaths: int
    current_rt: Optional[float]
    risk_level: str
    risk_score: float
    is_official_confirmed: bool
    forecast_7d: Optional[dict]
    updated_at: Optional[datetime]


class DashboardStats(BaseModel):
    total_signals_24h: int
    total_events_24h: int
    high_risk_events: int
    critical_events: int
    active_clusters: int
    countries_affected: int
    top_diseases: List[dict]
    top_countries: List[dict]
    recent_alerts: List[dict]
    cycle_summary: str
    last_updated: datetime


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=500)
    disease: Optional[str] = None
    country: Optional[str] = None
    risk_levels: Optional[List[str]] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    limit: int = Field(50, ge=1, le=500)
    offset: int = Field(0, ge=0)


class ManualSignalInput(BaseModel):
    text: str = Field(..., min_length=50, max_length=10000)
    source_type: str = "manual"
    source_url: Optional[str] = None
    published_at: Optional[datetime] = None


# ── Health & status ───────────────────────────────────────────────────────────

@app.get("/api/health", tags=["system"])
async def health_check():
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/status", tags=["system"])
async def system_status():
    """Returns status of all integrated services."""
    return {
        "api": "online",
        "database": "online",  # Check real connection in production
        "redis": "online",
        "elasticsearch": "online",
        "kafka": "online",
        "llm": "online",
        "last_collection_cycle": datetime.now(timezone.utc).isoformat(),
        "next_collection_cycle": datetime.now(timezone.utc).isoformat(),
    }


# ── Dashboard ─────────────────────────────────────────────────────────────────

@app.get("/api/dashboard", response_model=DashboardStats, tags=["dashboard"])
async def get_dashboard():
    """
    Main dashboard statistics. In production, queries Redis cache first.
    Cache is updated after each surveillance cycle.
    """
    # Stub response — replace with real DB queries
    return DashboardStats(
        total_signals_24h=1847,
        total_events_24h=243,
        high_risk_events=12,
        critical_events=2,
        active_clusters=8,
        countries_affected=34,
        top_diseases=[
            {"disease": "Avian Influenza H5N1", "count": 87, "risk": "high"},
            {"disease": "Mpox", "count": 54, "risk": "moderate"},
            {"disease": "West Nile Virus", "count": 41, "risk": "low"},
        ],
        top_countries=[
            {"country": "Egypt", "count": 43, "risk_level": "high"},
            {"country": "Vietnam", "count": 38, "risk_level": "moderate"},
            {"country": "USA", "count": 31, "risk_level": "low"},
        ],
        recent_alerts=[
            {
                "id": "alert-001",
                "title": "H5N1 outbreak in poultry — Egypt",
                "risk_level": "high",
                "created_at": "2024-01-15T08:30:00Z",
            },
        ],
        cycle_summary=(
            "Surveillance cycle identified elevated H5N1 activity in Egypt and Vietnam. "
            "Two critical-risk signals detected: novel avian influenza strain in Egypt "
            "with suspected human exposure. Recommend WHO notification."
        ),
        last_updated=datetime.now(timezone.utc),
    )


# ── Events ────────────────────────────────────────────────────────────────────

@app.get("/api/events", tags=["events"])
async def list_events(
    risk_level: Optional[str] = Query(None, description="Filter by risk level"),
    disease: Optional[str] = Query(None, description="Filter by disease name"),
    country: Optional[str] = Query(None, description="Filter by country"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """
    List extracted epidemiological events with filters.
    Returns paginated results ordered by risk_score DESC.
    """
    # In production: query PostgreSQL with SQLAlchemy
    return {
        "total": 0,
        "limit": limit,
        "offset": offset,
        "events": [],
        "message": "Connect to database to retrieve events",
    }


@app.get("/api/events/{event_id}", tags=["events"])
async def get_event(event_id: str):
    """Get a single event by ID with full XAI reasoning."""
    # In production: fetch from DB and include reasoning chain
    raise HTTPException(status_code=404, detail=f"Event {event_id} not found")


# ── Clusters ──────────────────────────────────────────────────────────────────

@app.get("/api/clusters", tags=["clusters"])
async def list_clusters(
    status: Optional[str] = Query("active"),
    risk_level: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
):
    """List active outbreak clusters."""
    return {"total": 0, "clusters": []}


@app.get("/api/clusters/{cluster_id}/forecast", tags=["clusters"])
async def get_cluster_forecast(cluster_id: str):
    """Get 7-day case forecast with confidence intervals for a cluster."""
    raise HTTPException(status_code=404, detail=f"Cluster {cluster_id} not found")


# ── Map data ──────────────────────────────────────────────────────────────────

@app.get("/api/map/events", tags=["map"])
async def get_map_events(
    risk_levels: Optional[str] = Query(None, description="Comma-separated risk levels"),
    days_back: int = Query(7, ge=1, le=90),
):
    """
    GeoJSON FeatureCollection of events for map display.
    Includes risk level, disease, case count per point.
    """
    return {
        "type": "FeatureCollection",
        "features": [],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/map/heatmap", tags=["map"])
async def get_heatmap_data(days_back: int = Query(7, ge=1, le=90)):
    """Heatmap data: list of [lat, lon, intensity] for Leaflet.heat."""
    return {"points": [], "generated_at": datetime.now(timezone.utc).isoformat()}


# ── Search ────────────────────────────────────────────────────────────────────

@app.post("/api/search", tags=["search"])
async def semantic_search(request: SearchRequest):
    """
    Full-text + semantic search over events and signals.
    Uses Elasticsearch with vector embeddings.
    """
    return {
        "query": request.query,
        "total": 0,
        "results": [],
        "message": "Connect to Elasticsearch to enable search",
    }


# ── Manual signal submission ──────────────────────────────────────────────────

@app.post("/api/signals/submit", tags=["signals"])
async def submit_signal(signal: ManualSignalInput, background_tasks: BackgroundTasks):
    """
    Submit a manual signal (e.g. from a field officer) for immediate processing.
    Processing happens asynchronously.
    """
    from core.processors.text_processor import TextProcessor
    from core.extractors.llm_extractor import extract_epi_data
    import uuid

    signal_id = str(uuid.uuid4())

    async def _process():
        processor = TextProcessor()
        processed = await processor.process(signal.text, signal.source_type)
        if processed.get("skip"):
            return
        result = await extract_epi_data(
            text=processed.get("text_translated") or signal.text,
            source_type=signal.source_type,
            collection_date=datetime.now(timezone.utc).isoformat(),
        )
        logger.info(f"Manual signal {signal_id}: {result.disease_name}, risk={result.risk_level}")

    background_tasks.add_task(_process)

    return {
        "signal_id": signal_id,
        "status": "queued",
        "message": "Signal accepted for processing. Results available shortly.",
    }


# ── Surveillance cycle trigger ────────────────────────────────────────────────

@app.post("/api/cycle/trigger", tags=["system"])
async def trigger_surveillance_cycle(background_tasks: BackgroundTasks):
    """Manually trigger a surveillance collection cycle."""
    from agents.supervisor.supervisor import SupervisorAgent

    async def _run():
        agent = SupervisorAgent()
        memory = await agent.run_cycle()
        logger.info(f"Manual cycle complete: {memory.summary[:100]}")

    background_tasks.add_task(_run)
    return {"status": "cycle_started", "message": "Surveillance cycle triggered"}


# ── Alerts ────────────────────────────────────────────────────────────────────

@app.get("/api/alerts", tags=["alerts"])
async def list_alerts(
    risk_level: Optional[str] = None,
    is_sent: Optional[bool] = None,
    limit: int = Query(20, ge=1, le=100),
):
    """List generated alerts."""
    return {"total": 0, "alerts": []}


@app.get("/api/alerts/{alert_id}", tags=["alerts"])
async def get_alert(alert_id: str):
    """Get full alert with reasoning and evidence."""
    raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
