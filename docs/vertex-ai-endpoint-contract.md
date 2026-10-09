## Architectural Context & Codebase Overview
<img width="1025" height="817" alt="image" src="https://github.com/user-attachments/assets/12feea5c-3ff7-48df-96bc-3d2882412a50" />

The system is built as a series of loosely‑coupled services, each optimized for a specific responsibility. The FastAPI ML Adapter runs on Cloud Run and provides a thin, HTTP‑based façade for Vertex AI model endpoints. FastAPI was chosen for its high performance, automatic OpenAPI generation, and minimal runtime footprint, making it ideal for a stateless inference service that can scale automatically.

When a prediction request arrives, the adapter forwards a lightweight JSON payload to the appropriate Vertex AI model. The model returns a GeoJSON FeatureCollection, which the adapter hands off to a Celery worker (`store_geojson_result`). Celery gives us reliable, asynchronous processing and retries, ensuring the backend can continue ingesting new requests even if the model call experiences transient latency.

The worker persists each feature into the PostGIS‑backed `Prediction` table, enabling powerful spatial queries and future analytics. To keep the UI snappy, the full GeoJSON result is also cached in Redis with a short TTL, allowing the frontend to fetch the latest predictions without hitting the database on every map repaint. Finally, Mapbox renders the data client‑side, providing an interactive, high‑performance map experience.


**Why these choices?**
- **FastAPI + Cloud Run** gives us serverless elasticity without managing infrastructure.
- **Celery + Redis** decouples long‑running model inference from request handling, providing resilience and back‑pressure handling.
- **PostGIS** is the de‑facto standard for spatial data in PostgreSQL, giving us precise geometry indexing and the ability to join predictions to our pre‑computed 1 km grid.
- **Redis caching** eliminates unnecessary DB round‑trips for the frequently‑polled map view.
- **Mapbox** supplies a mature WebGL‑based map engine that works well with GeoJSON and supports the custom styling defined in our UI theme.

**Django `Prediction` model (`backend/predictions/models.py`)**
The `Prediction` model is the canonical representation of a fire‑risk polygon inside the backend. Each record stores:
- `grid_id` – a foreign key to the static `BayAreaGrid` table, enabling fast look‑ups and a deterministic link between a GeoJSON feature and its spatial cell.
- `horizon_hours`, `lead_time_hours`, `target_timestamp` – fields that capture the forecast horizon; the `lead_time_hours` field was added in a later migration to support models that produce non‑hourly steps.
- `fire_probability` – a float in the range `[0, 1]` used for heat‑map intensity.
- `ml_metrics` – a JSON column capturing model‑specific metrics such as `w_unet` and `members` for downstream analytics.
- `timestamp` – when the prediction was ingested.

These fields were chosen to balance the needs of the UI (quick access to horizon and risk) and the analytics pipeline (preserving raw model metrics).

**1 km × 1 km grid (`core/models.py` – `BayAreaGrid`)**
We pre‑compute a uniform grid covering the San Francisco Bay Area, with each cell roughly 1 km². Storing this grid in the database allows us to join incoming GeoJSON polygons to a deterministic `grid_id` without performing expensive on‑the‑fly rasterisation. This design greatly reduces query complexity and improves performance when the UI filters by geography or when we aggregate statistics across cells.

**Migrations**
- `0001_initial.py` establishes the foundational tables (`Prediction` and `BayAreaGrid`).
- `0002_add_lead_time.py` introduced `lead_time_hours` and `target_timestamp` after the U‑Net model was extended to produce 3‑hour and 6‑hour forecasts. Splitting these concerns into a separate migration kept the original schema stable for earlier releases while still supporting new horizon options.

**GeoJSON handling code**
- `ml_adapter/main.py` normalises raw fixture files, merges separate horizon files into a single FeatureCollection, and injects required `properties` keys. This ensures the downstream pipeline receives a consistent shape regardless of how the ML team structures their output.
- `backend/harvester/tasks.py` implements `store_geojson_result`, which validates the presence of required property keys, writes each feature into `Prediction`, and updates the Redis cache.
- `backend/predictions/views.py` exposes a lightweight endpoint that serves the cached GeoJSON to the frontend, falling back to an empty collection if the cache is empty.
- The frontend components (`Dashboard.jsx` and `MapCanvas.jsx`) read the `horizon_hours` property to drive the time‑scrubber UI and apply Mapbox style expressions based on `fire_probability`.

**Constraints**
- **Bounding box**: All predictions are clamped to the Bay Area (`[-122.9, 36.9, -121.5, 38.3]`). This prevents out‑of‑region data (e.g., Southern California fixtures) from leaking into the UI and simplifies spatial indexing.
- **Supported horizons**: The current U‑Net model only provides forecasts for 0, 1, 3, and 6 hours. The time scrubber therefore snaps to these discrete steps, and the contract enforces `horizon_hours` to be one of these values.
- **No async gRPC**: We intentionally avoid gRPC async APIs to keep the stack simple and to rely on well‑understood HTTP semantics within Django and FastAPI.
- **Contract adherence**: Every component assumes the JSON schema defined later in this document; deviating from it would cause validation failures, broken maps, or missed cache updates.

---

# Vertex AI Endpoint Contract

## Overview
This document defines the **exact JSON contract** between the FastAPI ML Adapter (hosted on Cloud Run) and the Vertex AI model endpoints. The Backend (Django/Celery) and the Mapbox‑based UI rely on this contract to ingest predictions, store them safely, and render them without runtime errors.

---

## 1. PredictionRequest Payload (sent **to** Vertex AI)
The FastAPI adapter forwards a thin payload that tells the model which area and time‑horizon to predict.

| Field | Type | Required? | Description |
|------|------|-----------|-------------|
| `bbox` | `float[]` (4) | ✅ | `[west, south, east, north]` in WGS‑84 degrees. Must exactly match the Bay Area bounding box used by the Django pipeline. |
| `time_horizon` | `int` | ✅ | Hours from the start of the prediction (e.g., `0`, `1`, `3`, `6`). |
| `model_type` | `string` | ✅ | One of `"unet"`, `"pinn"`, `"rl"`. Determines which Vertex AI endpoint to invoke. |
| `date` | `string` (ISO‑8601) | ✅ | The **reference date** for the forecast (UTC). |
| `additional_params` | `object` | ❌ | Optional key‑value pairs for future extensions (e.g., custom thresholds). |

### Example JSON
```json
{
  "bbox": [-122.9, 36.9, -121.5, 38.3],
  "time_horizon": 3,
  "model_type": "unet",
  "date": "2026-10-06",
  "additional_params": {
    "confidence_threshold": 0.2
  }
}
```

---

## 2. Feature Properties – **Mapbox Standard**
Every GeoJSON **Feature** must contain a **`properties`** object. The UI and Celery ingest code assume the following keys exist **inside** `properties`:

| Key | Type | Allowed Values / Range | Why it matters |
|-----|------|------------------------|----------------|
| `fire_probability` | `float` | `0.0` – `1.0` | Used for heat‑map intensity and stored in Django `FloatField`. |
| `grid_id` | `int` | Positive integer | Primary lookup key for the `BayAreaGrid` FK in Django. |
| `horizon_hours` | `int` | `0`, `1`, `3`, `6` | Enables the time‑scrubber; the UI filters on this field. |
| `w_unet` | `float` | Any (model‑specific metric) | Captured for analytics; stored in `ml_metrics` JSONField. |
| `members` | `int` | Positive integer | Likewise stored for debugging and model‑performance dashboards. |

### Full Feature Example (nested properties)
```json
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
    "fire_probability": 0.73,
    "grid_id": 1245,
    "horizon_hours": 3,
    "w_unet": 0.12,
    "members": 8
  }
}
```

---

## 3. Unified FeatureCollection (single response)
The Vertex AI endpoint **must** return **one** GeoJSON `FeatureCollection` that contains **all** requested horizons. The backend stores this payload directly in PostGIS and caches it in Redis; the UI consumes it in a single request.

### Sample Unified Response (horizons 0, 1, 3, 6)
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {"type": "Polygon", "coordinates": [[[ -122.36, 37.78 ], [ -122.35, 37.78 ], [ -122.35, 37.77 ], [ -122.36, 37.77 ], [ -122.36, 37.78 ]]]},
      "properties": {"fire_probability": 0.95, "grid_id": 1120, "horizon_hours": 0, "w_unet": 0.04, "members": 12}
    },
    {
      "type": "Feature",
      "geometry": {"type": "Polygon", "coordinates": [[[ -122.35, 37.78 ], [ -122.34, 37.78 ], [ -122.34, 37.77 ], [ -122.35, 37.77 ], [ -122.35, 37.78 ]]]},
      "properties": {"fire_probability": 0.73, "grid_id": 1245, "horizon_hours": 1, "w_unet": 0.12, "members": 8}
    },
    {
      "type": "Feature",
      "geometry": {"type": "Polygon", "coordinates": [[[ -122.34, 37.78 ], [ -122.33, 37.78 ], [ -122.33, 37.77 ], [ -122.34, 37.77 ], [ -122.34, 37.78 ]]]},
      "properties": {"fire_probability": 0.48, "grid_id": 1370, "horizon_hours": 3, "w_unet": 0.18, "members": 5}
    },
    {
      "type": "Feature",
      "geometry": {"type": "Polygon", "coordinates": [[[ -122.33, 37.78 ], [ -122.32, 37.78 ], [ -122.32, 37.77 ], [ -122.33, 37.77 ], [ -122.33, 37.78 ]]]},
      "properties": {"fire_probability": 0.22, "grid_id": 1498, "horizon_hours": 6, "w_unet": 0.07, "members": 3}
    }
  ]
}
```

---

## 4. Bounding‑Box Enforcement
The FastAPI adapter includes the `bbox` from the **PredictionRequest** in the request body to the Vertex AI model. The model **must** clamp all output geometries to this box. If a polygon lies outside, it is either clipped or omitted.

### Why it matters
* **Celery Tasks** – The `store_geojson_result` task assumes every geometry intersects the Bay Area. Out‑of‑bounds polygons cause spatial index errors and waste storage.
* **Django Models** – `GeoDjango` validates geometries against the SRID‑4326 grid; foreign polygons raise `GEOSException` and abort the transaction.
* **Mapbox UI** – The front‑end time scrubber and legend assume the data fits within the map view; stray polygons would render off‑screen and break the user experience.

---

## 5. Summary Table of Required Keys
| Section | Required Keys | Location |
|---------|----------------|----------|
| **PredictionRequest** | `bbox`, `time_horizon`, `model_type`, `date` | Request body sent to Vertex AI |
| **Feature Properties** | `fire_probability`, `grid_id`, `horizon_hours`, `w_unet`, `members` | Inside each `Feature.properties` |
| **FeatureCollection** | `type="FeatureCollection"`, `features` array | Top‑level response |
| **Bounding‑Box Enforcement** | Implicit – model must respect `bbox` | Model output logic |

---

## 6. Impact on System Components
* **Celery Harvester (`store_geojson_result`)** – Parses the unified FeatureCollection, validates the presence of all required keys, and writes each feature into the `Prediction` model. Missing keys will raise a `ValidationError` and trigger a retry.
* **Django ORM** – The `Prediction` model maps directly to the keys above. `fire_probability` and `grid_id` are numeric fields. The `ml_metrics` JSONField stores the extra keys (`w_unet`, `members`).
* **Mapbox UI** – The front‑end reads the cached GeoJSON from `/api/predictions/current/`. It uses `properties.horizon_hours` for the time‑scrubber, `fire_probability` for colour mapping and opacity. The nested `properties` object is required for the Mapbox `expression` based style layers.

---

## 7. Versioning & Compatibility
* This contract corresponds to **Month 2** integration. Existing mock‑mode fixtures (`MOCK_INFERENCE=true`) already follow the same structure, so swapping to real Vertex AI endpoints is a **drop‑in** operation.
* Future extensions should be added under `additional_params` in the request payload and under a new namespace inside `properties` (e.g., `properties.metrics.<new_key>`). The contract version is tracked in the FastAPI header `X-Contract-Version: 2026-10-05`.

---

*Copy‑paste the sections above into your integration code. The contract is deliberately strict to avoid downstream crashes across Celery, Django, and the Mapbox UI.*
