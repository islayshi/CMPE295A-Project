# 📄 Fight Fire With AI: Master System Design Document (Bay Area Scope MVP)

## Introduction 
This document describes the design and implementation of the Master System Architecture and Frontend Minimum Viable Product (MVP) for **Fight Fire With AI**. Designed specifically for the San Francisco Bay Area, Fight Fire With AI is a day-ahead fire risk planning and zone-warning platform that synthesizes crucial environmental factors — weather, vegetation, terrain, and satellite imagery — to provide predictive fire risk mapping and telemetry guidance.

This project directly extends the wildfire prediction research established by Dr. Jerry Gao and collaborators across three key publications: grid-based risk prediction using Combined Random Forest models (Malik et al., *Atmosphere* 2021), wildfire progression modeling using Deep Reinforcement Learning (Adhikari et al., *IEEE CCWC* 2024), and ensemble-based risk prediction and detection using Cellular Automata majority voting (Malik et al., *IEEE CCWC* 2022). Fight Fire With AI builds upon these foundations by integrating U-Net spatial segmentation, Physics-Informed Neural Networks (PINN), and Reinforcement Learning (RL) into a unified ML ensemble, served through a cloud-native platform on **Google Cloud Platform (GCP)** with automated data harvesting and real-time visualization.

The frontend prototype serves as an interactive showcase of these capabilities, enabling users to visualize day-ahead fire risk zones on a 1×1 km grid heatmap, inspect emergency shelter POIs and zone-based warnings, and monitor live environmental telemetry (wind patterns, NWS Red Flag Warnings).

## 1. System Architecture: The Python & Django Monolith + Python Inference Engine

The system utilizes a Modular Monolith architecture to minimize deployment overhead while maintaining strict separation of concerns. The system is strictly scoped to the 9-county **San Francisco Bay Area** bounding box using a 1km x 1km spatial grid. The system is deployed on **Google Cloud Platform (GCP)** to leverage native Google Earth Engine integration and Vertex AI for ML model hosting.

**Revised Data Flow (Vertex Native Ingestion Architecture):**
[Data Sources (GEE, NOAA, NWS)] → (Celery daily cron) → [Django Harvester] → HTTP POST (lightweight bbox + time_horizon + model_type payload) → [FastAPI ML Adapter (Cloud Run)] → Vertex AI model endpoints (U-Net / PINN / RL) → Unified GeoJSON FeatureCollection → [Django Database Engine] → PostGIS (Cloud SQL) + Redis (Memorystore) → [Django REST API (Cloud Run)] → REST Polling (every 5 min) → [React Frontend (Cloud CDN)]

---

## 1.1 Component Specifications & Responsibilities

### The Django Monolith (Web & Orchestration)

**Module 1 (The Harvester & Active Fire Scout)**
The Harvester is designed with two complementary orchestration pipelines:
- **Automated Celery Startup Warmup (`harvester.signals.on_worker_ready`):** Registered via Celery `@worker_ready.connect` in `backend/harvester/signals.py` and loaded during `HarvesterConfig.ready()`. Automatically dispatches `fetch_wind_data.delay()`, `fetch_airnow_aqi.delay()`, and `trigger_active_inference.delay()` as soon as the Celery worker process initializes, ensuring immediate self-healing and pre-warming of the Redis cache and PostGIS database on startup without executing external scripts.
- **Daily Baseline Orchestrator (`trigger_daily_inference`):** Scheduled daily at 06:00 UTC by Celery Beat for regional risk mapping across strictly supported horizons (`0h`, `1h`, `3h`, `6h`).
- **Active Fire Scout (`trigger_active_inference`):** Scheduled every 30 minutes by Celery Beat (`trigger-active-inference-30min`) for near-real-time active wildfire detection and dynamic spread prediction (+1, +3, +6 hours):
  - Fetches VIIRS 375 m active fire detections from all three operational sensors via NASA FIRMS Area API (`VIIRS_SNPP_NRT`, `VIIRS_NOAA20_NRT`, `VIIRS_NOAA21_NRT` via `FIRMS_MAP_KEY`) across the expanded Bay Area & Delta bounding box (`BAY_AREA_BBOX = (-122.9, 36.9, -121.2, 38.5)`) using a rolling 2-day window (`/2`), filtered to the 2-calendar-day window ("From Yesterday 00:00:00 UTC to present", up to 48 hours) to maintain 100% parity with the NASA FIRMS web portal. Includes automatic failover to the public keyless 24-hour VIIRS CSVs if the keyed Area API is unreachable or returns invalid/error payloads (NFR-R04).
  - Deduplicates overlapping detections across satellite orbits within 0.5 km (prioritizing higher Fire Radiative Power).
  - Filters low-confidence detections and applies spatial exclusion masks around known East Bay and South Bay industrial flaring sites (Chevron Richmond Refinery, Phillips 66 Rodeo Refinery, Martinez Refining Co., Valero Benicia Refinery, and Newby Island Landfill in Alviso) to suppress refinery and landfill flare false alarms.
  - Caches all raw satellite hotspots (active wildland detections and suppressed flares) in Redis under `ffwai:telemetry:firms_hotspots` with metadata (`latitude`, `longitude`, `frp`, `confidence`, `satellite`, `is_industrial_flare`, `flare_site_name`, `acq_date`, `acq_time`).
  - Clusters remaining wildland hotspots within 3 km into distinct fire envelopes, applying a +25 km simulation buffer.
  - Upserts `FireIncident` records in PostGIS to track active incidents across runs.
  - Dispatches parallel AI inference per incident using a Celery `chord` (`run_async_inference.s(...)`), requesting `model_type="ensemble"`, `time_horizon=6`, current UTC `date`, and passing detected 375 m VIIRS hotspot coordinates as `seed_points`. When GOES-18 has no active 2 km pixel detection (sensor mismatch), U-Net uses the detected VIIRS hotspot coordinates as its ignition seed rather than aborting with zero features.
  - Aggregates multi-incident predictions in `aggregate_active_predictions`, persisting `PredictionPolygon` rows linked to `FireIncident` and updating the active Redis cache (`ffwai:predictions:current` and `ffwai:predictions:current:ensemble`) with a 6-hour TTL (`timeout=21600`).
  - Guards against overwriting a populated Redis cache with `features: []` if an asynchronous scan sees zero new burns.
  - Retains all prediction runs in PostGIS `PredictionPolygon` rows permanently for historical analysis and audits.
  - Periodically executes `archive_old_predictions`: automatically marks active incidents as contained (`is_active=False`, `containment_time=timezone.now()`) when 24 consecutive hours elapse without any satellite hotspot detections within their bounding box, and purges their active prediction keys from Redis while keeping historical PostGIS rows permanently intact.
- A `store_geojson_result()` function that writes returned GeoJSON to PostGIS and Redis with a 6-hour TTL (`timeout=21600`).

*Note: Under the new Vertex Native Ingestion architecture, the backend no longer constructs massive NumPy array tensors. Instead, it passes lightweight bounding boxes and ignition seeds to the ML Adapter.*

**Module 2 (Database Engine)**
The Database Engine module manages all persistent and transient spatial data storage for the platform. This module utilizes the GeoDjango framework to receive incoming predictive GeoJSON outputs generated by the external ML Inference Engine. Upon reception, the engine executes spatial database inserts into a PostgreSQL database augmented with the PostGIS extension, establishing a permanent historical archive for longitudinal fire tracking and model auditing (PredictionPolygon records are retained permanently). Simultaneously, to ensure low-latency data retrieval for the frontend application, the module maintains active prediction keys within an in-memory Redis cache with 6-hour TTL. Furthermore, the Database Engine holds responsibility for querying and serving static, mission-critical geospatial coordinates, such as the Federal Emergency Management Agency (FEMA) and California Governor's Office of Emergency Services (CalOES) designated emergency shelter locations directly from the PostGIS instance.

The Django model for the GeoJSON output contract is defined as follows:
- `timestamp` (DateTimeField, indexed)
- `source_model` (CharField: "unet", "pinn", "mock")
- `grid` (ForeignKey to BayAreaGrid, SRID=4326)
- `fire_probability` (FloatField, 0.0–1.0)
- `ml_metrics` (JSONField for raw model output parameters)

**Module 3 (API & Alerts)**
The API module functions as the primary communication interface between the backend monolith and the frontend client. This module utilizes the Django REST Framework (DRF) to expose secure HTTP endpoints for data retrieval. Dynamic turn-by-turn routing is currently out-of-scope; instead, the system focuses on alternative alerting methods such as Safe Shelter Handoff and Zone-Based Warnings. The frontend polls the REST API every 5 minutes to check for updated predictions and active zone warnings; no WebSocket connection is required for the MVP. The `GET /api/predictions/current/` endpoint incorporates an API Fallback Guard: if the Redis cache is empty or returns `features: []`, it automatically queries active PostGIS `PredictionPolygon` records before serving empty data. Forecast horizons are strictly constrained to integer values `[0, 1, 3, 6]`. Auto-generated OpenAPI 3.0 documentation is served at `/api/docs/` via `drf-spectacular`.

### The FastAPI ML Adapter (Cloud Run)

The FastAPI ML Adapter serves as an isolated translation layer between the Django/Celery backend and the ML models hosted on Vertex AI. It receives lightweight bounding box parameters, orchestrates necessary data, invokes the appropriate Vertex AI model endpoint(s), and normalizes their diverse outputs into a standard unified GeoJSON FeatureCollection.

- **Endpoint:** `POST /predict/progression` — Runs U-Net, PINN, and/or RL models for fire spread prediction based on payload `bbox`, `time_horizon` (0, 1, 3, 6), `model_type`, and `seed_points`.
- **Endpoint:** `POST /predict/ensemble` — Combines outputs from multiple models via weighted voting (extends Paper 3's Cellular Automata Rule 30 pattern).
- **Endpoint:** `GET /health` — Returns service status and mock mode flag.
- **Mock Mode & Fixture Purge:** Pre-recorded Santa Cruz GeoJSON mock fixtures and synthetic coordinate translations have been completely purged. When live models report 0 features, the adapter cleanly returns a GeoJSON FeatureCollection with `features: []` and `status: "no_active_fire"` without synthetic shifting.
- **Live Dispatch:** Forwards requests and `seed_points` down to containerized inference microservices (U-Net on port 8081, PINN on port 8082).
- Always returns the standard unified GeoJSON FeatureCollection output contract. (See [Vertex AI Endpoint Output Contract](vertex-ai-endpoint-contract.md) for Month 2 ML Integration requirements).


**ML Model Ensemble:**
The FastAPI adapter orchestrates three complementary model types, extending all three of the advisor's research papers:
- **U-Net** (static risk segmentation) — extends Paper 1's grid-based risk approach (using a strict 1km x 1km grid)
- **PINN** (physics-constrained spread) — novel physics contribution
- **RL Agent (DQN/PPO)** (dynamic step-by-step progression) — directly extends Paper 2's Deep RL methodology
- **Ensemble Combiner** — weighted voting/probability averaging across model outputs (extends Paper 3's Cellular Automata Rule 30 pattern)


---

## 2. Tech Stack Breakdown

This stack ensures total Python parity between the AI developers and the backend developers, optimizing geospatial capabilities and eliminating I/O bottlenecks.

- **Frontend (UI/UX):** React.js, Mapbox GL JS (via `react-map-gl/mapbox` for rendering complex GeoJSON polygons), Deck.gl (WebGL overlay for dynamic animated wind particles).
- **Backend (Core Monolith):** Python, Django, Django REST Framework, Celery (Task Scheduling & Orchestration), Celery Beat (Cron Scheduler).
- **Database:** PostgreSQL (hosted on **GCP Cloud SQL**).
  - _Extension:_ `PostGIS` (Managed via **GeoDjango**. Contains only the Bay Area `.osm.pbf` extract to ensure A* pathfinding executes under 2.0 seconds).
- **Caching & Message Broker:** Redis (hosted on **GCP Memorystore**). Serves dual-duty as the Celery task broker and the high-speed GeoJSON cache for the REST API.
- **Data & Storage:** Google Cloud Storage (GCS) for trained model weights and React build output. Google Earth Engine (GEE) and NASA FIRMS for real-time fire detection and satellite imagery.
- **API Documentation:** Auto-generated OpenAPI 3.0 via `drf-spectacular` at `/api/docs/`. FastAPI auto-generates Swagger at `/docs`.

---

## 3. External Data Sources

### 3.1 Category A — Backend-Owned Sources (Celery Harvester Tasks):
- **Google Earth Engine (GEE):** NDVI / EVI / NDWI vegetation indices from Landsat 8/9 (`LANDSAT/LC09/C02/T1_L2`). Critical ML training feature (used in all three advisor papers).
- **GOES-18 via GEE:** Fire Detection & Characterization (`NOAA/GOES/18/FDCC`) and Cloud/Moisture Imagery (`NOAA/GOES/18/MCMIPC`). High-temporal (5 min), low-spatial (2 km) satellite imagery. Daily composite exported to GCS.
- **VIIRS via GEE:** Near-real-time active fire hotspots (`NASA/VIIRS/002/VNP09GA`). High-spatial (375 m), low-temporal (12–24 hr). Paired with GOES-18 for potential super-resolution training by the ML team.
- **NOAA / Open-Meteo / OpenWeather:** Wind speed, direction, temperature, humidity for Deck.gl wind particles and ML features. Uses single-batch multi-coordinate querying and falls back gracefully to calibrated Bay Area climatological vectors on upstream network read timeout (NFR-R04).
- **NWS Alerts API:** Red Flag Warnings for map overlay polygons.
- **CA Energy Commission:** Static powerline GIS data — ignition risk feature from Paper 1.
- **FEMA/CalOES shelter data:** Static emergency POIs loaded into PostGIS.
- **CAL FIRE FRAP:** Historical fire perimeters for model validation and demo scenarios (CZU Lightning Complex, August 2020).
- **NASA FIRMS:** Near-real-time active fire hotspots from Suomi-NPP, NOAA-20, and NOAA-21 (VIIRS 375 m). Used for Active Fire Scout detection and ground-truth pins.
- **Sensor Resolution Mismatch & VIIRS Ignition Fallback:** GOES-18 ABI provides high-temporal (5 min) but coarse-spatial (2 km) pixel resolution, whereas VIIRS provides fine 375 m resolution. When early or small fires are detected by VIIRS but fall below the GOES-18 2 km pixel threshold, the pipeline automatically injects the VIIRS 375 m hotspot coordinates as `seed_points` (ignition seeds) into the U-Net inference tensor channels rather than aborting with zero features.
- **AirNow API:** Live PM2.5 / AQI measurements across Bay Area monitoring stations for environmental hazard overlays.

### 3.2 Category B — ML Pipeline Sources, Model Contracts & Automated Lifecycle:
- **USGS 3DEP DEM:** Static terrain data (elevation, slope, aspect, hillshade) ingested directly by the ML pipeline / Vertex AI during model training. Backend terrain extraction (`TerrainFeature` model and `load_terrain` command) has been retired.
- **Automated Celery Startup Warmup (`@worker_ready.connect`):** Registered in `backend/harvester/signals.py` and loaded during `HarvesterConfig.ready()`. Automatically dispatches `fetch_wind_data.delay()`, `fetch_airnow_aqi.delay()`, and `trigger_active_inference.delay()` immediately upon worker boot, ensuring that the Redis cache and PostGIS database pre-warm automatically without executing manual `seed_cache.py` scripts.
- **Complete Purge of Mock Fixtures & Synthetic Translations:** Pre-recorded Santa Cruz GeoJSON mock fixture files and artificial coordinate translations have been purged. When live models report 0 features, the system cleanly returns a GeoJSON FeatureCollection with `features: []` and `status: "no_active_fire"`, preventing misleading synthetic fire perimeters from displaying on unburned land.
- **Strictly Scoped Forecast Horizons (`0h`, `1h`, `3h`, `6h`):** All prediction interfaces (Frontend TimeScrubber HUD, MapCanvas layer filters, DRF API views, Celery tasks, and ML Adapter payloads) strictly constrain forecast horizons to `[0, 1, 3, 6]` hours. The legacy +24h day-ahead horizon has been completely retired to maintain contract fidelity with the hourly U-Net and PINN microservices.
- **NOAA HRRR:** Short-range weather forecasts (if ML team requires forecast-horizon features).
- **LANDFIRE fuel models:** Vegetation fuel type classification.
- **Google Drive (free unlimited student storage):** Potential shared workspace for large training datasets between backend and ML teams. *Note: Google Drive has API rate limits and is not suitable for programmatic high-frequency access. Use GCS for production data and Google Drive as a secondary backup for large files the ML team needs to access manually.*

---

## 4. RAG Knowledge Base — DEFERRED

> **Status:** Out of scope until core features (fire prediction, telemetry) are fully functional.

The RAG-backed chatbot (FR-E07, FR-E08) and its supporting vector database (`pgvector`) are deferred. The `pgvector` extension has been removed from the tech stack for the MVP. If re-introduced, the RAG chatbot will require:
- `pgvector` extension on Cloud SQL
- LangChain/LlamaIndex integration
- BAAQMD, CalFire, and PubMed knowledge base documents

---

## 5. Functional Requirements (FR)

### A. 🔴 Essential Features (Build First — Month 1)

- **FR-E01 [Prediction Visualization]:** Visualize ML-generated next-day fire risk zones on the interactive map as a 1×1 km grid-based Deck.gl heatmap. Each cell displays `fire_probability` with color intensity. Extends the grid-based visualization from all three advisor papers.
- **FR-E02 [Alerts & Zone Warnings]:** Trigger alternative alerting methods (e.g., Safe Shelter Handoff or Zone-Based Warnings) instead of turn-by-turn routing when risk zones intersect populated areas.
- **FR-E03 [Confidence Metrics]:** Display the ML model's `fire_probability` (float 0.0–1.0) from the GeoJSON contract for each grid cell.
- **FR-E04 [Telemetry & Environmental Hazards]:** Display live telemetry (Wind Speed/Direction), render Deck.gl animated wind particle arrays reflecting live weather vectors, and overlay NWS Red Flag Warning polygons when active.
- **FR-E05 [Emergency POIs]:** Display static Points of Interest using custom HTML markers (e.g., FEMA Evacuation Shelters with Lucide-react icons) anchored to the map. Utilizes FEMA/CalOES datasets loaded into PostGIS.
- **FR-E09 [Mock Mode]:** The system must support a `MOCK_INFERENCE=true` environment flag that bypasses the FastAPI ML Adapter and serves a pre-loaded Bay Area GeoJSON fixture. Required for Month 1 development and CI/CD testing without a trained model.
- **FR-E10 [Model Performance Dashboard]:** Display model evaluation metrics (ROC-AUC, F1, accuracy, precision, recall) per model run in a frontend admin panel. Echoes the evaluation methodology from all three advisor papers.

### B. 🟡 Desired Features (Month 2 / Other Developer)

- **FR-D02 [Air Quality Integration]:** Overlay real-time PM2.5 data on the map interface. OpenAQ / PurpleAir integration — delayed but kept in plan.
- **FR-D03 [Health-Personalized Risk]:** Generate personalized risk labels based on user health profiles and local AQI. Requires user accounts — assigned to the other backend developer.
- **FR-E06 [Alert Configuration]:** Allow configuration of SMS/push notifications — deferred.

### C. 🔵 Out of Scope (Until Core is Done)

- **FR-E07 [RAG Chatbot]:** Deferred — focus on wildfire prediction + telemetry first.
- **FR-E08 [Source Citation]:** Depends on FR-E07 (RAG chatbot).
- **FR-D01 [Extended Forecast]:** Depends on ML team's forecast horizon.
- **FR-D04 [Conversation History]:** Depends on RAG chatbot.
- **FR-D05 [Anthropogenic Data Integration]:** ML team to decide.
- **FR-D06 [Emission Estimation]:** Optional stretch goal.
- **FR-O01 [Climate Simulation]:** Stretch goal.
- **FR-O02 [Crowdsourced Reporting]:** Stretch goal.
- **FR-O03 [First Responder Tracking]:** Stretch goal.

> *Note: FRs will be adjusted continuously as development progresses and ML team capabilities solidify.*

---

## 6. Non-Functional Requirements (NFR)

### CAP Theorem Decision
**Fight Fire With AI chooses AP (Availability + Partition Tolerance) with eventual consistency.** Predictions are eventually consistent within one inference cycle (24 hours). The frontend always serves a response — either fresh predictions or the last cached prediction with a staleness indicator. If any component is unreachable, the system continues operating in degraded mode using cached data.

### A. Performance & Latency

- **NFR-P01 [Inference Speed]:** Inference runs as a daily Celery background task. Target completion < 60 seconds. Frontend reads from Redis cache (< 100ms). No synchronous user-facing inference SLA.

### B. Scalability

- **NFR-S01 [Concurrent Users]:** The REST API shall handle **100 concurrent users** with < 500ms p95 response time. (MVP uses REST polling, not WebSocket.)
- **NFR-S02 [Horizontal Scaling]:** The Celery worker pool shall support independent scaling of harvester tasks vs. inference tasks via separate queues (`harvest_queue`, `inference_queue`).

### C. Reliability & Fault Tolerance

- **NFR-R01 [Graceful Degradation]:** If external APIs or the ML Adapter fail, the pipeline shall automatically fall back to utilizing the last successfully cached GeoJSON prediction from Redis.
- **NFR-R04 [Prediction Staleness]:** If the most recent successful prediction is older than **48 hours**, the system shall: (a) mark risk zones with a `STALE` badge in the UI, (b) log a critical alert, and (c) attempt inference with the last known valid feature set (degraded mode).
- **NFR-R05 [Harvester Resilience]:** Each Celery harvester task shall implement independent retry logic with exponential backoff (max 3 retries). If a data source is unreachable after all retries, the task shall log a warning and proceed with the last cached value. The daily inference task shall execute regardless of partial harvester failures — partial data is better than no prediction.

### D. Observability

- **NFR-O01 [Structured Logging]:** All Celery tasks shall emit structured JSON logs with: task name, duration, data source, record count, and success/failure status. Django shall log API response times.
- **NFR-O02 [Health Endpoint]:** The Django backend shall expose `GET /api/health/` returning: database status, Redis status, last inference timestamp, prediction staleness, and Celery worker count. The FastAPI ML Adapter exposes `GET /health`.

### E. Usability (Developer Experience)

- **NFR-U01 [API Documentation]:** The Django REST API shall auto-generate OpenAPI 3.0 documentation via `drf-spectacular`, accessible at `/api/docs/`. The FastAPI ML Adapter auto-generates Swagger docs at `/docs`.
- **NFR-U02 [Docstring Traceability]:** Every Django model, serializer, and Celery task shall include a docstring citing which paper/FR/NFR it satisfies. This creates direct traceability from code to requirements.

### F. Deferred NFRs (Build If Easy / Time Permits)

- ~~**NFR-SEC03 [Rate Limiting]:**~~ Rate limit 60 req/min per IP via `django-ratelimit`. Include if trivial to add.
- ~~**NFR-C01 [Regional Configurability]:**~~ Bounding box + grid resolution configurable via env vars. Design for it, don't build multi-region.

### G. Removed NFRs

| Removed NFR | Reason |
|---|---|
| ~~NFR-P03 [Streaming Latency]~~ | RAG chatbot / WebSocket deferred; MVP uses REST polling |
| ~~NFR-S01 (old: 5,000 WebSocket)~~ | Replaced with 100 concurrent REST users |
| ~~NFR-S02 (old: RAG Guardrails)~~ | RAG chatbot is out of scope |
| ~~NFR-R02 [LLM Fallback]~~ | RAG chatbot is out of scope |
| ~~NFR-R03 [99.9% Uptime]~~ | Unrealistic on student budget; target ~99.5% via auto-restart |
| ~~NFR-SEC01 [AES-256]~~ | Health profiles are deferred |
| ~~NFR-SEC02 [JWT/OAuth]~~ | User accounts are deferred |

> *Note: NFRs will be adjusted continuously as development progresses.*

---

## 7. Out of Scope (Explicitly Excluded to Prevent Scope Creep)

Given the timeline and academic constraints, the following features are explicitly excluded:
- **Evacuation Routing:** Deprecated and removed from platform scope. The system focuses on zone-based warnings and emergency shelter POI telemetry rather than dynamic turn-by-turn routing.
- **RAG Chatbot & Health Profiles:** Deferred until core prediction and telemetry features are complete. Including pgvector, LangChain, and user account management.
- **Live Official Evacuation Orders:** Fragmented across different county systems with no single, free, real-time API. We rely entirely on our AI's predicted risk polygons for zone alerting.
- **Prescribed Burns vs. Wildfires:** AI relying purely on infrared pixels has difficulty distinguishing controlled burns from wildfires. For the MVP, all detected thermal anomalies are treated as potential risks.
- **Live Power Outages:** Utility APIs (e.g., PG&E) are tightly controlled and unreliable to scrape.
- **Sub-hourly fire spread prediction intervals:** Deferred until ML team delivers a short-term model.
- **On-demand (< 5 second) synchronous ML inference triggered by user action.**
- **Multi-region deployment:** System is scoped to the Bay Area. Regional configurability is designed but not built.
- **EFFIS (European Forest Fire Information System):** Not applicable for California. Use domestic sources (CAL FIRE FRAP, NASA FIRMS, WFIGS).

---

## 8. API Endpoint Registry

### A. Django REST API (Internal — Backend to Frontend)

| Method | Endpoint | Purpose | Response |
|---|---|---|---|
| `GET` | `/api/predictions/current/` | Latest fire risk prediction (from Redis cache with 6-hour TTL / timeout=21600). Supports `?model=ensemble\|unet\|pinn` and `?horizon=0\|1\|3\|6` (strictly scoped to `[0, 1, 3, 6]`; legacy +24h horizon removed). Uses model-scoped Redis cache keys (`ffwai:predictions:current[:model]`). Includes API Fallback Guard: if cache is cold or has empty features (`features: []`), automatically queries active PostGIS `PredictionPolygon` records before serving empty data. | GeoJSON FeatureCollection + metadata (staleness, model version, data completeness) |
| `GET` | `/api/predictions/history/` | Historical predictions with date range filter (reads permanently retained `PredictionPolygon` PostGIS records) | Paginated GeoJSON FeatureCollection list |
| `GET` | `/api/telemetry/wind/` | Current wind speed/direction for Deck.gl particles | JSON: `{speed, direction, timestamp}` |
| `GET` | `/api/telemetry/shelters/` | FEMA/CalOES emergency shelter locations | GeoJSON FeatureCollection (Points) |
| `GET` | `/api/telemetry/alerts/` | Active NWS Red Flag Warnings | GeoJSON FeatureCollection (Polygons) |
| `GET` | `/api/telemetry/hotspots/` | NASA FIRMS raw satellite hotspots (wildland detections & suppressed flares) | GeoJSON FeatureCollection (Points with FRP, confidence, satellite, flare metadata) |
| `GET` | `/api/metrics/` | Model performance metrics (ROC-AUC, F1, accuracy) | JSON array of `ModelPerformanceMetric` records |
| `GET` | `/api/health/` | System health check | JSON: `{db, redis, last_inference, staleness, workers}` |
| `GET` | `/api/docs/` | Auto-generated OpenAPI 3.0 documentation | Swagger UI (via `drf-spectacular`) |

### B. FastAPI ML Adapter (Internal — Celery Worker to ML Engine)

| Method | Endpoint | Purpose | Response |
|---|---|---|---|
| `POST` | `/predict/progression` | Trigger U-Net + PINN + RL fire spread prediction. Accepts `bbox`, `time_horizon` (0, 1, 3, 6), `model_type`, `date`, `mock`, and `seed_points: list[tuple[float, float]]` (or `ignition_points`). Pre-recorded mock fixtures are purged; when live models report 0 features, cleanly returns `features: []` with `status: "no_active_fire"`. | GeoJSON FeatureCollection |
| `POST` | `/predict/ensemble` | Explicit ensemble: combine all available model outputs via weighted scaling. Supports `seed_points`. When models report 0 features, returns `features: []` with `status: "no_active_fire"`. | GeoJSON FeatureCollection |
| `GET` | `/health` | ML Adapter health check + mock mode status | JSON: `{status, mock, models_loaded}` |
| `GET` | `/docs` | Auto-generated Swagger documentation | Swagger UI (built-in FastAPI) |


### Incident Containment Lifecycle & Cache Cleanup
- **Permanent Retention:** All prediction runs (`PredictionPolygon` rows in PostGIS) are permanently retained to maintain an immutable audit trail for longitudinal research (FR-E01).
- **Automated Containment:** `archive_old_predictions` executes periodically. Active incidents (`FireIncident.objects.filter(is_active=True)`) with no satellite hotspot detections within their bounding box for 24 consecutive hours are automatically marked as contained (`is_active=False`, `containment_time=timezone.now()`).
- **Partial Containment Cache Refresh:** When some incidents are contained while others remain active, `archive_old_predictions` immediately refreshes active Redis prediction cache keys (`ffwai:predictions:current` and `ffwai:predictions:current:ensemble`) to exclude contained incidents, serving only remaining active incidents' polygons.
- **Full Containment Redis Purge:** When all active incidents are contained (`remaining_active_count == 0`), transient active prediction keys (`ffwai:predictions:current*`) are purged from Redis while historical PostGIS rows remain intact.

### C. External APIs (Outbound — Celery Harvester to Third-Party)

| Service | Method | Endpoint / GEE Collection | Purpose | Cadence |
|---|---|---|---|---|
| Google Earth Engine | SDK | `LANDSAT/LC09/C02/T1_L2` | NDVI / EVI / NDWI vegetation indices | Weekly |
| Google Earth Engine | SDK | `NOAA/GOES/18/FDCC` | GOES-18 Fire Detection (thermal hotspots) | Daily composite |
| Google Earth Engine | SDK | `NOAA/GOES/18/MCMIPC` | GOES-18 Cloud & Moisture Imagery | Daily composite |
| Google Earth Engine | SDK | `NASA/VIIRS/002/VNP09GA` | VIIRS active fire hotspots (375 m) | Daily |
| NOAA / OpenWeather | `GET` | `api.openweathermap.org/data/2.5/...` | Wind speed, direction, temperature, humidity | Daily |
| NWS Alerts API | `GET` | `api.weather.gov/alerts/active` | Red Flag Warnings (Bay Area zone) | Every 6 hours |
| NASA FIRMS | `GET` | `firms.modaps.eosdis.nasa.gov/api/area/...` | VIIRS 375 m active fire hotspots for scout | Every 30 minutes |

---

## 9. Competitive Analysis & Defense Pitch (The Fight Fire With AI Advantage)

While existing apps like *Watch Duty* serve as the gold standard for UI/UX and human-verified reporting, Fight Fire With AI differentiates itself fundamentally through its AI-driven, automated architecture:

- **Predictive vs. Reactive:** Human-in-the-loop systems are reactive—they report where a fire is and what officials have already done based on radio scanners. Fight Fire With AI is **predictive**. By providing day-ahead fire risk planning, it offers users a critical head start before official channels issue orders, with the architecture designed to support shorter-interval predictions as the ML pipeline matures.
- **Proactive Zone Alerts:** Existing apps provide a map but leave the user to monitor changes. Fight Fire With AI proactively provides Safe Shelter Handoffs and Zone-Based Warnings based on predicted danger zones.

---

## 10. Frontend MVP Prototype Implementation Details

The frontend MVP was developed as a standalone showcase of the system's capabilities, designed specifically for a Master's defense presentation. It simulates the real-time AI and routing behaviors described above without requiring a live connection to the Python/Django backend.

### 9.1 Prototype Stack & Tooling
- **React 19 & Vite:** Core SPA framework providing fast development and hot-module reloading.
- **Tailwind CSS v4 & Lucide-React:** For rapid, utility-first UI styling with a "Glassmorphism" aesthetic (translucent, blurred backgrounds) and consistent SVG iconography.
- **Mapbox GL JS (`react-map-gl/mapbox`):** Renders the core geospatial canvas using the `dark-v11` style and 3D terrain exaggeration (`mapbox-dem`) to highlight topographical features in the Bay Area (e.g., Hayward hills).
- **Deck.gl:** A WebGL-powered framework used to overlay complex, high-performance animations—specifically, the animated wind particle grids.
- **Framer Motion:** Powers smooth UI animations, such as the slide-out RAG Chatbot drawer.

### 9.2 Map Layering & Visual Hierarchy (Strict Z-Index)
To prevent visual clutter, the map employs a strict hierarchical rendering order from bottom to top:
1. **Base Topography:** Mapbox `dark-v11` / `outdoors-v12` base map with 3D terrain exaggeration.
2. **Red Flag Warning Zone:** A static NWS environmental danger polygon rendered as a translucent red area.
3. **AQI 45-Mile Radial Grid:** Dynamic air quality mesh interpolated across regional reporting sensors.
4. **Predictive Spread (U-Net / PINN / Ensemble):** Semi-transparent color ramp polygons representing predicted fire progression filtered by time horizon.
5. **Deck.gl Wind Particles:** An animated WebGL vector field simulating continuous atmospheric breeze and gust patterns.
6. **Satellite Hotspots (NASA FIRMS):** Ground-truth infrared detections persisting across all time horizons (pulsing red rings for active wildland detections, distinct grey factory pins for suppressed petrochemical/landfill flaring sites with interactive hover tooltips).
7. **Static POIs & Markers:** Custom HTML markers (using `lucide-react` icons) for FEMA Evacuation Shelters and the User Location, anchored to the top of the map.

### 9.3 HUD (Heads-Up Display) Components
- **Model Selector & Timeline Bar Integration:** The model selector is integrated directly into the header of the bottom **Time Scrubber** bar (eliminating floating map canvas clutter and removing redundant duplicate tabs from the Layers drawer). It employs pure typography and distinct model accent colors: **PIML** (Scientific Teal `bg-teal-600`, with teal forecast badge `bg-teal-50 text-teal-800 border-teal-200` and teal scrubber accent), **U-Net** (Neural Indigo `bg-indigo-600`, with indigo forecast badge and scrubber accent), and **Ensemble** (Composite Purple `bg-purple-600`, disabled pending AI/ML specifications). This separates PIML cleanly from the Ember Orange branding used across the rest of the application. Switching models dynamically adapts the Time Scrubber's active time badge and slider thumb accents, and queries `/api/predictions/current/?model={model}` with model-scoped Redis caching.
- **Telemetry Card:** A dynamic floating panel displaying environmental telemetry (AQI, Wind Speed/Direction, and Vulnerability). It features a conditionally rendered, pulsing red banner when a Red Flag Warning is active, and a rotating SVG wind arrow physically aligned with the animated wind field.
- **Time Scrubber:** An interactive bottom timeline slider strictly scoped to 4 discrete forecast horizons: `0h` (Current Observed Fire), `+1h`, `+3h`, and `+6h`, filtering vector features client-side on the Mapbox GPU at 60 FPS (`filter: ['==', ['get', 'horizon_hours'], timeScrub]`) without network latency. Its top header houses the integrated Model Selector and the dynamic Active Forecast Time Badge.
- **Map Layers & Dynamic Legend:** A drawer providing toggles for optional secondary environmental overlays (**AQI Grid Layer** and **Emergency Shelters**), while core situational awareness layers (Fire Probability Polygons and Satellite Hotspots) remain permanently active on the map canvas. Houses the comprehensive visual legend for Red Flag Warnings, active wildland hotspots, suppressed flares, emergency shelters, and fire probability color gradients.
- **RAG Chatbot Drawer:** A floating action button (FAB) that opens an AI assistant interface that detects user inputs (e.g., evacuation routes, shelter capacity) and outputs localized advice citing NWS and CalOES.

<!-- ### 9.4 Scenario Orchestration (The "Golden Path" Script)
To bypass the lack of a live backend during the defense presentation, the prototype utilizes a `ScenarioController` to manually step through predefined JSON mock states (`mockData/geojsonStates.js` and `windGrids.js`).
- **State 1 (NORMAL):** Showcases ambient westerly winds, a low vulnerability score, and a clean map with no routes or warnings.
- **State 2 (AI_UPDATE):** Simulates an environmental shift. The wind shifts to a fierce 45 mph South-West blow, the Red Flag Warning polygon appears, the ML spread polygons bloom, and the original highway route renders as a compromised dashed red line.
- **State 3 (REROUTE):** Simulates the A* backend. The compromised route disappears, and a solid blue detour path connects the user's location to the nearest safe shelter (Chabot College). -->

---

## 11. QA & Testing Strategy

A rigorous Quality Assurance (QA) strategy ensures the reliability and accuracy of Fight Fire With AI, particularly given its safety-critical context. Testing is divided into the following phases:

### 11.1 AI & Data Pipeline Testing
- **Model Validation:** The U-Net model is validated against historical ground truth data (e.g., NASA FIRMS data from the CZU Lightning Complex fire, August 2020). Accuracy, Precision, Recall, and Intersection over Union (IoU) metrics will be calculated to ensure predictive reliability.
- **Mock Mode Testing:** Verify that the system correctly serves a pre-loaded Bay Area GeoJSON fixture when `MOCK_INFERENCE=true` without attempting a real inference.
- **Data Ingestion Unit Tests:** Automated unit tests (via `pytest`) verify that the Celery harvester successfully orchestrates the pipeline, including retry logic and fallback to cached data.

### 11.2 Backend & API Testing
- **PostGIS Spatial Queries:** Unit tests validate PostGIS spatial queries, ensuring spatial indexing, grid queries, and shelter POI lookups function accurately.
- **Health Endpoint Testing:** Verify `GET /api/health/` returns correct database, Redis, and inference staleness status.

### 11.3 Frontend Validation
- **Component Rendering:** React Testing Library is used to ensure HUD components (e.g., TelemetryCard) render correctly and react dynamically to state changes (e.g., wind shifts, Red Flag Warnings).
- **"Golden Path" E2E Testing:** End-to-end tests (via Cypress or Playwright) simulate user interactions, verifying the seamless transition between `NORMAL` and `AI_UPDATE` states on the Mapbox GL JS canvas, including the proper rendering of Deck.gl wind particles and custom HTML markers.

---

## 12. Performance Evaluation

Given the SLAs defined in the Non-Functional Requirements, performance is continuously evaluated across the stack:

### 12.1 AI Inference Profiling
- **Target:** Inference runs as a daily Celery background task (< 60 seconds).
- **Methodology:** TensorFlow Profiler is used to benchmark the inference time of the U-Net model when processing matrices. Inference runs are logged via structured JSON (NFR-O01) and monitored to ensure they meet the target execution time.

### 12.2 Database Query Benchmarking
- **Target:** Sub-100ms for PostGIS spatial grid and POI queries.
- **Methodology:** Automated query profiling ensures spatial lookups and Redis caching perform well within SLAs.

### 12.3 REST API Performance
- **Target:** 100 concurrent users with < 500ms p95 response time.
- **Methodology:** Locust is used to simulate concurrent REST API polling against `GET /api/predictions/current/`. On the frontend, Chrome DevTools and React Profiler are used to monitor framerates, ensuring the Deck.gl WebGL canvas and Mapbox GL JS layers maintain 60 FPS during complex animations.

---

## 13. Deployment Plan

The deployment strategy for the Fight Fire With AI MVP leverages containerization and cloud infrastructure to ensure scalability and ease of deployment.

### 13.1 Infrastructure Architecture
- **Containerization:** All modules (Django Backend, FastAPI ML Adapter, React Frontend, Celery Workers) are containerized using **Docker** and managed via `docker-compose` for local development and parity.
- **Cloud Provider:** Deployed on **Google Cloud Platform (GCP)**.
  - **Backend API:** Django REST API hosted on **Cloud Run** (serverless, scales to zero — cost-effective for student budget).
  - **ML Adapter:** FastAPI hosted on **Cloud Run** (separate service with ML dependencies isolated).
  - **ML Model Hosting:** Trained U-Net, PINN, and RL models served via **Vertex AI** managed endpoints with automatic retraining support.
  - **Database:** **Cloud SQL** for PostgreSQL with PostGIS extension enabled.
  - **Cache/Broker:** **Memorystore** (Redis) for Celery task queuing and GeoJSON cache.
  - **Object Storage:** **Google Cloud Storage (GCS)** for trained model weights and React build artifacts.
  - **Frontend:** Compiled React static assets hosted on **Cloud Storage** and distributed via **Cloud CDN**.
  - **Background Workers:** Celery Workers + Celery Beat running on a **Compute Engine** e2-micro instance (persistent — needs to stay alive for cron scheduling).
  - **Satellite Data:** **Google Earth Engine** (free academic tier) — natively integrated with GCP project.

### 13.2 CI/CD Pipeline
- **Continuous Integration (CI):** GitHub Actions automatically trigger on every Pull Request to run `eslint`, `pytest`, and build verifications.
- **Continuous Deployment (CD):** Upon merging to the `main` branch, the CI/CD pipeline builds new Docker images, pushes them to **Google Artifact Registry**, and triggers a rolling update on the Cloud Run services.

### 13.3 Local Development Stack & Lifecycle Ordering
To prevent race conditions during local startup (`scripts/run_local.sh`), startup follows a strict ordered lifecycle:
1. **Infrastructure Initialization:** Starts Docker containers (`docker compose up -d --build`) for PostgreSQL/PostGIS (5432), Redis (6379), U-Net (8081), and PINN (8082).
2. **Infrastructure Readiness Gate:** Actively polls until PostgreSQL (`pg_isready`) and Redis (`redis-cli ping`) accept TCP connections.
3. **Application Process Launch:** Spawns isolated terminals for Django (8000), Celery Worker, Celery Beat, FastAPI ML Adapter (8001), and React Frontend (5173).
4. **Service Health Gate:** Actively polls FastAPI ML Adapter (`GET /health`) on port 8001 until HTTP 200 is confirmed.
5. **Automated Cache, Database Warmup & Incident Containment (`@worker_ready.connect`):**
   - Retires the need to manually invoke `scripts/seed_cache.py` or any manual cleanup script.
   - Celery worker startup signal hook (`harvester.signals.on_worker_ready`) automatically dispatches:
     - `archive_old_predictions.delay()` (evaluates PostgreSQL incidents, automatically containing any with no recent detections)
     - `fetch_wind_data.delay()` (live wind vector telemetry)
     - `fetch_airnow_aqi.delay()` (live PM2.5 / AQI telemetry)
     - `trigger_active_inference.delay()` (NASA FIRMS VIIRS 375m active fire scout using 2-day rolling window)
   - Automatically pre-warms Redis and PostGIS across strictly supported forecast horizons (`0h`, `1h`, `3h`, `6h`).
   - Incident containment runs continuously on Celery Beat every 30 minutes (`archive-old-predictions-30min`).

---

## 14. ML Integration Contract

- **Plug-and-Play System:** The system treats the ML Inference Engine as a plug-and-play black box. The backend and ML teams are decoupled via the FastAPI ML Adapter and containerized inference services (`ml_services/`).
- **Inference Services Structure & Ports:**
  - **FastAPI ML Adapter (`ml_adapter/`):** Listens on port 8001. Proxies requests to downstream containerized services (`UNET_SERVICE_URL=http://localhost:8081` and `PINN_SERVICE_URL=http://localhost:8082`), handles health probing (`GET /health`), and multi-model ensemble blending (`POST /predict/ensemble`).
  - **U-Net Service (`ml_services/unet_service/`):** Listens on port 8081 (`AIP_HTTP_PORT=8081`). Exposes `GET /health` and `POST /predict`. Bundles pre-trained weights (`models/goes_h1`, `models/goes_h3`, `models/goes_h6`) and California 1 km terrain cache (`static_ca_1km.npz`). Uses native NOAA GOES-18 ABI and Open-Meteo ingestion with isotonic calibration. Post-processing uses a calibrated emission threshold of `P_EMIT = 0.001` and `MIN_CONFIDENCE = 0.001` with 4-decimal probability rounding (`round(p, 4)`), allowing low-intensity spot fires under mild meteorological conditions to emit subtle `LOW_RISK` spread perimeter polygons (0.1%–5%) across +1h, +3h, and +6h forecast horizons rather than culling them and appearing visually static.
  - **PINN / PIML Service (`ml_services/ml_pinn_service/`):** Listens on port 8082 (`AIP_HTTP_PORT=8082`). Exposes `GET /health` and `POST /predict`. Implements calibrated Physics-Informed Machine Learning (v0.3.1 PIML) fire spread simulation using Ridge regression trained on 218 CAL FIRE historical fires predicting growth multipliers that drive a 10-member level-set physics ensemble. Enforces a built-in LANDFIRE FBFM40 fuel check (`min_burnable_share = 0.25`), deliberately excluding agricultural crop residue burns (such as farmland in Courtland/Hood) while actively simulating wildland fires in burnable grass, brush, and timber. Runs with a unified +20 km buffer.
- **Contract Interface:**
  - **Input Payload:** JSON with `bbox` (4-float tuple), `date` (ISO-8601 string, optional — defaults to UTC now), `time_horizon` (int hours: 0, 1, 3, 6), and `model_type` ("unet", "pinn", "piml", or "ensemble").
  - **Output Contract (ML Engine → Django Backend):** Standard unified GeoJSON `FeatureCollection` containing per-cell features with `grid_id`, `fire_probability` (0.0–1.0), `risk_label`, `horizon_hours` (0, 1, 3, 6), `source_model`, `w_unet`, and `members`.
  - **Dedicated Parallel Inference Fan-Out & Multi-Incident Cumulative Cache:** The Celery active fire scout (`harvester.tasks.trigger_active_inference`) fans out separate parallel inference tasks for both `unet` and `pinn` (PIML) for each detected wildfire cluster across the expanded Bay Area & Sacramento Delta boundary (`BAY_AREA_BBOX = (-122.9, 36.9, -121.2, 38.5)`). Results are written directly to PostGIS (`PredictionPolygon` rows tagged with `source_model="unet"` and `source_model="pinn"`). When updating Redis (`ffwai:predictions:current:unet` and `ffwai:predictions:current:pinn`), `store_geojson_result` aggregates predictions across all currently active fire incidents within the last 6 hours, preventing concurrent incidents (e.g., Courtland, Galt, Rio Vista) from overwriting each other in the cache.
  - **Ensemble Status:** Blending disparate models not trained together is paused pending formal mathematical combination specification (weighting, Bayesian updating, or cellular automata voting) from the AI/ML research team.
- **Mock Fixture Purge & Clean Empty Output:**
  - Mock GeoJSON fixture files and synthetic coordinate translations have been purged.
  - When live models detect 0 features, the adapter cleanly returns a GeoJSON FeatureCollection with `features: []` and `status: "no_active_fire"`, avoiding any fallback or translation of pre-recorded Santa Cruz files onto the map.
- **Inference Cadence:** Daily Celery cron job (`harvester.tasks.trigger_daily_inference` at 06:00 UTC) plus 30-minute Active Fire Scout (`harvester.tasks.trigger_active_inference`). Uses NASA FIRMS Area API rolling 2-day window (`/2`) filtered to the NASA FIRMS 2-calendar-day window ("From Yesterday 00:00:00 UTC to present", up to 48 hours), guaranteeing uninterrupted detection telemetry across UTC calendar rollover and 1:1 parity with the NASA FIRMS web portal.
- **Active Models:** U-Net (spatial segmentation), PIML (Physics-Informed Machine Learning spread), RL Agent DQN/PPO (dynamic progression).
- **Incident Lifecycle Guard:** Current risk endpoint (`/api/predictions/current/`) strictly rejects contained or historical incidents (>6h old). When no active wildland fires are burning, it returns `features: []` with `status: "no_active_fire"`, preventing resurrection of past incidents.
- **Research Lineage:** U-Net extends Paper 1 (Malik et al., 2021), RL extends Paper 2 (Adhikari et al., 2024), Ensemble extends Paper 3 (Malik et al., 2022).
- **ML Black-Box Serving & LLM Implementation Prompt:** Formatted hand-off prompt and schema guide located at [`docs/ml-implementation-prompt.md`](./ml-implementation-prompt.md).



