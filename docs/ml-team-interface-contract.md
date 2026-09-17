# Fight Fire With AI — ML Team Interface Contract

> **Author:** Backend Engineering Team (Earl Padron)  
> **Last Updated:** September 2026  
> **Audience:** AI/ML Team Members  
> **Purpose:** This document defines the strict integration boundaries between the Backend (Wildfire Cloud Services) and the ML team (Machine Learning Cloud Services). If both teams adhere to these contracts, we can build and test independently through Month 1 and integrate cleanly in Week 5-6.

---

## Overview: How the Two Sides Connect

The system architecture is cleanly split into two GCP zones:

```
┌─────────────────────────────────────────────────────────────┐
│                 WILDFIRE CLOUD SERVICES (Backend)            │
│                                                             │
│  External APIs ──► Celery Harvester ──► Django REST APIs    │
│                          │                    │             │
│                     Memorystore           Cloud SQL         │
│                      (Redis)            (PostGIS)           │
└──────────────────────────┼──────────────────────────────────┘
                           │  HTTP POST (feature payload)
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              MACHINE LEARNING CLOUD SERVICES (ML Team)       │
│                                                             │
│          FastAPI ML Adapter ──► Vertex AI Endpoints         │
│                                   (U-Net, PINN, RL)         │
│                          │                                  │
│               GCS Bucket (model weights, features)          │
└─────────────────────────────────────────────────────────────┘
```

The **only communication channel** between these two zones is:
1. **Inbound (Backend → ML):** A daily HTTP POST from Celery to the FastAPI ML Adapter carrying harvested feature data.
2. **Outbound (ML → Backend):** A GeoJSON FeatureCollection HTTP response returned by the FastAPI ML Adapter.

---

## Contract 1: Input Data — What the Backend Provides

### 1.1 What We Harvest Daily (Backend's Responsibility)

The Celery harvester runs daily and will produce the following data layers. These are collected from Google Earth Engine and other public APIs:

| Data Source | GEE Collection ID / API | Spatial Resolution | Temporal | Feature(s) |
|---|---|---|---|---|
| **GOES-18 Fire Detection** | `NOAA/GOES/18/FDCC` | ~2 km | Every 5 min → daily composite | Fire mask, radiative power |
| **GOES-18 Cloud/Moisture** | `NOAA/GOES/18/MCMIPC` | ~2 km | Daily composite | Band values (Cloud Top Temp) |
| **VIIRS Hotspots** | `NASA/VIIRS/002/VNP09GA` | 375 m | 12-24 hr | Surface reflectance, active fire |
| **Landsat 8/9 Vegetation** | `LANDSAT/LC09/C02/T1_L2` | 30 m | ~8-16 days | NDVI, EVI, NDWI |
| **USGS DEM (static)** | Downloaded once → PostGIS | 10 m | Static | Elevation, slope, aspect, hillshade |
| **NOAA / OpenWeather** | REST API | Point data | Daily | Wind speed, direction, temperature, humidity |
| **NWS Red Flag Warnings** | NWS Alerts API | Polygon | On-event | Active warning zone geometry |

### 1.2 What You Need to Tell Us (REQUIRED — Action Item for ML Team)

> ⚠️ **IMPORTANT:** The backend cannot finalize the Celery harvester data pipeline without this information. Please provide it as soon as possible so we can write the `fetch_*` and `format_features()` functions.

We need the ML team to specify **exactly** how the harvested data should be formatted before it is sent to the FastAPI adapter. Specifically:

1. **Feature Tensor Shape:** What dimensions does each model expect?
   - Example: `np.ndarray` of shape `(H, W, C)` where `H=64`, `W=64`, `C=12` channels.
   - Or: A dictionary of named numpy arrays keyed by feature name.

2. **Exact Feature Set & Order:** Which features does each model need, and in what channel order?
   - Example: `[NDVI, EVI, elevation, slope, wind_speed, wind_dir, humidity, goes18_fire_mask, ...]`

3. **Normalization & Preprocessing:** Should the backend normalize values before sending?
   - Example: `elevation` normalized to `[0, 1]` using Bay Area min/max.
   - Example: Wind direction in degrees (0–360) vs. sin/cos encoded.

4. **Grid Alignment:** All backend data will be projected to the **1×1 km Bay Area grid** (18,000 cells, SRID=4326, centroid-based). Can your models accept this grid natively, or do they require a different CRS or resolution?

5. **Time Window:** Does the model need a single timestep or a temporal sequence?
   - Example: U-Net might need a single daily snapshot.
   - Example: RL agent might need the last `T=7` days as a temporal sequence.

### 1.3 How Data Is Delivered to the ML Team (The Handoff Mechanism)

Once the feature format is agreed upon, the backend will:

1. **Run the Celery harvester daily** to collect and process all data layers.
2. **Export a formatted `.npz` file** (or structured GCS-compatible format) per inference run.
3. **Upload it to a shared GCS bucket**, e.g., `gs://fightfirewai-features/daily/YYYY-MM-DD.npz`.
4. **Trigger the FastAPI ML Adapter** via HTTP POST with a reference to the uploaded file (or the payload inline if small enough).

**For Model Training (Month 1):** The ML team can access historical processed `.npz` files from GCS to train their U-Net, PINN, and RL models independently. You should not need the backend running to train.

**For Inference (Month 2):** The FastAPI ML Adapter will call your Vertex AI endpoints with the live daily feature payload.

---

## Contract 2: Model Hosting — Deployment Requirements

### 2.1 Your Deployment Responsibility

The ML team is responsible for:

1. **Training** the U-Net, PINN, and RL models using the feature data provided in GCS.
2. **Registering** each trained model in the **Vertex AI Model Registry** (GCP project: `fight-fire-with-ai`).
3. **Deploying** each model as a **Vertex AI managed endpoint** (online prediction endpoint).
4. **Providing** the backend team with the Endpoint IDs and required IAM roles so the FastAPI adapter can invoke them.

### 2.2 What You Need to Send the Backend Team (REQUIRED)

Once your models are deployed, please provide:

```
U-Net Endpoint:
  Vertex AI Endpoint ID: projects/XXXXX/locations/us-central1/endpoints/XXXXXXXX
  Endpoint name: unet-fire-risk-v1

PINN Endpoint:
  Vertex AI Endpoint ID: projects/XXXXX/locations/us-central1/endpoints/XXXXXXXX
  Endpoint name: pinn-fire-spread-v1

RL Agent Endpoint:
  Vertex AI Endpoint ID: projects/XXXXX/locations/us-central1/endpoints/XXXXXXXX
  Endpoint name: rl-progression-v1

IAM: Grant the FastAPI Cloud Run service account the role:
  - roles/aiplatform.user
  - On the GCP project or on each endpoint resource
```

### 2.3 Model Architecture Guidance (From Advisor's Research Papers)

The following model selections are based directly on the three advisor papers. You are not required to use these exact architectures, but the functionality must match.

| Model | Architecture Guidance | Paper Reference |
|---|---|---|
| **U-Net** | Spatial segmentation on 1×1 km grid. 12+ input channels (terrain, vegetation, weather). Weighted BCE loss with `fire_weight=20` to handle class imbalance. Output: fire probability mask per cell. | Extends Malik et al., *Atmosphere* 2021 |
| **PINN** | Physics-Informed Neural Network for fire spread. Encodes physical constraints (wind-driven spread, terrain slope) into the loss function. Output: spread probability per cell step. | Novel contribution |
| **RL Agent (DQN/PPO)** | Dynamic fire progression via Deep Reinforcement Learning. State: current fire mask + environmental conditions. Action: spread to adjacent cells. Output: step-by-step progression probabilities. DQN+MLP achieved 85.87% in Paper 2. PPO recommended for stability. | Directly extends Adhikari et al., *IEEE CCWC* 2024 |
| **Ensemble Combiner** | Majority voting or weighted probability averaging across U-Net, PINN, and RL outputs. | Extends Malik et al., *IEEE CCWC* 2022 (Cellular Automata Rule 30 majority voting) |

> **GOES-18 Super-Resolution (Optional Stretch Goal):** The advisor suggested pairing low-resolution GOES-18 imagery (2 km) with high-resolution VIIRS data (375 m) for super-resolution training. This is an ML team discretionary task and is NOT required for the MVP.

---

## Contract 3: Output — The Strict GeoJSON FeatureCollection Spec

### 3.1 The Non-Negotiable Output Format

> ⚠️ **CRITICAL:** The backend's PostGIS database and Django models are built to accept *exactly* this format. Any deviation will break ingestion. The ML models themselves output tensors — it is the FastAPI ML Adapter's responsibility to convert those tensors into this format.

**Every response from the FastAPI ML Adapter must be a valid GeoJSON `FeatureCollection`:**

```json
{
  "type": "FeatureCollection",
  "metadata": {
    "timestamp": "2026-08-28T20:00:00Z",
    "source_model": "ensemble",
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
            [-122.10, 38.50],
            [-122.09, 38.50],
            [-122.09, 38.51],
            [-122.10, 38.51],
            [-122.10, 38.50]
          ]
        ]
      },
      "properties": {
        "grid_id": 25,
        "fire_probability": 0.85,
        "risk_label": "HIGH_RISK",
        "source_model": "ensemble"
      }
    }
  ]
}
```

### 3.2 Field Specification (Strict Types)

#### `metadata` object (top-level):

| Field | Type | Required | Description |
|---|---|---|---|
| `timestamp` | `string` (ISO 8601 UTC) | YES | Datetime this inference was run. |
| `source_model` | `string` | YES | `"unet"`, `"pinn"`, `"rl"`, `"ensemble"`, or `"mock"`. |
| `model_version` | `string` | Recommended | Semantic version of the model used. |
| `grid_resolution_km` | `float` | Recommended | Always `1.0` for MVP. |
| `total_cells` | `int` | Recommended | Number of features in the collection. |

#### Each `Feature` in `features[]`:

| Field | Type | Required | Constraints |
|---|---|---|---|
| `geometry.type` | `string` | YES | Must be `"Polygon"`. NOT `"MultiPolygon"` or `"Point"`. |
| `geometry.coordinates` | `array` | YES | Ring of `[lon, lat]` pairs (NOT lat/lon). Must close (first = last). SRID: 4326. |
| `properties.grid_id` | `integer` | YES | The `BayAreaGrid.id` primary key from PostGIS. Backend will provide a grid lookup CSV. |
| `properties.fire_probability` | `float` | YES | Range: `0.0` to `1.0`. Do NOT use percentages. |
| `properties.risk_label` | `string` | YES | Exactly: `"HIGH_RISK"`, `"MEDIUM_RISK"`, or `"LOW_RISK"`. |
| `properties.source_model` | `string` | YES | Same as metadata source_model field. |

### 3.3 Risk Label Thresholds

| Probability Range | `risk_label` |
|---|---|
| `>= 0.70` | `"HIGH_RISK"` |
| `0.40 – 0.69` | `"MEDIUM_RISK"` |
| `< 0.40` | `"LOW_RISK"` |

### 3.4 Common Mistakes — Do NOT Return These

| ❌ Do NOT return | ✅ Return instead |
|---|---|
| Raw `numpy` array or tensor | GeoJSON FeatureCollection |
| Matplotlib / PNG image | GeoJSON FeatureCollection |
| Flat list of probabilities | GeoJSON with `grid_id` mapping per feature |
| `MultiPolygon` geometry | `Polygon` geometry (one Feature per grid cell) |
| Coordinates as `[lat, lon]` | Coordinates as `[lon, lat]` (GeoJSON standard) |
| Probabilities as 0–100 | Probabilities as 0.0–1.0 |

---

## Demo Scenario: CZU Lightning Complex (August 2020)

For the defense presentation, the backend will preload historical data for the **CZU Lightning Complex fire** (Santa Cruz Mountains — August 17–22, 2020).

**What the backend provides for training/validation:**
- Historical GOES-18, VIIRS, Landsat data for August 2020 formatted to spec and uploaded to GCS.
- Historical CAL FIRE FRAP perimeter data for ground truth validation.
- A grid cell lookup CSV mapping `grid_id` → lat/lon bounds for the Santa Cruz Mountains area.

**What the ML team delivers for the demo:**
- A trained model producing meaningful fire probability values for the CZU area.
- Validation metrics (ROC-AUC, F1, precision, recall) that the backend will store in the `ModelPerformanceMetric` table and display on the frontend Performance Dashboard via `GET /api/metrics/`.

---

## Collaboration Timeline

| Timeline | Backend (Earl) | ML Team |
|---|---|---|
| **Now → Week 2** | Scaffolding Django, Celery, Docker. Delivering mock GeoJSON. | **Reply with:** feature tensor shape, feature names/order, normalization requirements. |
| **Week 2–4** | Celery harvesters live. Historical `.npz` files uploaded to GCS. | Begin model training using GCS historical data. |
| **Week 4–5** | Frontend MVP running against mock data. End-to-end routing working. | Deploy models to Vertex AI. Send Endpoint IDs to backend. |
| **Week 5–6** | Swap mock → real Vertex AI invocations in FastAPI. Integration testing. | Support integration, fix any output format issues. |
| **Week 7** | Full ensemble pipeline validated. Defense demo rehearsal. | Provide final metrics for Performance Dashboard. |

---

## FAQ

**Q: Do we write the FastAPI code?**  
A: The backend has scaffolded the FastAPI adapter with mock mode. The ML team is responsible for the `invoke_vertex_ai()` function inside the adapter and the tensor-to-GeoJSON conversion logic. We will collaborate during Week 5-6.

**Q: What if a model isn't ready in time?**  
A: The system has graceful fallback. If only U-Net is ready, it uses that and marks `source_model="unet"`. PINN and RL are optional — minimum viable demo requires U-Net working.

**Q: What if we train on Google Colab instead of Vertex AI?**  
A: Training location is entirely your choice. We only need the **deployed Vertex AI endpoint** for inference. Upload your trained weights to the Vertex AI Model Registry after training wherever you like.

**Q: What coordinate reference system should we use?**  
A: All geometry must be **WGS84 (SRID 4326)**. Do not use projected CRS (e.g., UTM) in the GeoJSON output.

**Q: Will you provide a grid lookup table?**  
A: Yes. The backend will export a CSV from `BayAreaGrid` mapping: `grid_id, min_lon, min_lat, max_lon, max_lat, centroid_lon, centroid_lat`. This lets you map your grid cell predictions to the correct `grid_id` for the output JSON.

---

## Contact & Reference Documents

- **Backend (Earl Padron):** Slack / GitHub Issues on `CMPE295A-Project` repo
- **Design Document:** [`docs/design-doc.md`](./design-doc.md)
- **Architecture Components Guide:** [`docs/architecture-components-guide.md`](./architecture-components-guide.md)
