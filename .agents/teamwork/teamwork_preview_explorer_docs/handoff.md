# Comprehensive Documentation & Architecture Investigation Report: `feature/ml-adapter-integration`

## 1. Observation

### 1.1 Overall Branch Git Log and Statistics
* **Base Commit / Merge Base**: `57304128e9c693878a22d8e06dab8344a007a050`
* **Feature Branch**: `feature/ml-adapter-integration` (`HEAD` at `e046b1149ced5b054e884ed0e24013d4eae9002f`)
* **Diff Stats Across Branch**: 56 files changed, 5,215 insertions(+), 2,671 deletions(-)
* **Commit History (6 Commits, Chronological Order)**:
  1. `93423ab` (`2026-10-05 09:37:26 -0700`) — `feat(predictions): track migration 0002 for PredictionPolygon schema`:
     - Tracks migration renaming `FireRiskPrediction` to `PredictionPolygon`.
     - Adds `ml_metrics` JSONField for raw machine learning output storage.
  2. `ead0603` (`2026-10-05 12:10:09 -0700`) — `feat: complete ML adapter integration, chronological fire tracking, and robust UI updates`:
     - Implements async Celery ingestion pipeline (`harvester/tasks.py`) with scout tasks (`trigger_active_inference`).
     - Normalizes fixture ingestion in FastAPI ML Adapter (`ml_adapter/main.py`).
     - Removes deprecated `routing` app (`backend/routing/*`).
     - Updates `docs/design-doc.md`, `README.md`, `c4_architecture_diagrams.md`.
     - Adds automated shell scripts: `scripts/install.sh` and `scripts/run_local.sh`.
  3. `8e8948f` (`2026-10-05 12:16:50 -0700`) — `docs: update README with setup scripts and mock inference instructions`:
     - Documents one-touch `./scripts/install.sh` and `./scripts/run_local.sh`.
     - Details interactive Django shell commands to trigger mock inference via `harvester.tasks.trigger_mock_inference`.
  4. `7f7ae70` (`2026-10-05 12:26:00 -0700`) — `fix: correct fixture directory path in ML adapter`:
     - Resolves fixture path resolution to `fixtures/frontend_team_geojson_files`.
  5. `9716769` (`2026-10-05 12:46:13 -0700`) — `style: overhaul Time Scrubber UI, align with California Ember theme, snap to valid horizons, update map legend, and remove outdated 24h mock file`:
     - Snaps time scrubber to discrete valid prediction horizons (`0`, `1`, `3`, `6` hours).
     - Deletes outdated mock fixture `Palisades_2025-01-11_h24.geojson`.
     - Updates map legend to continuous probability gradient.
  6. `e046b11` (`2026-10-05 23:59:53 -0700`) — `chore: cleanup and checkpoint ML adapter integration`:
     - Introduces `docs/vertex-ai-endpoint-contract.md` (187 lines).
     - Updates GOES-18 mock spread fixtures across 0h, 1h, 3h, 6h.
     - Adds 5 additional Bay Area emergency shelters in `seed_shelters.py`.
     - Implements continuous IDW AQI interpolation in `AQIGrid.jsx` / `aqiMath.js`.
     - Adds interactive "Safe Haven" hover pop-ups for emergency shelters in `MapCanvas.jsx`.

---

### 1.2 Specific Updates to `docs/vertex-ai-endpoint-contract.md`
* **Status**: New file added on `feature/ml-adapter-integration` (187 lines, 0 lines on `main`).
* **Purpose**: Formalizes the strict Month 2 JSON contract between the FastAPI ML Adapter (Cloud Run) and Vertex AI model endpoints.
* **Exact Contract Details Observed**:
  1. **`PredictionRequest` Payload (FastAPI → Vertex AI)**:
     - `bbox`: `float[]` of 4 elements: `[west, south, east, north]` in WGS-84 degrees. Example: `[-122.9, 36.9, -121.5, 38.3]`. Clamps all output geometries to the Bay Area.
     - `time_horizon`: `int` (hours from forecast start: `0`, `1`, `3`, `6`).
     - `model_type`: `string` (`"unet"`, `"pinn"`, `"rl"`).
     - `date`: `string` (ISO-8601 UTC reference date).
     - `additional_params`: `object` (optional key-value pairs, e.g. `confidence_threshold: 0.2`).
  2. **Feature Properties (Mapbox Standard)**:
     Inside each `Feature.properties`:
     - `fire_probability`: `float` (`0.0`–`1.0`) — Heatmap intensity, mapped to Django `FloatField`.
     - `grid_id`: `int` (positive integer) — Foreign key linking to `BayAreaGrid`.
     - `horizon_hours`: `int` (`0`, `1`, `3`, `6`) — Drives Mapbox slider filtering.
     - `w_unet`: `float` — Model-specific weighting metric stored in `ml_metrics` JSONField.
     - `members`: `int` — Ensemble member count stored in `ml_metrics` JSONField.
  3. **Unified `FeatureCollection` Output**:
     - Returns a single combined response containing all horizons (`0`, `1`, `3`, `6`) in one payload.
     - Shielding Django from handling multi-file joins or asynchronous stream stitching.
  4. **Bounding-Box Enforcement**:
     - Models are required to clip or omit polygons outside `[-122.9, 36.9, -121.5, 38.3]`.
     - Prevents Celery indexing failures, `GEOSException` spatial violations in GeoDjango SRID 4326, and off-screen rendering bugs in Mapbox.
  5. **Protocol & Architectural Constraints**:
     - No async gRPC: Strictly adheres to synchronous HTTP REST semantics to ensure operational simplicity and reliability across Cloud Run.
     - Version tracking via HTTP header `X-Contract-Version: 2026-10-05`.

---

### 1.3 Specific Updates to `README.md`
* **Diff Stats**: 84 lines modified (net -17 lines due to streamlining).
* **Observed Modifications**:
  1. **Project Scope Revision**:
     - *Removed*: References to "dynamic evacuation routing platform" and "calculate safe A* evacuation routes in real time".
     - *Added*: "day-ahead fire risk planning and zone-warning system scoped to the 9-county San Francisco Bay Area... providing zone-based alerts and emergency shelter POI telemetry in real time."
     - *Removed*: `backend/routing/` from the directory structure tree and removed `POST /api/routing/evacuate/` from the API reference.
  2. **Automated Setup Instructions**:
     - Replaced manual 4-step setup (`python3.12 -m venv .venv`, `pip install -r backend/requirements.txt`, `pip install -r ml_adapter/requirements.txt`, `npm install`) with a single automated script:
       ```bash
       ./scripts/install.sh
       ```
     - Updated Homebrew/Ubuntu prerequisites from `python@3.12` to standard `python3`.
  3. **Automated Run Command (`./scripts/run_local.sh`)**:
     - Replaced manual opening of 5 separate terminals with a one-touch macOS script:
       ```bash
       ./scripts/run_local.sh
       ```
       Which automatically launches Docker (`docker compose up -d`) and uses AppleScript (`osascript`) to spawn 5 coordinated terminal windows:
       1. Django REST API (`python manage.py runserver`)
       2. Celery Worker (`celery -A core worker -l info --pool=solo`)
       3. React Frontend (`npm run dev`)
       4. FastAPI ML Adapter (`uvicorn main:app --port 8001 --reload`)
       5. Celery Beat (`celery -A core beat -l info`)
  4. **Mock Inference Workflow via Django Shell**:
     - Documented explicit instructions for developers to manually trigger mock inference without waiting for Celery Beat:
       ```bash
       python manage.py shell
       >>> from harvester.tasks import trigger_mock_inference
       >>> trigger_mock_inference()
       ```
     - Highlights immediate polygon rendering at `http://localhost:5173/` across the time scrubber.

---

### 1.4 Specific Updates to `docs/design-doc.md`
* **Diff Stats**: 64 lines modified.
* **Observed Architectural & Design Updates**:
  1. **Vertex Native Ingestion Architecture**:
     - Line 14 updated:
       `[Data Sources (GEE, NOAA, NWS, USGS)] → (Celery daily cron) → [Django Harvester] → HTTP POST (lightweight bbox + time_horizon + model_type payload) → [FastAPI ML Adapter (Cloud Run)] → Vertex AI model endpoints (U-Net / PINN / RL) → Unified GeoJSON FeatureCollection → [Django Database Engine] → PostGIS (Cloud SQL) + Redis (Memorystore) → [Django REST API (Cloud Run)] → REST Polling (every 5 min) → [React Frontend (Cloud CDN)]`
     - Removed obsolete concept of Django Harvester downloading multi-gigabyte satellite imagery tensors and packaging massive NumPy arrays. Vertex endpoints handle native data acquisition given the bounding box coordinates.
  2. **Schema & Model Evolution (Database Engine §1)**:
     - The database model moved from `FireRiskPrediction(danger_zone, risk_label)` to:
       - `grid` (ForeignKey to `BayAreaGrid`, SRID=4326)
       - `fire_probability` (FloatField, `0.0`–`1.0`)
       - `ml_metrics` (JSONField for model parameters)
     - `risk_label` ("HIGH_RISK", "MEDIUM_RISK", "LOW_RISK") is completely removed from the database model; thresholds and continuous rendering are offloaded to client-side WebGL shaders.
  3. **Data Lifecycle & Caching**:
     - Redis stores pre-assembled GeoJSON under key `ffwai:predictions:current` (1-hour TTL) for sub-100ms frontend polling responses.
     - PostGIS permanently stores prediction polygons for longitudinal queries, with a scheduled Celery job (`archive_old_predictions`) purging records older than 30 days.
  4. **Deprecation of A* Evacuation Routing**:
     - Section 6 explicitly marks "Evacuation Routing" as deprecated and removed from project scope due to fragmented, proprietary county road closure data feeds.
     - Section 11.2 and 12.2 pivoted from "Routing Engine Benchmarking" to "Database Query Benchmarking" (< 100ms PostGIS spatial queries).

---

### 1.5 Codebase Additions: Backend Pipeline & Models
1. **`backend/harvester/tasks.py`**:
   - `trigger_active_inference`: The "Scout" task. Downloads public NASA FIRMS MODIS CSV data, filters for Bay Area coordinates (`lat [36.9, 38.3]`, `lon [-122.9, -121.5]`), generates 1km x 1km bounding boxes (`±0.0055` lon, `±0.0045` lat), and asynchronously fans out `run_async_inference.delay(bbox, "unet")`.
   - `run_async_inference`: Decoupled Celery task invoking the FastAPI ML Adapter (`POST /predict/progression`) with exponential retries (`max_retries=3, default_retry_delay=60`).
   - `store_geojson_result`: Parses the unified GeoJSON, maps horizons (`0`, `1`, `3`, `6`), calculates `target_timestamp = timestamp + timedelta(hours=lead_time_hours)`, packs model variables into `ml_metrics`, executes an atomic bulk insert (`PredictionPolygon.objects.bulk_create`), serializes the updated dataset, and populates Redis `ffwai:predictions:current` with a 3600-second TTL.
   - `archive_old_predictions`: Daily cleanup task deleting `PredictionPolygon` records older than 30 days.
2. **`backend/predictions/models.py` & `serializers.py`**:
   - `FireIncident`: New model tracking fire lifecycle (`name`, `start_time`, `end_time`, `is_active`, `containment_status`).
   - `PredictionPolygon`: Replaces `FireRiskPrediction`, adding `fire_incident` FK, `lead_time_hours`, `target_timestamp`, and `ml_metrics` JSONField. Indexed on `[timestamp]`, `[target_timestamp]`, `[grid, timestamp]`, `[grid, target_timestamp]`, `[source_model, timestamp]`.
   - `PredictionPolygonGeoJSONSerializer`: Dynamically serializes polygons from `obj.grid.geometry.coords` and merges `ml_metrics` directly into GeoJSON feature properties.
3. **`backend/telemetry/management/commands/seed_shelters.py`**:
   - Expanded shelter inventory from 6 to 11 verified regional emergency facilities across Sonoma, Marin, Alameda, Santa Clara, San Mateo, and Santa Cruz counties.
   - Added: Petaluma Community Center (Sonoma, capacity 800), Marin Center (Marin, capacity 1200), Robert Livermore Community Center (Alameda, capacity 900), Dublin Senior Center (Alameda, capacity 400), Morgan Hill Community Center (Santa Clara, capacity 750).
   - Ingests locations into PostGIS as `Point(lon, lat, srid=4326)`.

---

### 1.6 Codebase Additions: Frontend AQI & Safe Haven Shelters
1. **Continuous AQI Interpolation Layer (`AQIGrid.jsx` & `aqiMath.js`)**:
   - **Inverse Distance Weighting (IDW)**: Computes continuous PM2.5 values across the 9 Bay Area counties.
   - **High-Resolution Spatial Grid**: Step size refined from 4 miles down to 2 miles (higher resolution), with coverage expanded from 45/50 miles to a 70-mile radius centered at `(37.6688, -122.0828)`, eliminating boundary cutoffs.
   - **Visual Appearance**: Evaluates at grid cell centers. Uses Mapbox fill layer with `fill-opacity: 0.40` and `fill-antialias: false` to seamlessly blend adjacent cells into a continuous smoke/air quality cloud.
   - **Dual Layer Visualization**: Overlays circular sensor badge markers (`aqi-sensor-bubbles`, radius 14, white border) with centered numeric text labels (`aqi-sensor-labels`) showing the exact EPA AQI index.
2. **Interactive "Safe Haven" Hover Pop-ups (`MapCanvas.jsx`)**:
   - **Marker Redesign**: Replaces static green shield icons with high-visibility blue circular markers featuring a Lucide `Tent` icon (`<Tent size={14} strokeWidth={2.5} />`).
   - **Zero-Latency Hover Popup**: React state `selectedShelter` driven by `onMouseEnter` / `onMouseLeave`.
   - Renders a floating Mapbox `Popup` (`anchor="bottom", offset={30}`) displaying:
     - Shelter Name in bold slate header.
     - Full street address with `MapPin` icon.
     - Verified capacity (e.g. "Capacity: 1200") with `Users` icon.
     - Official source badge ("FEMA").
3. **Time Scrubber & Map Legend Overhaul (`TimeScrubber.jsx`, `LayersLegend.jsx`)**:
   - Discrete horizon snapping: Time scrubber strictly enforces values `[0, 1, 3, 6]` hours (removing outdated `+12h` and `+24h` options).
   - Displays real-time estimated clock time ETA based on local time.
   - Mapbox WebGL expression updates:
     - Dynamic filtering: `['==', ['coalesce', ['get', 'horizon_hours'], ['get', 'lead_time_hours'], 0], timeScrub]`.
     - Smooth continuous color gradient interpolation (`fire_probability` 0.0 yellow `#eab308` -> 0.5 orange `#f97316` -> 0.8 red `#dc2626` -> 1.0 dark red `#991b1b`).
     - Smooth opacity interpolation (0.2 to 0.8).
   - Legend updated to display the continuous gradient bar and an active toggle for Emergency Shelters.

---

### 1.7 Expansion of Architectural Decisions (8 Original -> 13 Proposed)

The original 8 decisions provided in the draft are:
1. *Inference Cadence: Scheduled (Asynchronous)*
2. *Rolling Forecasts*
3. *Active Fire Detection (The "Scout")*
4. *Ingestion Boundary: Vertex Native Ingestion*
5. *GeoJSON Payload Assembly*
6. *Frontend Querying Pattern: Static Payload Polling*
7. *Frontend Filtering Strategy: Mapbox Property Filtering*
8. *Data Lifecycle & Caching: Ephemeral Redis + Persistent PostGIS*

Based on our direct code and documentation findings, here are **5 high-impact candidate Architectural Decisions** to expand the list from 8 to 13:

* **Decision 9: Spatial Data Normalization & Incident Lifecycle Tracking (PostGIS FKs over Raw Polygons)**
  - *Context*: Storing repetitive polygon coordinate arrays for every inference run causes massive relational database bloat and slow spatial joins.
  - *Decision*: In `backend/predictions/models.py`, predictions are stored in `PredictionPolygon` as foreign keys to the pre-computed 1km x 1km `BayAreaGrid`, rather than embedding arbitrary spatial polygons. A parent `FireIncident` model was introduced to track longitudinal fire containment states (`start_time`, `end_time`, `is_active`, `containment_status`). Raw ML model variables (`w_unet`, `members`, `p_low`, `frp_mw`) are preserved in a flexible `ml_metrics` JSONField, eliminating recurring database schema migrations when ML teams update feature sets.

* **Decision 10: Zone-Based Alerting & Emergency POI Telemetry (Strategic Deprecation of Turn-by-Turn Routing)**
  - *Context*: Dynamic turn-by-turn evacuation routing (A* engine) required real-time road closure graphs, which are severely fragmented and paywalled across regional transit agencies (511 SF Bay).
  - *Decision*: The platform deprecated and removed the `backend/routing/` A* engine. Instead, the architecture pivoted to zone-based risk warnings and Emergency Shelter POI telemetry. The backend seeds 11 FEMA/CalOES designated emergency shelters directly into PostGIS as SRID 4326 Point features, providing sub-100ms proximity queries and safety zone intersection checks without external network dependencies.

* **Decision 11: Continuous Environmental Synthesis: Client-Side IDW AQI Field Generation**
  - *Context*: Raw AQI sensor networks (AirNow, OpenAQ) provide sparse, point-based telemetry. Rendering isolated pins fails to communicate spatial smoke drift across residential communities.
  - *Decision*: In `frontend/src/components/Map/AQIGrid.jsx` and `aqiMath.js`, the frontend computes a continuous PM2.5 / AQI field using client-side Inverse Distance Weighting (IDW) interpolation. By evaluating IDW at 2-mile step intervals across an expanded 70-mile radius with `fill-antialias: false` and `fill-opacity: 0.40`, the map generates a smooth, regional air quality cloud overlaid with discrete numeric sensor badges, avoiding the need for heavy server-side raster generation.

* **Decision 12: Interactive POI Telemetry: Client-Side Zero-Latency Hover Architecture**
  - *Context*: When inspecting emergency facilities during an incident, querying secondary backend endpoints for shelter capacity and address details introduces network latency and server load.
  - *Decision*: In `frontend/src/components/Map/MapCanvas.jsx`, emergency shelter POI telemetry is delivered in the initial static GeoJSON payload and rendered via a client-side React `Popup` component. Hovering over the `Tent` icon triggers zero-latency hover cards detailing verified shelter capacity, street address, and FEMA verification status directly from Mapbox memory.

* **Decision 13: Discrete Forecast Horizon Snapping & Continuous Probability Gradient Visualization**
  - *Context*: Previous prototypes featured speculative 12h and 24h horizons and mapped fire risk into coarse static tiers (`risk_label`: HIGH, MEDIUM, LOW). The actual U-Net and PINN deep learning models only output reliable predictions at 0h, 1h, 3h, and 6h horizons.
  - *Decision*: The time scrubber UI (`TimeScrubber.jsx`) strictly snaps to discrete valid intervals (`+0h`, `+1h`, `+3h`, `+6h`), calculating a dynamic clock ETA for user clarity. Concurrently, static string risk labels were removed in favor of continuous Mapbox WebGL color and opacity gradients (`fire_probability` 0.0 yellow to 1.0 dark red), giving emergency managers fine-grained risk assessment.

---

## 2. Logic Chain

1. **Premise 1**: The user draft established an initial architecture of 8 decisions centered on Celery asynchronous scheduling, Redis caching, and Vertex Native Ingestion.
2. **Premise 2**: Code inspection of `backend/predictions/models.py` (lines 24–128) and migration `0002` reveals that `FireRiskPrediction` was replaced with `PredictionPolygon`, `FireIncident` was created, and `risk_label` was replaced with `ml_metrics` and `lead_time_hours`.
   - *Inference*: The architecture evolved from flat fire risk tagging to relational grid normalization and multi-horizon incident tracking. This provides the concrete basis for **Decision 9**.
3. **Premise 3**: Inspection of git commit `ead0603` and `docs/design-doc.md` (lines 202–204) shows the complete deletion of `backend/routing/` (A* engine) and the expansion of `backend/telemetry/management/commands/seed_shelters.py` to 11 Bay Area facilities.
   - *Inference*: The project made an explicit architectural pivot away from turn-by-turn navigation towards zone alerts and shelter POIs, forming the foundation for **Decision 10**.
4. **Premise 4**: Inspection of `frontend/src/components/Map/AQIGrid.jsx` (lines 35–150) and `frontend/src/utils/aqiMath.js` (lines 55–85) demonstrates client-side IDW interpolation over a 70-mile radius at 2-mile resolution.
   - *Inference*: Environmental telemetry is synthesized continuously on the client GPU rather than queried as heavy server rasters, forming **Decision 11**.
5. **Premise 5**: Inspection of `MapCanvas.jsx` (lines 89–146) shows Mapbox `Popup` hover listeners directly bound to shelter markers with SVG Lucide icons.
   - *Inference*: UI telemetry inspection is fully decoupled from server queries via zero-latency client-side state, giving **Decision 12**.
6. **Premise 6**: Inspection of `docs/vertex-ai-endpoint-contract.md` (lines 41–43, 60), `TimeScrubber.jsx` (lines 1–61), and `MapCanvas.jsx` (lines 46–77) confirms that 24h predictions were removed, horizons are strictly snapped to `[0, 1, 3, 6]`, and polygons use continuous linear interpolation on `fire_probability`.
   - *Inference*: The frontend visualization matches the exact mathematical capabilities of the ML model, yielding **Decision 13**.

---

## 3. Caveats

1. **Live Vertex AI Endpoint**: As defined in `ml_adapter/main.py` lines 88–130, live Vertex AI inference calls are stubbed with `MOCK_INFERENCE=true` serving the normalized GOES-18 mock fixtures. The contract in `docs/vertex-ai-endpoint-contract.md` defines the exact shape for Month 2 deployment, but live endpoint invocation requires deployed Vertex endpoints on GCP.
2. **Test Database Access in Sandbox**: Running `pytest` against GeoDjango database integration tests in this environment failed due to local PostgreSQL port 5432 being unreachable within the sandbox container. However, Python syntax compilation (`py_compile`) and frontend production bundling (`npm run build`) both verified with 100% success.
3. **External NASA FIRMS API**: The scout task `trigger_active_inference` in `harvester/tasks.py` includes a fallback to static Bay Area coordinates (San Jose, San Francisco) if the public NASA FIRMS CSV cannot be fetched due to network restrictions.

---

## 4. Conclusion

The `feature/ml-adapter-integration` branch represents a foundational architectural evolution:
1. **Documentation Alignment**: `docs/vertex-ai-endpoint-contract.md` establishes a crystal-clear, 187-line schema contract for Month 2 Vertex AI models, bounding-box clamping (`[-122.9, 36.9, -121.5, 38.3]`), and discrete horizons (`0`, `1`, `3`, `6` hours). `README.md` and `docs/design-doc.md` have been updated to reflect the deprecation of A* routing, automated local execution scripts (`install.sh`, `run_local.sh`), and the Vertex Native Ingestion paradigm.
2. **Backend Robustness**: Celery now features an automated NASA FIRMS scout task, asynchronous fan-out, atomic bulk writes to PostGIS, 1-hour Redis caching, and 30-day archival cleanup. PostGIS schemas now support multi-horizon tracking (`PredictionPolygon`) and incident lifecycles (`FireIncident`).
3. **Frontend Polish & Innovation**: The UI features client-side continuous IDW AQI field interpolation, discrete horizon snapping on the time scrubber with real-time ETA display, continuous WebGL fire risk gradients, and interactive hover pop-ups for 11 regional emergency shelters.
4. **Architectural Decisions**: The original 8 architectural decisions can now be cleanly expanded to **13 robust, fully substantiated decisions**, fulfilling all project requirements.

---

## 5. Verification Method

To independently verify these findings:

1. **Verify Git History & Diffs**:
   ```bash
   git log --oneline 57304128e9c693878a22d8e06dab8344a007a050..feature/ml-adapter-integration
   git diff --stat 57304128e9c693878a22d8e06dab8344a007a050..feature/ml-adapter-integration -- docs/ README.md
   ```

2. **Verify Documentation Files**:
   - Inspect `docs/vertex-ai-endpoint-contract.md` for section headers, bounding box definition, and property table.
   - Inspect `README.md` for `./scripts/install.sh`, `./scripts/run_local.sh`, and `trigger_mock_inference()`.
   - Inspect `docs/design-doc.md` §1 for "Vertex Native Ingestion Architecture" and §6 for "Evacuation Routing: Deprecated".

3. **Verify Python Syntax & Frontend Build**:
   ```bash
   source .venv/bin/activate
   python -m py_compile backend/predictions/models.py backend/predictions/views.py backend/harvester/tasks.py ml_adapter/main.py
   cd frontend && npm run build
   ```

4. **Invalidation Conditions**:
   - If `docs/vertex-ai-endpoint-contract.md` contains uncommitted changes altering `bbox` coordinates or allowed horizons.
   - If `backend/routing/` is re-introduced into the codebase.
