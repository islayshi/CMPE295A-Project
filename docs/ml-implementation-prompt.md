# Fight Fire With AI — AI/ML Model Local Integration & LLM Implementation Guide

## Overview
This document provides complete instructions and a structured prompt for the AI/ML engineering team (or an LLM coding assistant) to package the wildfire prediction models (U-Net, PINN, RL Agent, Ensemble) into a decoupled "black box" microservice. This enables seamless local testing with the backend's FastAPI ML Adapter and ensures 100% production parity with Google Cloud Vertex AI Managed Endpoints.

---

## Part 1: Architecture & Integration Topology (The "Black Box" Pattern)

The Fight Fire With AI prediction pipeline operates across three clearly separated tiers:

```
┌────────────────────────────────────────────────────────────────────────┐
│ 1. BACKEND CORE (Django & Celery) — Port 8000                          │
│    - Celery acts as an Active Fire Scout (queries NASA FIRMS)          │
│    - Computes 1 km × 1 km bounding boxes for fire anomalies           │
│    - Calls FastAPI ML Adapter via HTTP POST                            │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ POST http://localhost:8001/predict/progression
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 2. TRANSLATION LAYER (FastAPI ML Adapter) — Port 8001                  │
│    - Maintained in `ml_adapter/main.py`                                │
│    - Month 1: Serves static fixture when MOCK_INFERENCE=true           │
│    - Month 2: Routes PredictionRequest to the appropriate model service:│
│         • model_type="unet"  ──► POST http://localhost:8081/predict    │
│         • model_type="pinn"  ──► POST http://localhost:8082/predict    │
│         • model_type="ensemble" ──► Queries both & aggregates          │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
           ┌────────────────────────┴────────────────────────┐
           ▼                                                 ▼
┌─────────────────────────────────────┐   ┌─────────────────────────────────────┐
│ 3A. U-NET SERVICE — Port 8081       │   │ 3B. PINN SERVICE — Port 8082        │
│  - Standalone container/server      │   │  - Standalone container/server      │
│  - Native Ingestion for bbox & time │   │  - Physics-constrained spread      │
│  - Returns GeoJSON FeatureCollection│   │  - Returns GeoJSON FeatureCollection│
└─────────────────────────────────────┘   └─────────────────────────────────────┘
```

### Local Testing Workflow
To prevent port collisions on the developer machine, each model runs on its own assigned port:
1. **U-Net Developer Runs Inference Service (Port 8081):**
   ```bash
   cd ml_unet_service/
   python serve.py --port 8081
   # Or docker run -p 8081:8081 gcr.io/fightfirewithai/unet-service:latest
   ```
2. **PINN Developer Runs Inference Service (Port 8082):**
   ```bash
   cd ml_pinn_service/
   python serve.py --port 8082
   # Or docker run -p 8082:8082 gcr.io/fightfirewithai/pinn-service:latest
   ```
3. **Backend Triggers Prediction:** Celery triggers `POST http://localhost:8001/predict/progression` on the FastAPI ML Adapter, specifying `model_type="unet"` or `"pinn"`. The adapter forwards the request to the respective port (`8081` or `8082`).
4. **ML Service Returns GeoJSON:** The target service returns a unified GeoJSON `FeatureCollection` covering horizons (`0`, `1`, `3`, `6` hours).
5. **Backend Ingestion:** The backend ingests the GeoJSON, persists cell forecasts to PostGIS (`PredictionPolygon`), and caches the FeatureCollection in Redis (`ffwai:predictions:current`).

---

## Part 2: Structured Prompt for LLM / AI Coding Assistant

Copy and paste the prompt below into an LLM (Gemini, Claude, ChatGPT) or an automated coding agent working on the ML codebase:

```markdown
You are a Senior Machine Learning Engineer and MLOps Specialist working on the "Fight Fire With AI" wildfire risk prediction platform.

Your task is to package our wildfire prediction models (U-Net, PINN, RL progression agent, and Ensemble Combiner) into a decoupled "black-box" HTTP inference service that integrates with the project's backend FastAPI ML Adapter and deploys to Google Cloud Vertex AI.

---

### 1. ARCHITECTURAL TOPOLOGY & SERVICE BOUNDARIES
* The backend team maintains the **FastAPI ML Adapter** on port `8001` (`ml_adapter/main.py`), which orchestrates requests from Django/Celery.
* The ML team builds and maintains standalone model inference services:
  - **U-Net Service:** Runs locally on **port `8081`** (`POST http://localhost:8081/predict`)
  - **PINN Service:** Runs locally on **port `8082`** (`POST http://localhost:8082/predict`)
  - **Ensemble Combiner:** Handled by the FastAPI ML Adapter calling both endpoints or by a dedicated composite container.
* In local development, the FastAPI ML Adapter forwards prediction requests based on `model_type` to port `8081` or `8082`.
* In production on Google Cloud Platform, each container interface deploys to its own Vertex AI Managed Endpoint.
* **Native Ingestion:** Prediction requests send lightweight metadata (`bbox`, `date`, `time_horizon`). Each model service natively ingests whatever dynamic weather (NOAA) or satellite bands (GEE/FIRMS) it needs internally for the requested bounding box and timestamp. The backend does not generate `.npz` feature files.

---

### 2. STRICT CONTRACT SPECIFICATIONS

#### A. Input Request Contract (`POST /predict`)
Your endpoint must handle both raw JSON payloads (from local testing) and Vertex AI's standard `{"instances": [...]}` wrapper:

```json
{
  "bbox": [-122.9, 36.9, -121.5, 38.3],
  "time_horizon": 6,
  "model_type": "unet",
  "date": "2026-10-16",
  "additional_params": {
    "confidence_threshold": 0.2
  }
}
```

* `bbox` (`list[float]`, required): `[min_lon, min_lat, max_lon, max_lat]` in WGS-84 degrees (`EPSG:4326`). All output geometries **must be clamped within these bounds**.
* `time_horizon` (`int`, required): Forecast horizon limit in hours (`6` for standard runs). The service should generate predictions across all supported discrete intervals: `0` (current state), `1`, `3`, and `6` hours.
* `model_type` (`str`, required): `"unet"`, `"pinn"`, `"rl"`, or `"ensemble"`.
* `date` (`str`, required): ISO-8601 UTC date or timestamp string (e.g. `"2026-10-16"` or `"2026-10-16T21:00:00Z"`). If only a date is provided, default reference time is `21:00 UTC` (peak afternoon burn window in California).
* `additional_params` (`dict`, optional): Model hyperparameter overrides or threshold configurations.

#### B. Output Response Contract (`GeoJSON FeatureCollection`)
Your endpoint must respond with HTTP `200 OK` and a **Unified GeoJSON `FeatureCollection` containing all forecast horizons (0, 1, 3, 6 hours)** in a single payload. 

The frontend Mapbox time-scrubber filters by `properties.horizon_hours` on the client side; omitting horizons will break the user experience.

```json
{
  "type": "FeatureCollection",
  "metadata": {
    "timestamp": "2026-10-16T18:00:00Z",
    "source_model": "unet",
    "model_version": "1.0.0",
    "grid_resolution_km": 1.0,
    "total_cells": 18000
  },
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "Polygon",
        "coordinates": [
          [
            [-122.35, 37.78],
            [-122.34, 37.78],
            [-122.34, 37.77],
            [-122.35, 37.77],
            [-122.35, 37.78]
          ]
        ]
      },
      "properties": {
        "grid_id": 1245,
        "fire_probability": 0.95,
        "horizon_hours": 0,
        "source_model": "unet",
        "w_unet": 1.0,
        "members": 1,
        "risk_label": "ACTIVE_FIRE"
      }
    },
    {
      "type": "Feature",
      "geometry": {
        "type": "Polygon",
        "coordinates": [
          [
            [-122.34, 37.78],
            [-122.33, 37.78],
            [-122.33, 37.77],
            [-122.34, 37.77],
            [-122.34, 37.78]
          ]
        ]
      },
      "properties": {
        "grid_id": 1246,
        "fire_probability": 0.72,
        "horizon_hours": 3,
        "source_model": "unet",
        "w_unet": 0.85,
        "members": 1,
        "risk_label": "HIGH_RISK"
      }
    }
  ]
}
```

#### C. Non-Negotiable Field & Geometry Rules
1. `metadata.timestamp` (`str`, required): ISO-8601 UTC string when inference occurred.
2. `metadata.source_model` (`str`, required): One of `"unet"`, `"pinn"`, `"rl"`, `"ensemble"`.
3. `features[].properties.grid_id` (`int`, required): Positive integer. You may output your existing **California 1 km lattice IDs directly** or standard `BayAreaGrid.id`. The backend PostGIS database automatically stubs any non-existing lattice IDs on the fly.
4. `features[].properties.fire_probability` (`float`, required): Decimal between `0.0` and `1.0` (do NOT use 0–100%).
5. `features[].properties.horizon_hours` (`int`, required): Must be one of `0`, `1`, `3`, or `6`.
6. `features[].properties.source_model` (`str`, required): Matches metadata source model.
7. `features[].geometry.type`: Must be `"Polygon"`. Rings must close (first coordinate == last coordinate). Do NOT return `MultiPolygon` or `Point`.
8. Coordinate ordering: `[longitude, latitude]` in WGS-84 degrees (`EPSG:4326`). Do NOT invert to `[lat, lon]`.
9. Optional / Additional Properties: Extra fields such as `risk_label`, `w_unet`, and `members` are fully supported; the backend stores them in `ml_metrics` JSONField and passes them through.

---

### 3. REPOSITORY CONTRACT FILES TO REFERENCE
* `docs/vertex-ai-endpoint-contract.md`: Exact JSON contract, field constraints, bounding box requirements, and Mapbox UI integration details.
* `docs/ml-team-interface-contract.md`: Input feature specifications (GOES-18, VIIRS, Landsat, NOAA weather) and deployment expectations.
* `ml_adapter/main.py`: Current FastAPI adapter implementation showing routing (`/predict/progression`), Pydantic schemas, and horizon merging.
* `ml_adapter/fixtures/bay_area_fixture.json`: Live baseline fixture demonstrating the expected FeatureCollection output.
* `backend/predictions/models.py`: Django `PredictionPolygon` ORM schema showing database columns mapped from `properties`.
* `backend/harvester/tasks.py`: Celery ingestion task (`store_geojson_result()`) showing database insertion and Redis cache storage.

---

### 4. YOUR TASKS & DELIVERABLES
Generate production-ready code for the ML team:
1. `serve.py`: A high-performance FastAPI/Uvicorn server supporting configurable `--port` (default `8081` for U-Net, `8082` for PINN) exposing:
   - `GET /health`: Health check returning `{"status": "ok", "models_loaded": true}`.
   - `POST /predict`: Unpacks either raw `PredictionRequest` or `{"instances": [...]}` payload, executes inference, and returns the unified GeoJSON `FeatureCollection`.
2. `postprocessing.py`: Tensor-to-GeoJSON conversion module that:
   - Maps model raster grid indices to lattice `grid_id`s and polygon geometries.
   - Assembles predictions across all forecast horizons (`0, 1, 3, 6` hours).
   - Enforces bounding box clamping (`[-122.9, 36.9, -121.5, 38.3]`).
3. `Dockerfile`: Container definition exposing the assigned port (`8081` for U-Net, `8082` for PINN), compatible with both local testing (`docker run -p <PORT>:<PORT> ...`) and Vertex AI custom container serving.
4. `native_ingestion.py`: Internal data loader that pulls the required weather/satellite features for the given `bbox` and timestamp.
```

---

## Part 3: Architecture Clarifications & FAQ (Answers to ML Team Questions)

### Q1: `grid_id` — Can we use our California 1 km lattice IDs, or must we map to `BayAreaGrid.id`?
* **Answer:** **You can use your California 1 km lattice IDs directly.**
* **Why:** The backend's PostGIS ingestor (`backend/harvester/tasks.py`) features dynamic grid cell stubbing. If your features contain lattice IDs that do not exist in our static table, PostGIS automatically stubs and saves those grid cells using the polygon geometry provided in the feature. There is no need for your team to build a complex coordinate-snapping mapper.

### Q2: Which hour to use when the request sends only a past date (e.g., `YYYY-MM-DD`)?
* **Answer:** **Default to `21:00 UTC` (1:00 PM PST / 2:00 PM PDT).**
* **Why:** In California, early afternoon (around 1:00–2:00 PM local time) represents the peak diurnal burn window (highest daily temperatures, lowest relative humidity, and strongest afternoon winds). If the backend provides an explicit ISO-8601 timestamp (e.g. `2026-10-16T18:00:00Z`) or sets `additional_params.hour`, the model should use that hour instead.

### Q3: What should `members` count?
* **Answer:** **Treat `members` as a binary flag (1 if fire predicted, 0 if not) or omit it during standalone model runs.**
* **Why:** `members` represents the number of distinct models agreeing on a fire detection (e.g., 2 out of 3 models). For an individual standalone model (such as U-Net running alone on 8081), `members` is always 1 (or 0). The full multi-model voting count is computed during ensemble aggregation.

### Q4: Is it OK that the U-Net fetches its own inputs rather than loading daily `.npz` files?
* **Answer:** **YES, Native Ingestion is required.**
* **Why:** An hourly spread model cannot run off a daily static `.npz` file. Our updated architecture uses the **Celery Scout Pattern**: the backend queries NASA FIRMS for active fire coordinates, computes the bounding box, and hands off the bounding box to the model. The model service handles its own feature fetching natively. The backend will NOT generate `.npz` files.

### Q5: Is it OK to keep an extra `risk_label` field on each cell?
* **Answer:** **YES, extra fields like `risk_label` are completely fine.**
* **Why:** The backend ingestion engine automatically captures all additional properties (such as `risk_label`, `w_unet`, `confidence`) into the PostgreSQL `ml_metrics` JSONField, and preserves them in the cached GeoJSON payload. The frontend map renders based on continuous `fire_probability` ($0.0$ to $1.0$), so extra metadata causes zero issues.

---

## Part 4: Action Items Needed from the ML Team

1. **Local Ports:** Configure U-Net to serve on port `8081` and PINN on port `8082`.
2. **Local Runner Deliverable:** Provide `serve.py` or the Docker image name runnable locally on your assigned port.
3. **Vertex AI Credentials:** Once deployed to GCP, supply the Vertex AI Endpoint ID and grant `roles/aiplatform.user` to the Cloud Run service account.
