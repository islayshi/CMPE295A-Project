# Fight Fire With AI

A wildfire risk prediction and dynamic evacuation routing platform for the San Francisco Bay Area, powered by a U-Net / PINN / Reinforcement Learning ML ensemble and deployed on Google Cloud Platform.

**Team:** Earl Padron, Isla Shi, Scott Kennedy, Nikhil Koganti  
**Course:** CMPE 295A — Master's Project (San José State University)  
**Advisor:** Dr. Jerry Gao

---

## About The Project

Fight Fire With AI is a day-ahead fire risk planning and dynamic evacuation routing system scoped to the 9-county San Francisco Bay Area. It synthesizes satellite imagery, weather telemetry, vegetation indices, and terrain data to produce a live fire risk heatmap on a 1x1 km spatial grid, and uses that prediction to calculate safe A* evacuation routes in real time.

The system directly extends three peer-reviewed publications by Dr. Jerry Gao:
- **Malik et al., Atmosphere 2021:** Grid-based risk prediction with terrain and vegetation features.
- **Adhikari et al., IEEE CCWC 2024:** Deep Reinforcement Learning (DQN) for fire progression modeling.
- **Malik et al., IEEE CCWC 2022:** Ensemble majority voting via Cellular Automata Rule 30.

### Architecture Overview
<img width="1477" height="1452" alt="image" src="https://github.com/user-attachments/assets/1ce2a0c2-2664-49a6-9f6f-49b9a6db83c9" />


The backend is a modular Django monolith (Cloud Run) paired with a separate FastAPI ML Adapter (Cloud Run) that acts as a translation layer between the data pipeline and Vertex AI model endpoints. The two halves communicate through a strict GeoJSON FeatureCollection contract, enabling the backend and ML teams to develop independently.

---

## Tech Stack

### Backend
- **Python 3.12:** Primary language across all backend services.
- **Django 5.x + Django REST Framework:** Core API and ORM.
- **GeoDjango + PostGIS:** Spatial queries and A* routing engine.
- **Celery + Celery Beat:** Async task worker and daily cron scheduler.
- **FastAPI:** Lightweight ML Adapter bridging Django to Vertex AI.

### Infrastructure (GCP)
- **Cloud Run:** Serverless hosting for Django REST API and FastAPI Adapter.
- **Compute Engine (e2-micro):** Persistent Celery worker and Beat scheduler.
- **Cloud SQL (PostgreSQL 16 + PostGIS 3.4):** Spatial database.
- **Memorystore (Redis 7):** Celery message broker and GeoJSON cache.
- **Google Cloud Storage (GCS):** Processed feature files and model weights.
- **Vertex AI:** Managed ML model endpoints (U-Net, PINN, RL Agent).
- **Google Earth Engine (GEE):** Free academic-tier satellite data access.

### ML Models
- **U-Net:** Spatial fire risk segmentation (extends Paper 1).
- **PINN:** Physics-Informed Neural Network for fire spread.
- **RL Agent (DQN/PPO):** Dynamic step-by-step fire progression (extends Paper 2).
- **Ensemble Combiner:** Cellular Automata Rule 30 majority voting (extends Paper 3).

### Frontend
- **React 19 + Vite:** Single-page application.
- **Mapbox GL JS:** Base map with 3D terrain.
- **Deck.gl:** WebGL wind particle animations.
- **Tailwind CSS v4:** Utility-first styling.

### Local Development
- **Docker + docker-compose:** PostGIS and Redis local parity with GCP.

---

## Features

- **Fire Risk Heatmap:** Day-ahead probability visualization on an 18,000-cell 1x1 km Bay Area grid via Deck.gl color intensity.
- **Dynamic A* Evacuation Routing:** Computes shortest safe path to the nearest FEMA/CalOES shelter, actively avoiding HIGH_RISK PostGIS polygons.
- **Live Environmental Telemetry:** Animated Deck.gl wind particles, NWS Red Flag Warning overlays, vulnerability scoring.
- **Plug-and-Play ML Ensemble:** U-Net, PINN, and RL Agent results combined via weighted voting; MOCK_INFERENCE=True enables full development without a trained model.
- **Model Performance Dashboard:** ROC-AUC, F1, accuracy, and recall metrics surfaced via REST for frontend display.
- **Resilient Data Pipeline:** Celery exponential backoff retry (NFR-R05), 48-hour Redis staleness fallback (NFR-R04), AP architecture.

---

## Getting Started

### Prerequisites

Ensure the following are installed on your machine:
- **Python 3.12+:** Backend runtime.
- **Docker Desktop:** Runs the database and cache locally.
- **Node.js 20+:** React frontend.
- **GDAL 3.7+:** Required by GeoDjango.
- **Git:** Version control.

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
Open `.env` and fill in your local values. Keep `MOCK_INFERENCE=True` during early development.

**3. Start the local infrastructure (Docker):**
*Context: Docker allows us to run isolated "containers" for PostgreSQL (our database) and Redis (our caching layer) without having to manually install and configure them on your computer.*
```bash
docker compose up -d
docker compose ps
```
**Expected Output:**
```
NAME             IMAGE                    COMMAND                  SERVICE   STATUS                  PORTS
ffwai_postgres   postgis/postgis:16-3.4   "docker-entrypoint.s..." db        Up (healthy)            0.0.0.0:5432->5432/tcp
ffwai_redis      redis:7-alpine           "docker-entrypoint.s..." redis     Up (healthy)            0.0.0.0:6379->6379/tcp
```

**4. Create a virtual environment and install dependencies:**
*Context: A virtual environment isolates the Python packages used for this project so they don't conflict with other projects on your computer.*
```bash
python3.12 -m venv .venv
source .venv/bin/activate
cd backend
pip install -r requirements.txt
```

**5. Run Database Migrations:**
*Context: "Migrations" are how Django translates our Python code (the data models) into actual SQL tables in the PostgreSQL database. This command applies those changes to the database running inside your Docker container.*
```bash
python manage.py makemigrations
python manage.py migrate
```
**Expected Output:**
```
Operations to perform:
  Apply all migrations: admin, auth, contenttypes, grid, harvester, predictions, sessions, telemetry
Running migrations:
  Applying grid.0001_initial... OK
  Applying harvester.0001_initial... OK
  Applying predictions.0001_initial... OK
  Applying telemetry.0001_initial... OK
```

**6. Generate the Spatial Grid:**
*Context: This is a custom command we built to divide the San Francisco Bay Area into 1x1 kilometer squares (over 19,000 cells) and store them in the database for spatial analysis.*
```bash
python manage.py generate_grid
```
**Expected Output:**
```
  Generating grid cells...
  Progress: 19,000 / 19,344 cells (98.2%) — 3.1s elapsed
  Grid generation complete!
    Cells written : 19,344
```

**7. Load Mock Terrain Data:**
*Context: This command generates synthetic elevation, slope, and aspect data for the grid cells so we can test routing and UI rendering before connecting to the live Google Earth Engine data.*
```bash
python manage.py load_terrain --mock
```
**Expected Output:**
```
  Generating mock terrain data...
  Progress: 19,000 / 19,344 (98.2%) — 1.7s
  Mock terrain loaded!
```

**8. Install frontend dependencies:**
```bash
cd ../frontend
npm install
```

### Troubleshooting macOS GDAL Issues
Because GeoDjango relies on C++ spatial libraries, macOS users often encounter Homebrew linkage issues like `Library not loaded: libabsl_log_internal_check_op...dylib` or `gdal-config not found`.

**Fix 1: Re-link Homebrew dependencies**
```bash
brew update
brew upgrade
brew reinstall abseil re2 gdal
```

**Fix 2: Explicitly set GDAL library paths in `.env`**
If Django cannot find GDAL, add the paths to your environment. In `backend/.env`:
```bash
# For Apple Silicon (M1/M2/M3):
export GDAL_LIBRARY_PATH="/opt/homebrew/opt/gdal/lib/libgdal.dylib"
export GEOS_LIBRARY_PATH="/opt/homebrew/opt/geos/lib/libgeos_c.dylib"

# For Intel Macs:
export GDAL_LIBRARY_PATH="/usr/local/opt/gdal/lib/libgdal.dylib"
export GEOS_LIBRARY_PATH="/usr/local/opt/geos/lib/libgeos_c.dylib"
```

---

## Running Locally

Open **three terminal windows**. Ensure you are in the `backend/` directory and your virtual environment is activated (`source ../.venv/bin/activate`) in each terminal.

**Terminal 1 — Django REST API:**
```bash
cd backend
python manage.py runserver
# Expected Output: Starting development server at http://127.0.0.1:8000/
```

**Terminal 2 — Celery Worker:**
```bash
cd backend
celery -A core worker --loglevel=info
```

**Terminal 3 — React Frontend:**
```bash
cd frontend
npm run dev
# Expected Output: Local: http://localhost:5173/
```

---

## Usage

### Interactive API Documentation
Once Django is running, the full OpenAPI 3.0 Swagger UI is available at:
```
http://localhost:8000/api/docs/
```

### Example: Check System Health
Open a terminal and run:
```bash
curl http://localhost:8000/api/health/
```
**Expected Output:**
```json
{"status":"healthy","db":"ok","redis":"ok","mock_inference":true,"last_inference_timestamp":null,"staleness_hours":null,"is_stale":false}
```

### Example: Request an Evacuation Route
```bash
curl -X POST http://localhost:8000/api/routing/evacuate/ \
  -H "Content-Type: application/json" \
  -d '{"origin": {"lat": 37.1234, "lon": -122.4567}}'
```

---

## API Reference

All endpoints are prefixed with `/api/`. Full interactive docs at `/api/docs/`.

### Predictions
- `GET /api/predictions/current/`: Latest fire risk GeoJSON (from Redis cache with database fallback).
- `GET /api/predictions/history/`: Historical inference runs. Supports `?start=`, `?end=`, `?model=` filters.

### Routing
- `POST /api/routing/evacuate/`: A* route from `{origin: {lat, lon}}` to nearest safe shelter.

### Telemetry
- `GET /api/telemetry/wind/`: Wind speed and direction for Deck.gl particles.
- `GET /api/telemetry/alerts/`: Active NWS Red Flag Warnings.
- `GET /api/telemetry/shelters/`: FEMA/CalOES shelter POIs.

### Metrics & System
- `GET /api/metrics/`: Model performance metrics (ROC-AUC, F1, accuracy).
- `GET /api/health/`: System health status.
- `GET /api/docs/`: Swagger UI (OpenAPI 3.0).

---

## Project Structure

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
│   ├── manage.py
│   └── requirements.txt
├── frontend/                   # React 19 + Vite + Mapbox + Deck.gl
├── docs/                       # Project documentation
├── docker-compose.yaml         # Local dev: PostGIS + Redis
├── .env.example                # Environment variable reference
└── GEMINI.md                   # AI assistant role and project context
```

---

## Architecture Decisions

Key decisions are documented in `docs/architecture-decision-record.md`.

- **Cloud Provider:** GCP (Native GEE integration, Vertex AI auto-retraining).
- **Realtime Strategy:** REST Polling every 5 minutes (Simpler MVP, WebSockets deferred).
- **CAP Theorem:** AP (Availability + Partition Tolerance) - Fire risk maps are better stale than unavailable.
- **ML Inference Cadence:** Daily Celery cron (Satellite data resolves at approximately 24h cadence).
- **Grid Resolution:** 1x1 km for 18,000 cells (Matches advisor's paper methodology).
- **Demo Scenario:** CZU Lightning Complex, Aug 2020 (Documented Bay Area event with historical data).

---

## Contributing

1. Create a feature branch: `git checkout -b feat/your-feature-name`
2. Make changes and write tests in the appropriate app's `tests.py`.
3. Run tests: `pytest` (from `backend/`).
4. Commit with a descriptive message. All commits must include a detailed message explaining what changed and why. Traceability is critical.
5. Open a Pull Request against `main`.
