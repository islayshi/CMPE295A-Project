## 2026-10-06T19:49:59Z
Read /Users/earlpadron/Desktop/Spring 2026 Courses/CMPE 295A/CMPE295A-Project/.agents/teamwork/ORIGINAL_REQUEST.md.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Your working directory for metadata and progress is:
/Users/earlpadron/Desktop/Spring 2026 Courses/CMPE 295A/CMPE295A-Project/.agents/teamwork/teamwork_preview_worker_1

You EXCLUSIVELY own and must write the target deliverable file:
/Users/earlpadron/Desktop/Spring 2026 Courses/CMPE 295A/CMPE295A-Project/MERGE_REQUEST_DESCRIPTION.md

Read the three Explorer handoff reports thoroughly before drafting:
1. Backend Explorer report: /Users/earlpadron/Desktop/Spring 2026 Courses/CMPE 295A/CMPE295A-Project/.agents/teamwork/teamwork_preview_explorer_backend/handoff.md
2. Frontend Explorer report: /Users/earlpadron/Desktop/Spring 2026 Courses/CMPE 295A/CMPE295A-Project/.agents/teamwork/teamwork_preview_explorer_frontend/handoff.md
3. Docs & Architecture Explorer report: /Users/earlpadron/Desktop/Spring 2026 Courses/CMPE 295A/CMPE295A-Project/.agents/teamwork/teamwork_preview_explorer_docs/handoff.md

Your task is to craft a comprehensive, production-grade Merge Request description in Markdown for the `feature/ml-adapter-integration` branch into `main`.

Ensure all requirements and acceptance criteria in ORIGINAL_REQUEST.md are strictly fulfilled:
1. Include the EXACT original "Goal Description" verbatim:
```
Goal Description
The ML team provided Jupyter notebooks detailing the U-Net and PINN models. Our goal is to architect a scalable integration between Django, FastAPI, and Vertex AI. We have shifted to a Scheduled Asynchronous Pipeline, utilizing Celery as a scout to query active fires and caching the resulting ML predictions for lightning-fast frontend delivery.
```
2. Include at least 10 Architectural Decisions (incorporate the original 8 verbatim/adapted, plus at least 5 new architectural decisions formulated from recent backend, data, and frontend additions, totaling 13 decisions):
   - Decision 1: Inference Cadence: Scheduled (Asynchronous)
   - Decision 2: Rolling Forecasts
   - Decision 3: Active Fire Detection (The "Scout")
   - Decision 4: Ingestion Boundary: Vertex Native Ingestion
   - Decision 5: GeoJSON Payload Assembly
   - Decision 6: Frontend Querying Pattern: Static Payload Polling
   - Decision 7: Frontend Filtering Strategy: Mapbox Property Filtering
   - Decision 8: Data Lifecycle & Caching: Ephemeral Redis + Persistent PostGIS
   - Decision 9: Spatial Data Normalization & Incident Lifecycle Tracking (PostGIS FKs over Raw Polygons)
   - Decision 10: Zone-Based Alerting & Emergency POI Telemetry (Strategic Deprecation of Turn-by-Turn Routing)
   - Decision 11: Continuous Environmental Synthesis: Client-Side IDW AQI Field Generation
   - Decision 12: Interactive POI Telemetry: Client-Side Zero-Latency Hover Architecture
   - Decision 13: Discrete Forecast Horizon Snapping & Continuous Probability Gradient Visualization
3. Detail Recent Codebase Additions with concrete file paths, functions, models, and algorithms:
   - Backend:
     - Celery pipeline: Beat schedules in settings.py (`crontab` 06:00 UTC daily inference, midnight UTC 30-day archival, 30-min active inference); active fire "Scout" task (`trigger_active_inference`) downloading NASA FIRMS MODIS C6.1 CSV feed, Bay Area spatial filtering (`lat [36.9, 38.3]`, `lon [-122.9, -121.5]`), 1 km × 1 km dynamic bounding box calculation, network fallback to mock coords, and async fan-out via `run_async_inference.delay(bbox, "unet")`; inference execution task (`run_async_inference`) calling FastAPI ML Adapter (`POST /predict/progression`) with retries; worker startup hydration hook (`on_worker_ready`); result storage (`store_geojson_result`) with auto-stubbing missing `BayAreaGrid` cells, `target_timestamp` calculation, `ml_metrics` packing, atomic bulk creation of `PredictionPolygon`, and Redis caching under `ffwai:predictions:current` (1h TTL).
     - PostGIS models & migrations: `PredictionPolygon` replacing `FireRiskPrediction` via migrations `0002` and `0003`, `lead_time_hours` (0, 1, 3, 6), `target_timestamp`, `ml_metrics` JSONField, `FireIncident` model for tracking fire status/containment, spatial/temporal indexes, 1.0 km grid resolution in `generate_grid.py`.
     - `seed_shelters` management command: Expanded from 6 to 11 emergency shelters across 6 Bay Area counties (Alameda, Santa Clara, San Mateo, Santa Cruz, Sonoma, Marin), WGS84 Point geometries (`srid=4326`), capacity, address, idempotent `get_or_create`.
     - Deprecation and excision of `backend/routing/`: Full deletion of routing directory, settings/urls cleanup, regression tests in `backend/api/tests.py` asserting 404 and unimportable module.
     - Views & Serializers: `current_predictions` Redis O(1) query with DB fallback, `PredictionPolygonGeoJSONSerializer` dynamically unpacking `ml_metrics` into top-level Feature properties.
   - Frontend:
     - Continuous AQI Interpolation Layer: Mapbox GL JS native implementation (`react-map-gl/mapbox` Source and Layer in `AQIGrid.jsx`, not Deck.gl), 2-mile high-resolution IDW grid over 70-mile radius centered at Hayward, `fill-antialias: false` with removed boundary lines to render a smooth continuous raster-like cloud fill, exact station ground-truth bubble overlay with EPA numbers, official 6-tier EPA color scale in `aqiMath.js`, 5-minute REST polling from `/telemetry/aqi/`, interactive toggle switch in `LayersLegend.jsx`.
     - Interactive "Safe Haven" Emergency Shelter Pop-ups: Circular `Tent` icon marker badges in `MapCanvas.jsx`, hover-triggered Mapbox `Popup` cards displaying shelter name, physical address (`MapPin`), capacity (`Users`), and data source badge ("FEMA"), state managed in `Dashboard.jsx`, toggle switch in `LayersLegend.jsx`.
     - Timeline Slider & Mapbox Property Filtering: `TimeScrubber.jsx` snapping strictly to valid ML horizons `[0, 1, 3, 6]` with dynamic clock ETA and active pulsing radar beacon; Mapbox WebGL expression `['==', ['coalesce', ['get', 'horizon_hours'], ['get', 'lead_time_hours'], 0], timeScrub]` for 0ms network latency scrubbing; continuous linear color interpolation for fire probability (`0.0 -> #eab308` to `1.0 -> #991b1b`).
     - Navigation & UI Theme: Modern segmented control pill navbar in `Navbar.jsx`, strict California Ember 60-30-10 palette adherence.
   - Documentation Updates:
     - Section detailing changes made to `docs/vertex-ai-endpoint-contract.md` (new 187-line Month 2 contract, `PredictionRequest` payload, bounding box clamping to `[-122.9, 36.9, -121.5, 38.3]`, Mapbox property schema, unified single-response FeatureCollection, discrete horizons `[0, 1, 3, 6]`, version header `X-Contract-Version: 2026-10-05`).
     - Section detailing changes made to `README.md` (scope realignment removing A* routing and highlighting zone warnings/shelters, one-touch automated setup via `./scripts/install.sh`, 5-terminal runner via `./scripts/run_local.sh`, and Django shell mock inference triggering).
     - Section detailing changes made to `docs/design-doc.md` (Vertex Native Ingestion architecture, retirement of heavy NumPy tensor pipelines, schema evolution to `PredictionPolygon` with `ml_metrics`, 1h Redis caching, 30-day PostGIS data lifecycle, and routing engine benchmark pivot to DB query benchmark).
4. Include a comprehensive "Verification and Testing" section documenting verified tests, frontend build (`npm run build`), python syntax checks, and regression tests.
5. Create and write the file to `/Users/earlpadron/Desktop/Spring 2026 Courses/CMPE 295A/CMPE295A-Project/MERGE_REQUEST_DESCRIPTION.md`.
6. Write your handoff report to `/Users/earlpadron/Desktop/Spring 2026 Courses/CMPE 295A/CMPE295A-Project/.agents/teamwork/teamwork_preview_worker_1/handoff.md`.
7. Send a message to parent reporting completion and referencing the deliverable path.
