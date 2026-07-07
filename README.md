# EpiSurveillance 🦠

> **LLMs for Automated Zoonotic Disease Surveillance from Social Media and News Feeds**

[![CI](https://github.com/sarahsayed697-dotcom/epi-surveillance/actions/workflows/ci.yml/badge.svg)](https://github.com/sarahsayed697-dotcom/epi-surveillance/actions)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110-green.svg)](https://fastapi.tiangolo.com)
[![Claude API](https://img.shields.io/badge/Claude-3.5%20Sonnet-orange.svg)](https://anthropic.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A production-grade, multi-agent AI platform for early detection of zoonotic disease outbreaks.
Continuously monitors Twitter/X, Reddit, WHO, CDC, FAO, news feeds, and PubMed — then uses
Claude (Anthropic) to extract structured epidemiological intelligence with explainable risk
scoring, fake news detection, and real-time alerting.

---

## 🌍 Why This Project

Zoonotic diseases — infections that jump from animals to humans — account for over 60% of
emerging infectious diseases globally. Early detection is critical, yet official reporting
systems often lag weeks behind actual events. This platform bridges that gap by continuously
monitoring open digital sources and applying AI to identify outbreak signals days or weeks
before official notifications.

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🌐 Multi-source ingestion | Twitter/X, Reddit, WHO, CDC, FAO, NewsAPI, PubMed, RSS feeds |
| 🦠 20+ diseases monitored | H5N1, Mpox, Ebola, Nipah, Rabies, Plague, Disease X, and more |
| 🧠 Claude AI extraction | 30+ structured fields per signal: cases, deaths, GPS, symptoms, transmission |
| 🤖 Multi-agent architecture | Supervisor, Epidemiologist, Fact-Checker, Alert, and Predictor agents |
| 📊 Risk scoring | 5-level composite score (Very Low → Critical) with full XAI reasoning |
| 🔍 Fake news detection | Classifies signals as verified / rumor / satire / misinformation / bot |
| 📈 Epi parameters | Estimates R0, Rt, CFR, doubling time, and spillover probability |
| 🚨 Real-time alerting | Slack, email, and webhook notifications for high-risk events |
| 🗺️ Interactive dashboard | World map, heatmap, timelines, forecasts, and confidence intervals |
| 🔒 Production-ready | FastAPI, PostgreSQL, Redis, Elasticsearch, Neo4j, Kafka, Grafana |
Data Sources → NLP Pipeline → Multi-Agent AI → Risk Engine → Dashboard & Alerts
↓               ↓               ↓               ↓               ↓
Twitter/X      Language         Supervisor      PostgreSQL     React/Next.js
Reddit        Detection         Agent           Neo4j          World map
WHO/CDC       Translation    Epidemiologist  Elasticsearch    Alert system
NewsAPI         Cleaning      Fact-Checker      Redis           Grafana
PubMed        NER/Extract      Predictor        Kafka

---

## 🚀 Quick Start

### Option A — Demo (no Docker required)

```bash
git clone https://github.com/sarahsayed697-dotcom/epi-surveillance.git
cd epi-surveillance
pip install -r requirements.txt
export ANTHROPIC_API_KEY=your_key_here
python scripts/demo.py
```

Runs the full AI extraction pipeline on 3 sample signals and prints structured results —
no database or Docker needed.

### Option B — Full Stack with Docker

```bash
git clone https://github.com/sarahsayed697-dotcom/epi-surveillance.git
cd epi-surveillance
cp .env.example .env          # Add your ANTHROPIC_API_KEY
make up                       # Start all 10 services
make init-db                  # Create database tables
make cycle                    # Trigger first surveillance cycle
```

| Service | URL |
|---------|-----|
| API docs | http://localhost:8000/api/docs |
| Dashboard | http://localhost:3000 |
| Grafana | http://localhost:3001 (admin/admin) |
| Neo4j Browser | http://localhost:7474 |
| Prometheus | http://localhost:9090 |

### Option C — Local development

```bash
pip install -r requirements.txt
cp .env.example .env
docker-compose up -d postgres redis   # Only DB services
make init-db
make run-api      # Terminal 1 — FastAPI on port 8000
make run-worker   # Terminal 2 — Surveillance cycle every 5 min
```

---

## 📁 Project Structure
epi-surveillance/
│
├── api/
│   └── main.py                         # FastAPI REST API — 15 endpoints
│
├── agents/
│   ├── supervisor/supervisor.py        # Master orchestrator
│   ├── epidemiologist/                 # R0, Rt, CFR estimation
│   ├── fact_checker/                   # Cross-source validation
│   └── alert/                         # Slack / email alert dispatch
│
├── core/
│   ├── collectors/collectors.py        # Twitter, Reddit, WHO, News collectors
│   ├── processors/text_processor.py   # Language detect, translate, clean, dedup
│   └── extractors/llm_extractor.py    # Claude-powered extraction engine
│
├── db/
│   ├── models.py                       # SQLAlchemy ORM — 4 tables
│   └── database.py                    # Async PostgreSQL engine
│
├── config/
│   ├── settings.py                    # Pydantic environment settings
│   └── prometheus.yml                 # Monitoring configuration
│
├── scripts/
│   ├── demo.py                        # Quick test — no Docker needed
│   ├── init_db.py                     # Database table creation
│   └── run_surveillance_cycle.py      # Continuous surveillance worker
│
├── tests/
│   └── test_pipeline.py               # 20+ unit and async tests
│
├── docker/
│   └── Dockerfile.api                 # API container
│
├── .github/workflows/ci.yml           # GitHub Actions CI/CD pipeline
├── docker-compose.yml                 # Full 10-service stack
├── Makefile                           # One-command operations
├── requirements.txt
└── .env.example

---

## ⚙️ Environment Variables

Copy `.env.example` to `.env` and fill in your values:

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | ✅ Required | Your Claude API key — [get one here](https://console.anthropic.com) |
| `SECRET_KEY` | ✅ Required | Random string for JWT token signing |
| `TWITTER_BEARER_TOKEN` | Optional | Enables Twitter/X signal collection |
| `REDDIT_CLIENT_ID` | Optional | Enables Reddit signal collection |
| `REDDIT_CLIENT_SECRET` | Optional | Enables Reddit signal collection |
| `NEWSAPI_KEY` | Optional | Enables news article collection |
| `GOOGLE_MAPS_API_KEY` | Optional | Enhanced geocoding accuracy |
| `SLACK_WEBHOOK_URL` | Optional | Enables Slack alert notifications |

The platform runs with **only `ANTHROPIC_API_KEY`** — all other keys are optional and expand coverage.

---

## 🤖 AI Pipeline
Raw text (any language)
↓
Text Processor
→ Clean & normalise
→ Detect language
→ Translate to English (Claude)
→ Deduplicate via content hash
↓
Keyword density filter
→ Route to fast model (Haiku) or full model (Sonnet)
↓
Claude extraction — 30+ structured fields
{disease, cases, deaths, symptoms, location,
GPS coordinates, transmission route,
credibility label, risk score, R0, reasoning}
↓
FactCheckerAgent
→ Cross-source validation
→ Misinformation detection
↓
EpidemiologistAgent
→ R0 / Rt / CFR estimation
→ Spillover probability
↓
Risk scoring (7-factor composite 0–1)
↓
AlertAgent
→ Slack / email for High & Critical events
↓
PostgreSQL + Neo4j + Elasticsearch + Dashboard

**Model routing strategy:**
- `claude-3-5-sonnet` — full extraction on high-priority, high-density signals
- `claude-3-haiku` — bulk screening of low keyword-density content (cost-efficient)

---

## 🎯 Risk Classification

| Level | Score | Criteria |
|-------|-------|----------|
| 🟢 Very Low | 0.0 – 0.2 | Vague report, single low-credibility source |
| 🟡 Low | 0.2 – 0.4 | Unconfirmed, no human cases |
| 🟠 Moderate | 0.4 – 0.6 | Animal cases only, credible source |
| 🔴 High | 0.6 – 0.8 | Confirmed human cases, verified by multiple sources |
| 🚨 Critical | 0.8 – 1.0 | Novel pathogen, multi-country spread, officially confirmed |

**7 risk factors scored per event:**
multi-source confirmation · official confirmation · human involvement ·
animal involvement · novel pathogen flag · severity · geographic spread

---

## 🦠 Diseases Monitored
Rabies          Avian Influenza H5N1    H7N9           Mpox
Anthrax         Leptospirosis           Brucellosis    CCHF
Ebola           Marburg                 Nipah          Hendra
West Nile       Japanese Encephalitis   Lyme Disease   Plague
Q Fever         COVID-19 variants       Disease X      Novel unknown pathogens

---

## 🌐 API Reference
GET  /api/health                    System health check
GET  /api/status                    All service statuses
GET  /api/dashboard                 24-hour surveillance summary
GET  /api/events                    List events (filter by disease, country, risk)
GET  /api/events/{id}               Single event with full XAI reasoning
GET  /api/clusters                  Active outbreak clusters
GET  /api/clusters/{id}/forecast    7-day case forecast with confidence intervals
GET  /api/map/events                GeoJSON FeatureCollection for map display
GET  /api/map/heatmap               Heatmap data [lat, lon, intensity]
POST /api/search                    Semantic search over all events
POST /api/signals/submit            Manual signal submission (field officers)
POST /api/cycle/trigger             Trigger surveillance cycle manually
GET  /api/alerts                    Alert history
GET  /api/alerts/{id}               Single alert with evidence chain

Full interactive docs available at `http://localhost:8000/api/docs`

---

## 🧪 Running Tests

```bash
make test

# or directly:
pytest tests/ -v --asyncio-mode=auto --cov=. --cov-report=term-missing
```

Test coverage includes: text cleaning, bot detection, satire detection,
keyword density scoring, content hashing, risk score validation,
Pydantic schema enforcement, and async processing pipeline.

---

## 🛠️ Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| LLM | Claude 3.5 Sonnet + Claude 3 Haiku | Extraction, translation, reasoning |
| API | FastAPI + Pydantic v2 | REST API, validation, async |
| Relational DB | PostgreSQL 16 + SQLAlchemy | Events, clusters, alerts |
| Graph DB | Neo4j 5 | Disease–host–location knowledge graph |
| Search | Elasticsearch 8 | Full-text + semantic search |
| Cache | Redis 7 | Dashboard stats, deduplication set |
| Streaming | Apache Kafka | High-throughput signal ingestion |
| Monitoring | Grafana + Prometheus | Metrics and alerting |
| CI/CD | GitHub Actions | Lint, test, build, deploy |
| Containers | Docker + Docker Compose | Local and cloud deployment |

---

## 📊 Research Evaluation Metrics

| Metric | Target | Description |
|--------|--------|-------------|
| Precision | > 0.80 | Fraction of alerts that are true events |
| Recall | > 0.75 | Fraction of true events detected |
| F1-score | > 0.77 | Harmonic mean of precision and recall |
| AUROC | > 0.85 | Overall discrimination ability |
| Lead time | > 7 days | Detection before official WHO/CDC reporting |
| False alarm rate | < 0.15 | Fraction of alerts that are false positives |
| Latency | < 2 hours | Signal collection to alert dispatch |

**Benchmark datasets:** ProMED-mail archive · HealthMap · WHO Disease Outbreak News · EpiWatch

---

## 🤝 Contributing

Contributions are welcome. To contribute:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Make your changes and run tests: `make test`
4. Submit a pull request with a clear description

Please follow the existing code style and include tests for new features.

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

## 📚 Citation

If you use EpiSurveillance in your research, please cite:

```bibtex
@software{episurveillance2024,
  title   = {EpiSurveillance: LLMs for Automated Zoonotic Disease Surveillance
             from Social Media and News Feeds},
  author  = {Sayed, Sarah},
  year    = {2024},
  url     = {https://github.com/sarahsayed697-dotcom/epi-surveillance},
  license = {MIT}
}
```

---

## 👩‍💻 Author

**Sarah Sayed**
- GitHub: [@sarahsayed697-dotcom](https://github.com/sarahsayed697-dotcom)

---

*Built with Claude AI (Anthropic) · FastAPI · PostgreSQL · Docker*
---

## 🏗️ System Architecture
