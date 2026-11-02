# Fight Fire With AI

A wildfire risk prediction and alert platform for the San Francisco Bay Area, powered by a U-Net / PINN / Reinforcement Learning ML ensemble and deployed on Google Cloud Platform.

**Team:** Earl Padron, Isla Shi, Scott Kennedy, Nikhil Koganti  
**Course:** CMPE 295A — Master's Project (San José State University)  
**Advisor:** Dr. Jerry Gao

---

## About The Project

Fight Fire With AI is a day-ahead fire risk planning and zone-warning system scoped to the 9-county San Francisco Bay Area. It synthesizes satellite imagery, weather telemetry, vegetation indices, and terrain data to produce a live fire risk heatmap on a 1x1 km spatial grid, providing zone-based alerts and emergency shelter POI telemetry in real time.

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
- **GeoDjango + PostGIS:** Spatial queries and spatial indexing.
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

- **Fire Risk Heatmap and Progression** Day-ahead probability visualization on an 18,000-cell 1x1 km Bay Area grid via Deck.gl color intensity.
- **Live Environmental Telemetry:** Animated Deck.gl wind particles, NWS Red Flag Warning overlays.
- **Plug-and-Play ML Ensemble:** U-Net, PINN, and RL Agent results combined via weighted voting; MOCK_INFERENCE=True enables full development without a trained model.
- **Model Performance Dashboard:** ROC-AUC, F1, accuracy, and recall metrics surfaced via REST for frontend display.
- **Data Dashboard:** (Pending) 
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

> **macOS (Homebrew):** `brew install gdal python3`
> **Ubuntu:** `sudo apt-get install gdal-bin libgdal-dev python3`

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
*Context: Docker allows us to run isolated containers for PostgreSQL (PostGIS spatial database), Redis (caching and task queue), and the containerized U-Net and PINN machine learning microservices.*
```bash
docker compose up -d
docker compose ps
```
**Expected Output:**
```
NAME                 IMAGE                           COMMAND                  SERVICE        STATUS                  PORTS
ffwai_postgres       postgis/postgis:16-3.4          "docker-entrypoint.s..." db             Up (healthy)            0.0.0.0:5432->5432/tcp
ffwai_redis          redis:7-alpine                  "docker-entrypoint.s..." redis          Up (healthy)            0.0.0.0:6379->6379/tcp
ffwai_unet_service   cmpe295a-project-unet-service   "/bin/sh -c 'exec uv..." unet-service   Up                      0.0.0.0:8081->8081/tcp
ffwai_pinn_service   cmpe295a-project-pinn-service   "sh -c 'python serve..." pinn-service   Up (healthy)            0.0.0.0:8082->8082/tcp
```

**4. Create a virtual environment and install dependencies:**
*Context: We have provided an automated script that creates a Python virtual environment and installs all dependencies for the backend, ML adapter, and frontend.*
```bash
./scripts/install.sh
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

We have provided automated scripts within [`scripts/`](file:///Users/earlpadron/Desktop/Spring%202026%20Courses/CMPE%20295A/CMPE295A-Project/scripts/) to automate the entire stack (Docker microservices, telemetry cache warmup, Celery task queue, FastAPI ML Adapter, Django REST backend, and Vite React UI) in one click.

### Developer Scripts Overview

* **[`scripts/seed_cache.py`](file:///Users/earlpadron/Desktop/Spring%202026%20Courses/CMPE%20295A/CMPE295A-Project/scripts/seed_cache.py):**
  * Fetches live wind telemetry from Open-Meteo and builds the 1,600-point vector grid in Redis (`ffwai:wind_current`).
  * Fetches live AQI stations from AirNow into Redis (`ffwai:aqi_data`).
  * Runs the NASA FIRMS VIIRS 375m Active Fire Scout (`trigger_active_inference`).
  * Dispatches live inference to the containerized U-Net (port 8081) and PINN (port 8082) via the ML Adapter, pre-populating fire prediction polygons across all 5 horizons (`0h`, `+1h`, `+3h`, `+6h`, and `24h`) for **U-Net**, **PINN**, and **Ensemble**.
* **[`scripts/run_local.sh`](file:///Users/earlpadron/Desktop/Spring%202026%20Courses/CMPE%20295A/CMPE295A-Project/scripts/run_local.sh):**
  * Starts Docker containers (`docker compose up -d` for PostGIS, Redis, U-Net, and PINN).
  * Runs `scripts/seed_cache.py` so the cache and PostGIS database are immediately warm on launch.
  * Spawns all 5 components in dedicated Terminal windows:
    * **Terminal 1:** Django REST Backend (`python manage.py runserver 8000`)
    * **Terminal 2:** Celery Worker (`celery -A core worker -l info --pool=solo`)
    * **Terminal 3:** Celery Beat (`celery -A core beat -l info`)
    * **Terminal 4:** FastAPI ML Adapter in live mode (`MOCK_INFERENCE=false uvicorn ml_adapter.main:app --port 8001`)
    * **Terminal 5:** Vite React Frontend (`npm run dev`)
* **[`scripts/stop_local.sh`](file:///Users/earlpadron/Desktop/Spring%202026%20Courses/CMPE%20295A/CMPE295A-Project/scripts/stop_local.sh):**
  * Cleanly terminates all processes running on ports 8000, 8001, 5173, shuts down Celery workers, and stops the Docker containers.

---

### Option A: One-Command Automated Launch (Recommended)

In your terminal at the project root, run:

```bash
./scripts/run_local.sh
```

This starts all Docker containers, runs `seed_cache.py` to warm up Redis with live telemetry and predictions, and opens the 5 terminal tabs automatically.

To shut down all services and containers when done:
```bash
./scripts/stop_local.sh
```

---

### Option B: Manual Terminal Execution

If you prefer to start each service manually in separate terminal windows:

```bash
# 1. Start Docker Containers (Postgres, Redis, U-Net, PINN)
docker compose up -d

# 2. Warm up Redis cache & PostGIS predictions
./.venv/bin/python scripts/seed_cache.py

# 3. Terminal 1: Django Backend (port 8000)
source .venv/bin/activate && cd backend && python manage.py runserver 8000

# 4. Terminal 2: Celery Worker
source .venv/bin/activate && export PYTHONPATH=backend:ml_adapter:ml_services/unet_service && cd backend && celery -A core worker -l info --pool=solo

# 5. Terminal 3: Celery Beat Scheduler
source .venv/bin/activate && cd backend && celery -A core beat -l info

# 6. Terminal 4: FastAPI ML Adapter (Live Docker mode)
source .venv/bin/activate && export PYTHONPATH=backend:ml_adapter:ml_services/unet_service && MOCK_INFERENCE=false uvicorn ml_adapter.main:app --port 8001 --reload

# 7. Terminal 5: Vite React Frontend (port 5173)
cd frontend && npm run dev
```

---

### Testing Live Satellite Mode vs. Mock Demonstration Mode

You can control whether the application runs in **Live Satellite Mode** or **Mock Demonstration Mode** via the `MOCK_INFERENCE` setting in `.env`:

* **Live Satellite Mode (`MOCK_INFERENCE=False`)**:
  * Real-time NASA FIRMS VIIRS 375m scout + NOAA GOES-18 satellite feeds from AWS S3.
  * Dispatches to live Docker containers (`ffwai_unet_service` on 8081, `ffwai_pinn_service` on 8082).
  * If no natural wildfires are active in the Bay Area today, the map displays zero fire polygons (clean satellite conditions).
* **Mock Demonstration Mode (`MOCK_INFERENCE=True`)**:
  * Serves calibrated historical wildfire spread fixtures (Santa Cruz Mountains) across all 5 horizons (`0h`, `+1h`, `+3h`, `+6h`, `+24h`).
  * Used for frontend UI/UX evaluation and demonstration of the Model Selector (U-Net vs. PINN vs. Ensemble) without waiting for real-world fire events.
  * To activate: set `MOCK_INFERENCE=True` in `.env` and re-run `./.venv/bin/python scripts/seed_cache.py`.


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

---

## API Reference

All endpoints are prefixed with `/api/`. Full interactive docs at `/api/docs/`.

### Predictions
- `GET /api/predictions/current/`: Latest fire risk GeoJSON (from Redis cache with database fallback).
- `GET /api/predictions/history/`: Historical inference runs. Supports `?start=`, `?end=`, `?model=` filters.

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
│   ├── grid/                   # BayAreaGrid, VegetationIndex models
│   ├── predictions/            # FireRiskPrediction, ModelPerformanceMetric, serializers
│   ├── harvester/              # Celery tasks: GEE data harvest + ML inference pipeline
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
