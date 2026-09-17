# 🔥 Fight Fire With AI

> A wildfire risk prediction and dynamic evacuation routing platform for the San Francisco Bay Area, powered by a U-Net / PINN / Reinforcement Learning ML ensemble and deployed on Google Cloud Platform.

**Team:** Earl Padron · Isla Shi · Scott Kennedy · Nikhil Koganti  
**Course:** CMPE 295A — Master's Project (San José State University)  
**Advisor:** Dr. Jerry Gao

---

## 📖 About The Project

Fight Fire With AI is a day-ahead fire risk planning and dynamic evacuation routing system scoped to the 9-county San Francisco Bay Area. It synthesizes satellite imagery, weather telemetry, vegetation indices, and terrain data to produce a live fire risk heatmap on a 1×1 km spatial grid — and uses that prediction to calculate safe A\* evacuation routes in real time.

The system directly extends three peer-reviewed publications by Dr. Jerry Gao:

| Paper | Contribution Extended |
|---|---|
| Malik et al., *Atmosphere* 2021 | Grid-based risk prediction with terrain + vegetation features |
| Adhikari et al., *IEEE CCWC* 2024 | Deep Reinforcement Learning (DQN) for fire progression modeling |
| Malik et al., *IEEE CCWC* 2022 | Ensemble majority voting via Cellular Automata Rule 30 |

### Architecture Overview

```
[External Data Sources]
  GEE (GOES-18, VIIRS, Landsat) + NOAA/NWS + USGS DEM
          │
          ▼  (Celery daily cron — Compute Engine)
[Django Harvester] ──HTTP POST──► [FastAPI ML Adapter] ──► [Vertex AI]
                                        │                  U-Net / PINN / RL
                                        │◄─── GeoJSON FeatureCollection ────┘
          │
          ▼
[Cloud SQL (PostGIS)] + [Memorystore (Redis)]
          │
          ▼  (REST polling every 5 min)
[Django REST API — Cloud Run] ──► [React Frontend — Cloud CDN]
```

The backend is a **modular Django monolith** (Cloud Run) paired with a **separate FastAPI ML Adapter** (Cloud Run) that acts as a translation layer between the data pipeline and Vertex AI model endpoints. The two halves communicate through a strict GeoJSON FeatureCollection contract — enabling the backend and ML teams to develop independently.

---

## 🛠️ Tech Stack

### Backend
- **Python 3.12** — Primary language across all backend services
- **Django 5.x + Django REST Framework** — Core API and ORM
- **GeoDjango + PostGIS** — Spatial queries and A\* routing engine
- **Celery + Celery Beat** — Async task worker + daily cron scheduler
- **FastAPI** — Lightweight ML Adapter bridging Django → Vertex AI

### Infrastructure (GCP)
- **Cloud Run** — Serverless hosting for Django REST API + FastAPI Adapter
- **Compute Engine (e2-micro)** — Persistent Celery worker + Beat scheduler
- **Cloud SQL (PostgreSQL 16 + PostGIS 3.4)** — Spatial database
- **Memorystore (Redis 7)** — Celery message broker + GeoJSON cache
- **Google Cloud Storage (GCS)** — Processed feature files and model weights
- **Vertex AI** — Managed ML model endpoints (U-Net, PINN, RL Agent)
- **Google Earth Engine (GEE)** — Free academic-tier satellite data access

### ML Models
- **U-Net** — Spatial fire risk segmentation (extends Paper 1)
- **PINN** — Physics-Informed Neural Network for fire spread
- **RL Agent (DQN/PPO)** — Dynamic step-by-step fire progression (extends Paper 2)
- **Ensemble Combiner** — Cellular Automata Rule 30 majority voting (extends Paper 3)

### Frontend
- **React 19 + Vite** — Single-page application
- **Mapbox GL JS** — Base map with 3D terrain
- **Deck.gl** — WebGL wind particle animations
- **Tailwind CSS v4** — Utility-first styling

### Local Development
- **Docker + docker-compose** — PostGIS + Redis local parity with GCP

---

## ✨ Features

- 🗺️ **Fire Risk Heatmap** — Day-ahead probability visualization on an 18,000-cell 1×1 km Bay Area grid via Deck.gl color intensity
- 🚗 **Dynamic A\* Evacuation Routing** — Computes shortest safe path to the nearest FEMA/CalOES shelter, actively avoiding HIGH\_RISK PostGIS polygons
- 🌬️ **Live Environmental Telemetry** — Animated Deck.gl wind particles, NWS Red Flag Warning overlays, vulnerability scoring
- 🤖 **Plug-and-Play ML Ensemble** — U-Net, PINN, and RL Agent results combined via weighted voting; `MOCK_INFERENCE=True` enables full dev without a trained model
- 📊 **Model Performance Dashboard** — ROC-AUC, F1, accuracy, and recall metrics surfaced via REST for frontend display
- 🔁 **Resilient Data Pipeline** — Celery exponential backoff retry (NFR-R05), 48-hour Redis staleness fallback (NFR-R04), AP architecture

---

## 🚀 Getting Started

### Prerequisites

Ensure the following are installed on your machine:

| Tool | Version | Purpose |
|---|---|---|
| Python | 3.12+ | Backend runtime |
| Docker Desktop | Latest | Runs PostGIS + Redis locally |
| Node.js | 20+ | React frontend |
| GDAL | 3.7+ | Required by GeoDjango |
| Git | Any | Version control |

> **macOS (Homebrew):** `brew install gdal python@3.12`  
> **Ubuntu:** `sudo apt-get install gdal-bin libgdal-dev python3.12`

### Installation

**1. Clone the repository:**

```bash
git clone https://github.com/<your-org>/CMPE295A-Project.git
cd CMPE295A-Project
```

**2. Set up environment variables:**

```bash
cp .env.example .env
```

Open `.env` and fill in your local values. Key variables:

```bash
# Django
SECRET_KEY=your-generated-secret-key   # See .env.example for generation command
DEBUG=True

# Database (matches docker-compose defaults)
DB_NAME=ffwai_db
DB_USER=ffwai_user
DB_PASSWORD=ffwai_password
DB_HOST=localhost
DB_PORT=5432

# Redis (matches docker-compose defaults)
REDIS_URL=redis://localhost:6379/0

# ML — keep True during Month 1 development
MOCK_INFERENCE=True
ML_ADAPTER_URL=http://localhost:8001
```

**3. Start the local infrastructure (PostGIS + Redis):**

```bash
docker compose up -d
```

Verify services are healthy:

```bash
docker compose ps
# Both `ffwai_postgres` and `ffwai_redis` should show "healthy"
```

**4. Install Python dependencies:**

```bash
cd backend
pip install -r requirements.txt
```

> **Note on GDAL:** If `pip install` fails on `GDAL`, ensure `gdal-config` is in your PATH.  
> macOS: `export PATH="/opt/homebrew/bin:$PATH"`

**5. Run Django migrations:**

```bash
python manage.py migrate
```

**6. Install frontend dependencies:**

```bash
cd ../frontend
npm install
```

### 🛑 Troubleshooting macOS GDAL Issues
Because GeoDjango heavily relies on C++ spatial libraries, macOS users (especially on Apple Silicon) often run into Homebrew linkage issues like `Library not loaded: libabsl_log_internal_check_op...dylib` or `gdal-config not found`.

**Fix 1: Re-link Homebrew dependencies**
```bash
brew update
brew upgrade
brew reinstall abseil gdal
```

**Fix 2: Explicitly set GDAL library paths in `.env`**
If Django still can't find GDAL, add the Homebrew library paths to your environment. In `backend/.env` (or your shell profile):
```bash
# For Apple Silicon (M1/M2/M3):
export GDAL_LIBRARY_PATH="/opt/homebrew/opt/gdal/lib/libgdal.dylib"
export GEOS_LIBRARY_PATH="/opt/homebrew/opt/geos/lib/libgeos_c.dylib"

# For Intel Macs:
export GDAL_LIBRARY_PATH="/usr/local/opt/gdal/lib/libgdal.dylib"
export GEOS_LIBRARY_PATH="/usr/local/opt/geos/lib/libgeos_c.dylib"
```

---

## ▶️ Running Locally

Open **three terminal windows** from the `backend/` directory:

**Terminal 1 — Django REST API:**

```bash
cd backend
python manage.py runserver
# → http://localhost:8000
```

**Terminal 2 — Celery Worker:**

```bash
cd backend
celery -A core worker --loglevel=info
```

**Terminal 3 — Celery Beat (cron scheduler):**

```bash
cd backend
celery -A core beat --loglevel=info
```

**Terminal 4 — React Frontend:**

```bash
cd frontend
npm run dev
# → http://localhost:5173
```

> **FastAPI ML Adapter** (optional for Month 1 — mock mode is on by default):  
> Run from the `ml-adapter/` directory: `uvicorn main:app --port 8001 --reload`

---

## 🧪 Usage

### Interactive API Documentation

Once Django is running, the full OpenAPI 3.0 Swagger UI is available at:

```
http://localhost:8000/api/docs/
```

### Example: Fetch the Latest Fire Risk Map

```bash
curl http://localhost:8000/api/predictions/current/
```

Response (GeoJSON FeatureCollection):

```json
{
  "type": "FeatureCollection",
  "metadata": {
    "timestamp": "2026-09-16T06:00:00Z",
    "source_model": "mock",
    "total_cells": 18000
  },
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[-122.10, 37.50], [-122.09, 37.50], [-122.09, 37.51], [-122.10, 37.51], [-122.10, 37.50]]]
      },
      "properties": {
        "grid_id": 42,
        "fire_probability": 0.85,
        "risk_label": "HIGH_RISK",
        "source_model": "mock"
      }
    }
  ]
}
```

### Example: Request an Evacuation Route

```bash
curl -X POST http://localhost:8000/api/routing/evacuate/ \
  -H "Content-Type: application/json" \
  -d '{"origin": {"lat": 37.1234, "lon": -122.4567}}'
```

### Example: Check System Health

```bash
curl http://localhost:8000/api/health/
```

```json
{
  "status": "healthy",
  "db": "ok",
  "redis": "ok",
  "mock_inference": true,
  "last_inference_timestamp": null,
  "staleness_hours": null,
  "is_stale": false
}
```

### Manually Trigger the Inference Pipeline

```bash
# From the backend/ directory with Celery worker running:
python manage.py shell -c "from harvester.tasks import trigger_daily_inference; trigger_daily_inference.delay()"
```

---

## 📡 API Reference

All endpoints are prefixed with `/api/`. Full interactive docs at `/api/docs/`.

### Predictions

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/predictions/current/` | Latest fire risk GeoJSON (from Redis cache → DB fallback) |
| `GET` | `/api/predictions/history/` | Historical inference runs. Supports `?start=`, `?end=`, `?model=` filters |

### Routing

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/routing/evacuate/` | A\* route from `{origin: {lat, lon}}` to nearest safe shelter |

### Telemetry

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/telemetry/wind/` | Wind speed/direction for Deck.gl particles (from Redis) |
| `GET` | `/api/telemetry/alerts/` | Active NWS Red Flag Warnings GeoJSON (from Redis) |
| `GET` | `/api/telemetry/shelters/` | FEMA/CalOES shelter POIs GeoJSON. Supports `?county=` filter |

### Metrics & System

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/metrics/` | Model performance metrics (ROC-AUC, F1, accuracy). Supports `?model=`, `?limit=` |
| `GET` | `/api/health/` | System health: DB, Redis, inference staleness |
| `GET` | `/api/docs/` | Swagger UI (OpenAPI 3.0) |
| `GET` | `/api/schema/` | Raw OpenAPI schema (JSON) |

### ML Adapter (FastAPI — Port 8001)

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/predict/progression` | Triggers U-Net + PINN + RL inference. Returns mock GeoJSON when `MOCK_INFERENCE=True` |
| `POST` | `/predict/ensemble` | Explicit ensemble endpoint with Cellular Automata majority voting |
| `GET` | `/health` | ML Adapter health + loaded model status |

---

## 🏗️ Project Structure

```
CMPE295A-Project/
├── backend/                    # Django monolith
│   ├── core/                   # Django project settings, URLs, Celery config
│   ├── grid/                   # BayAreaGrid, TerrainFeature, VegetationIndex models
│   ├── predictions/            # FireRiskPrediction, ModelPerformanceMetric, serializers
│   ├── harvester/              # Celery tasks: GEE data harvest + ML inference pipeline
│   ├── routing/                # A* evacuation routing engine
│   ├── telemetry/              # Wind, NWS alerts, FEMA shelter endpoints
│   ├── metrics/                # Model performance dashboard endpoint
│   ├── api/                    # Health check + legacy connection test
│   ├── manage.py
│   └── requirements.txt
├── frontend/                   # React 19 + Vite + Mapbox + Deck.gl
├── docs/
│   ├── design-doc.md           # Master system design document (source of truth)
│   ├── ml-team-interface-contract.md   # ML team integration spec
│   ├── architecture-components-guide.md
│   └── architecture-decision-record.md
├── docker-compose.yaml         # Local dev: PostGIS + Redis
├── .env.example                # Environment variable reference
└── GEMINI.md                   # AI assistant role and project context
```

---

## 📐 Architecture Decisions

Key decisions are documented in [`docs/architecture-decision-record.md`](docs/architecture-decision-record.md).

| Decision | Choice | Rationale |
|---|---|---|
| Cloud Provider | GCP | Native GEE integration; Vertex AI auto-retraining |
| Realtime Strategy | REST Polling (5 min) | Simpler MVP; WebSockets deferred |
| CAP Theorem | AP (Availability + Partition Tolerance) | Fire risk maps are better stale than unavailable |
| ML Inference Cadence | Daily Celery cron | Satellite data resolves at ~24h cadence |
| Grid Resolution | 1×1 km (18,000 cells) | Matches advisor's paper methodology |
| Demo Scenario | CZU Lightning Complex (Aug 2020) | Documented Bay Area event with historical data |

---

## 🤝 Contributing

1. Create a feature branch: `git checkout -b feat/your-feature-name`
2. Make changes and write tests in the appropriate app's `tests.py`
3. Run tests: `pytest` (from `backend/`)
4. Commit with a descriptive message following the format used in this repo (see git log for examples)
5. Open a Pull Request against `main`

> **Critical:** All commits must include a detailed message explaining what changed and why. The team may need to revert at any time — make your commits traceable.

---

## 👥 Team

| Member | Role |
|---|---|
| Earl Padron | Backend Engineering & Systems Architecture |
| Isla Shi | Frontend Development |
| Scott Kennedy | AI / Machine Learning |
| Nikhil Koganti | AI / Machine Learning |

**Advisor:** Dr. Jerry Gao — San José State University
