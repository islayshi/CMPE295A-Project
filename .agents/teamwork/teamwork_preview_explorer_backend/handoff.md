# Backend Investigation Report: `feature/ml-adapter-integration`

## 1. Observation

All observations are derived from Git analysis (`git log`, `git diff main..feature/ml-adapter-integration`) and direct source code examination in the repository.

### 1.1 Celery Pipeline Additions & Modifications

#### Configuration & Schedules (`backend/core/settings.py`)
- **Import added**:
  ```python
  from celery.schedules import crontab
  ```
  (`backend/core/settings.py:20`)
- **Celery Beat Schedule updates** (`backend/core/settings.py:156-181`):
  ```python
  CELERY_BEAT_SCHEDULE = {
      "trigger-daily-inference": {
          "task": "harvester.tasks.trigger_daily_inference",
          "schedule": crontab(minute=0, hour=6),  # 06:00 UTC daily
      },
      "fetch-wind-data-hourly": {
          "task": "harvester.tasks.fetch_wind_data",
          "schedule": 3600,  # 1 hour in seconds
      },
      "fetch-aqi-data-30min": {
          "task": "harvester.tasks.fetch_aqi_data",
          "schedule": 1800,  # 30 minutes in seconds
      },
      "fetch-nws-alerts-15min": {
          "task": "harvester.tasks.fetch_nws_alerts",
          "schedule": 900,  # 15 minutes in seconds
      },
      "archive-old-predictions-nightly": {
          "task": "harvester.tasks.archive_old_predictions",
          "schedule": crontab(minute=0, hour=0),
      },
      "trigger-active-inference-30min": {
          "task": "harvester.tasks.trigger_active_inference",
          "schedule": 1800,  # 30 minutes in seconds
      },
  }
  ```
  Key changes:
  1. `trigger-daily-inference` shifted from interval `86400` to cron schedule `crontab(minute=0, hour=6)` (06:00 UTC).
  2. New task `archive-old-predictions-nightly` added at midnight UTC (`crontab(minute=0, hour=0)`).
  3. New task `trigger-active-inference-30min` added every 30 minutes (1800s).

#### Active Fire Scout Task (`backend/harvester/tasks.py:794-854`)
- **Task**: `trigger_active_inference` (`@shared_task(name="harvester.tasks.trigger_active_inference", bind=True, max_retries=3, default_retry_delay=60)`)
- **External Data Source**: Queries NASA FIRMS public MODIS C6.1 CSV feed:
  `https://firms.modaps.eosdis.nasa.gov/data/active_fire/modis-c6.1/csv/MODIS_C6_1_USA_contiguous_and_Hawaii_24h.csv`
- **Spatial Filtering**: Restricts active fire detections to the San Francisco Bay Area bounding box:
  `lat_min, lat_max = 36.9, 38.3`, `lon_min, lon_max = -122.9, -121.5`.
- **Fault-Tolerant Fallback**: If network fails or CSV headers are invalid, gracefully falls back to mock coordinates:
  - San Jose: `(37.3382, -121.8863)`
  - San Francisco: `(37.7749, -122.4194)`
- **Dynamic Bounding Box Calculation**: Converts fire coordinate into a 1 km × 1 km bounding box:
  - Latitude offset: `0.0045°` (~0.5 km)
  - Longitude offset: `0.0055°` (~0.5 km at 37°N)
  - Formula:
    ```python
    bbox = [
        round(lon - 0.0055, 4), round(lat - 0.0045, 4),
        round(lon + 0.0055, 4), round(lat + 0.0045, 4)
    ]
    ```
- **Asynchronous Fan-Out**: Fires `run_async_inference.delay(bbox, "unet")` for each detected fire coordinate.

#### Asynchronous Inference Execution Task (`backend/harvester/tasks.py:764-792`)
- **Task**: `run_async_inference(bbox, model_type="unet")` (`@shared_task(name="harvester.tasks.run_async_inference", bind=True, max_retries=3, default_retry_delay=60)`)
- **FastAPI Integration**: Makes HTTP POST to `{settings.ML_ADAPTER_URL}/predict/progression`:
  ```python
  payload = {
      "bbox": bbox,
      "time_horizon": 24,
      "model_type": model_type,
      "mock": settings.MOCK_INFERENCE
  }
  response = requests.post(url, json=payload, timeout=120)
  ```
- **Persistence Call**: Invokes `store_geojson_result(geojson_result)` upon successful response.

#### Development / Mock Trigger Task (`backend/harvester/tasks.py:856-865`)
- **Task**: `trigger_mock_inference()` (`@shared_task(name="harvester.tasks.trigger_mock_inference", bind=True)`)
- Bypasses NASA FIRMS scraping and instantly dispatches `run_async_inference.delay([-122.5, 37.5, -122.4, 37.6], "unet")`.

#### Data Archival Task (`backend/harvester/tasks.py:867-882`)
- **Task**: `archive_old_predictions()` (`@shared_task(name="harvester.tasks.archive_old_predictions")`)
- Deletes `PredictionPolygon` records older than 30 days (`threshold_date = datetime.now(timezone.utc) - timedelta(days=30)`):
  ```python
  old_predictions = PredictionPolygon.objects.filter(timestamp__lt=threshold_date)
  deleted_count, _ = old_predictions.delete()
  ```

#### Startup Hydration Hook (`backend/harvester/tasks.py:752-762`)
- **Signal**: Connected to Celery `@worker_ready.connect`:
  ```python
  @worker_ready.connect
  def on_worker_ready(sender, **kwargs):
      fetch_aqi_data.delay()
      fetch_wind_data.delay()
      fetch_nws_alerts.delay()
  ```
  Immediately hydrates Redis cache with telemetry upon worker startup so initial frontend load is not blank.

#### Result Storage & Ingestion (`backend/harvester/tasks.py:178-288`)
- **Function**: `store_geojson_result(geojson: dict) -> int`
- **Dynamic Grid Stubbing**:
  ```python
  incoming_grid_ids = [
      f.get("properties", {}).get("grid_id") 
      for f in features 
      if f.get("properties", {}).get("grid_id") is not None
  ]
  if incoming_grid_ids:
      existing_grid_ids = set(BayAreaGrid.objects.filter(id__in=incoming_grid_ids).values_list("id", flat=True))
      missing_grid_ids = set(incoming_grid_ids) - existing_grid_ids
      if missing_grid_ids:
          # Automatically stubs missing BayAreaGrid cells with geometry and centroid from feature!
  ```
- **Horizon & Lead Time Processing**:
  - Extracts `lead_time_hours` from `horizon_hours` property (defaulting to 0).
  - Computes `target_timestamp = timestamp + dt.timedelta(hours=lead_time_hours)`.
- **Flexible ML Metrics Storage**:
  - Captures extra ML metrics into `ml_metrics` JSONField:
    ```python
    ml_metrics = {k: v for k, v in props.items() if k not in ("grid_id", "fire_probability", "source_model", "timestamp", "horizon_hours")}
    ```
- **Atomic Persistence & Redis Assembly**:
  ```python
  with transaction.atomic():
      PredictionPolygon.objects.bulk_create(predictions_to_create, ignore_conflicts=True)

  if timestamp:
      valid_polygons = PredictionPolygon.objects.filter(timestamp=timestamp).select_related("grid")
      serializer = PredictionPolygonGeoJSONSerializer(valid_polygons, many=True)
      feature_collection = {
          "type": "FeatureCollection",
          "metadata": {"timestamp": target_timestamp.isoformat(), "total_cells": valid_polygons.count()},
          "features": serializer.data,
      }
      cache.set("ffwai:predictions:current", json.dumps(feature_collection), timeout=3600)
  ```

---

### 1.2 PostGIS Models & Migrations

#### `PredictionPolygon` (`backend/predictions/models.py:40-128`)
Replaced `FireRiskPrediction` model via Django migrations `0002` and `0003`:
- **Model Fields**:
  - `grid`: `ForeignKey(BayAreaGrid, on_delete=models.CASCADE, related_name="predictions")`
  - `fire_incident`: `ForeignKey(FireIncident, on_delete=models.SET_NULL, null=True, blank=True, related_name="predictions")`
  - `timestamp`: `DateTimeField(db_index=True)` (inference run time)
  - `lead_time_hours`: `IntegerField(default=0)` (horizon: 0, 1, 3, 6 hours)
  - `target_timestamp`: `DateTimeField(null=True, blank=True, db_index=True)` (valid timestamp for future state)
  - `source_model`: `CharField(max_length=50, choices=SOURCE_MODEL_CHOICES)`
  - `fire_probability`: `FloatField()` (0.0 to 1.0)
  - `ml_metrics`: `JSONField(null=True, blank=True)` (stores raw model weights/metrics: `p_low`, `w_unet`, `frp_mw`, `p_unet`, `members`)
  - `created_at`: `DateTimeField(auto_now_add=True, db_index=True)`
- **Database Indexes**:
  - `Index(fields=["timestamp"])`
  - `Index(fields=["target_timestamp"])`
  - `Index(fields=["grid", "timestamp"])`
  - `Index(fields=["grid", "target_timestamp"])`
  - `Index(fields=["source_model", "timestamp"])`
- **Ordering**: `ordering = ["-timestamp", "lead_time_hours"]`

#### `FireIncident` (`backend/predictions/models.py:24-38`)
New model introduced to track active fire incident lifecycles:
- `name`: `CharField(max_length=255, blank=True)`
- `start_time`: `DateTimeField(db_index=True)`
- `end_time`: `DateTimeField(null=True, blank=True)`
- `is_active`: `BooleanField(default=True, db_index=True)`
- `containment_status`: `FloatField(null=True, blank=True)` (0.0 to 100.0)
- Ordering: `ordering = ["-start_time"]`

#### `EmergencyShelter` (`backend/telemetry/models.py:16-48`)
- `name`: `CharField(max_length=255)`
- `location`: `PointField(srid=4326)` (WGS84 GPS coordinates)
- `address`: `TextField(blank=True)`
- `county`: `CharField(max_length=100, blank=True)`
- `capacity`: `IntegerField(null=True, blank=True)`
- `source`: `CharField(max_length=50, default="FEMA")`
- Index: `Index(fields=["county"])`

#### `BayAreaGrid` (`backend/grid/models.py`) & Grid Generation (`backend/grid/management/commands/generate_grid.py:62`)
- `CELL_SIZE_KM` updated from `0.5` to `1.0` km to match the 1 km standard resolution across Vertex AI, U-Net, and FIRMS feeds.

#### Migration History (`backend/predictions/migrations/`)
- `0002_predictionpolygon_delete_fireriskprediction_and_more.py`:
  - Renamed model `FireRiskPrediction` -> `PredictionPolygon`.
  - Added `ml_metrics` JSONField.
  - Updated index names.
- `0003_fireincident_alter_predictionpolygon_options_and_more.py`:
  - Created `FireIncident` model.
  - Added `lead_time_hours`, `target_timestamp`, and `fire_incident` foreign key to `PredictionPolygon`.
  - Added indexes on `target_timestamp` and `[grid, target_timestamp]`.
  - Updated ordering to `["-timestamp", "lead_time_hours"]`.

---

### 1.3 `seed_shelters` Management Command

Located at `backend/telemetry/management/commands/seed_shelters.py`:
- **Help Text**: `'Seeds emergency shelters in the SF Bay Area for telemetry POIs.'` (updated from `'for evacuation routing'`).
- **Data Expansion**: Expanded from 6 to 11 emergency shelters across 6 Bay Area counties.
- **Shelters Seeded**:
  1. *Chabot College Emergency Shelter* — Alameda County (Hayward), capacity 500
  2. *San Jose Convention Center* — Santa Clara County (San Jose), capacity 2,000
  3. *Oakland Coliseum* — Alameda County (Oakland), capacity 5,000
  4. *San Mateo County Event Center* — San Mateo County (San Mateo), capacity 1,500
  5. *Santa Cruz County Fairgrounds* — Santa Cruz County (Watsonville), capacity 1,000
  6. *Cow Palace Arena* — San Mateo County (Daly City), capacity 3,000
  7. *Petaluma Community Center* — Sonoma County (Petaluma), capacity 800 (**New**)
  8. *Marin Center (San Rafael)* — Marin County (San Rafael), capacity 1,200 (**New**)
  9. *Robert Livermore Community Center* — Alameda County (Livermore), capacity 900 (**New**)
  10. *Dublin Senior Center* — Alameda County (Dublin), capacity 400 (**New**)
  11. *Morgan Hill Community Center* — Santa Clara County (Morgan Hill), capacity 750 (**New**)
- **Implementation & Idempotency**:
  - Uses `EmergencyShelter.objects.get_or_create(name=s["name"], defaults={...})`.
  - Safe for repeated executions during CI/CD or bootstrap without generating duplicates.
  - Points constructed using `Point(s["lon"], s["lat"], srid=4326)`.

---

### 1.4 Other Backend Additions & Modifications

#### Complete Removal / Excision of Deprecated Routing App
- Deleted directory `backend/routing/` containing `engine.py`, `views.py`, `models.py`, `serializers.py`, `urls.py`, and `tests.py`.
- Removed `"routing"` from `INSTALLED_APPS` in `backend/core/settings.py:60`.
- Removed `path("api/routing/", include("routing.urls"))` from `backend/core/urls.py:32`.
- Added regression tests in `backend/api/tests.py:7-27`:
  - `test_routing_app_not_in_installed_apps`
  - `test_routing_endpoints_return_404` (asserts `/api/routing/evacuate/` and `/api/routing/` return 404)
  - `test_routing_module_cannot_be_imported` (asserts `importlib.util.find_spec("routing") is None`)

#### Predictions API Views & Serializers
- **`current_predictions` View (`backend/predictions/views.py:33-69`)**:
  - Primary path: O(1) in-memory Redis lookup via cache key `"ffwai:predictions:current"`.
  - Cache miss fallback: Queries database for latest prediction `timestamp <= now`, fetches all polygons for that timestamp, serializes to FeatureCollection, caches in Redis with 1-hour TTL (`timeout=3600`), and returns the response.
  - Safe empty fallback: Returns `{"type": "FeatureCollection", "features": []}` if database has no records yet.
- **`PredictionPolygonGeoJSONSerializer` (`backend/predictions/serializers.py:19-53`)**:
  - Converts `PredictionPolygon` instances to standard GeoJSON Feature objects.
  - Sets `geometry` to `{"type": "Polygon", "coordinates": obj.grid.geometry.coords}`.
  - Serializes `grid_id`, `fire_probability`, `source_model`, `timestamp`, `lead_time_hours`, `horizon_hours`, `target_timestamp`.
  - Automatically unpacks `ml_metrics` dictionary into top-level properties so ML metrics (`w_unet`, `members`, `p_low`, `p_unet`, `frp_mw`) are directly accessible to Mapbox styling layers.
- **`prediction_history` View (`backend/predictions/views.py:72-120`)**:
  - Updated to query `PredictionPolygon` instead of `FireRiskPrediction`.

#### Test Suite & Configuration
- Created `backend/conftest.py` for root pytest discovery.
- Added comprehensive unit tests in `backend/predictions/tests.py` testing Redis cache retrieval and DB fallback.
- Added comprehensive unit tests in `backend/harvester/tests.py` testing `trigger_active_inference` scout parsing, bounding box calculations, network fallbacks, malformed CSV handling, and 30-day archival.
- Cleaned up redundant dependencies in `backend/requirements.txt` (`earthengine-api` and `django-cors-headers` duplicates removed).

---

## 2. Logic Chain

1. **Decoupling ML Inference from Frontend HTTP Requests (Scheduled Asynchronous Pipeline)**:
   - *Observation*: Previously, `current_predictions` attempted to call the ML Adapter synchronously via HTTP when predictions were missing.
   - *Logic*: Direct HTTP calls from web views to ML adapters cause thread starvation and timeout risks under high traffic or emergency situations. By introducing Celery Beat schedules (`trigger-active-inference-30min`, `trigger-daily-inference`), Celery becomes the active orchestrator. Views only read from the Redis cache (`cache.get("ffwai:predictions:current")`) or fall back to pre-indexed PostGIS rows, achieving O(1) read latency.

2. **Scout Architecture via Lightweight Satellite Feeds**:
   - *Observation*: `trigger_active_inference` polls NASA FIRMS MODIS CSV every 30 minutes, extracts Bay Area coordinates, computes 1 km × 1 km bounding boxes, and fans out `run_async_inference.delay(bbox, "unet")`.
   - *Logic*: Vertex AI should not be constantly processing the entire 18,000-cell grid when fire activity is sparse. The Celery scout acts as an event filter: detecting hotspots from lightweight public feeds and restricting heavy deep learning inference strictly to affected geographic regions.

3. **Multi-Horizon Schema & Rolling Forecast Support**:
   - *Observation*: Model changed from `FireRiskPrediction` to `PredictionPolygon` with `lead_time_hours`, `target_timestamp`, and `ml_metrics`. Migrations `0002` and `0003` add indexes on `target_timestamp` and `[grid, target_timestamp]`.
   - *Logic*: The U-Net and PINN models output +0h (current), +1h, +3h, and +6h spread forecasts. By storing `lead_time_hours` and computing `target_timestamp = timestamp + timedelta(hours=lead_time_hours)`, both the frontend Mapbox time-scrubber and backend historical analysis can query and render slices through time without schema redesign.

4. **Elimination of Dead / Out-of-Scope Code**:
   - *Observation*: `backend/routing/` was removed, routing urls were deleted, and `api/tests.py` explicitly tests 404 response on routing routes.
   - *Logic*: The project scope focuses on wildfire prediction, risk mapping, and telemetry (wind, AQI, shelter POIs). Removing unfinished evacuation routing code reduces technical debt, simplifies dependencies, and prevents confusion regarding core system responsibilities.

5. **Expanded POI Telemetry for UI Safe Haven Feature**:
   - *Observation*: `seed_shelters` expanded from 6 to 11 shelters across 6 counties with `get_or_create`.
   - *Logic*: The frontend introduces an interactive "Safe Haven" hover pop-up for emergency shelters. Increasing the density and geographic distribution ensures the UI displays representative emergency resources across North Bay (Marin, Sonoma), East Bay (Alameda), Peninsula (San Mateo), South Bay (Santa Clara), and Central Coast (Santa Cruz).

---

## 3. Caveats

1. **Local Database Service Requirement for Integration Tests**:
   - When executing the full test suite via `.venv/bin/pytest backend/`, tests marked `@pytest.mark.django_db` raise `OperationalError` if the local PostgreSQL/PostGIS container is not running on port 5432 (`Is the server running on that host and accepting TCP/IP connections?`). All non-DB unit tests (such as Redis cache retrieval in `predictions/tests.py` and routing regression tests in `api/tests.py`) execute and pass cleanly.
2. **NASA FIRMS Rate Limits & Network Availability**:
   - `trigger_active_inference` uses a public NASA FIRMS CSV endpoint. While a mock coordinate fallback for SF and San Jose is implemented, production deployment should consider an authenticated FIRMS MAP_KEY if polling frequency increases.
3. **Month 1 Mock Mode vs. Month 2 Vertex AI Ingestion**:
   - Currently, `run_async_inference` invokes FastAPI `/predict/progression`, which in mock mode stitches local GeoJSON fixtures (`current_fire_goes18_...`, `spread_goes_...h1/h3/h6`). Live Vertex AI deployment will use the same JSON request/response contract defined in `docs/vertex-ai-endpoint-contract.md`.

---

## 4. Conclusion

The backend additions on `feature/ml-adapter-integration` deliver the core infrastructure required for the Scheduled Asynchronous ML Pipeline:
1. **Celery Pipeline**: Scheduled scout task (`trigger_active_inference` every 30 min) querying NASA FIRMS, asynchronous fan-out (`run_async_inference`), automated 30-day archival (`archive_old_predictions`), worker startup cache hydration hook (`on_worker_ready`), and unified GeoJSON assembly.
2. **PostGIS Schema**: Upgraded to `PredictionPolygon` with multi-horizon fields (`lead_time_hours`, `target_timestamp`), flexible `ml_metrics` JSON storage, composite spatial/temporal indexes, and the new `FireIncident` tracking model.
3. **Shelter Seeding**: Enhanced `seed_shelters` management command populating 11 emergency shelters across 6 Bay Area counties.
4. **Architectural Cleanliness**: Complete deprecation and removal of the unneeded A* routing module, reinforced by automated regression tests in `backend/api/tests.py`.

---

## 5. Verification Method

To independently verify these findings, execute the following commands in the project root:

1. **Verify Git History and Diff**:
   ```bash
   git diff --stat main..feature/ml-adapter-integration -- backend/
   ```

2. **Verify Routing App Deprecation and Redis Cache Fallback Tests**:
   ```bash
   ./.venv/bin/pytest backend/api/tests.py backend/predictions/tests.py -k "test_current_predictions_from_cache or test_routing"
   ```
   *Expected Result*: 4 passed in ~0.2s.

3. **Verify Full PostGIS Test Suite (Requires Docker Compose)**:
   ```bash
   docker compose up -d db redis
   ./.venv/bin/pytest backend/
   ```

4. **Verify Management Commands**:
   ```bash
   python backend/manage.py seed_shelters --dry-run # or inspect command directly
   ```

5. **Files to Inspect Directly**:
   - `backend/core/settings.py` (lines 20, 60-63, 156-181)
   - `backend/harvester/tasks.py` (lines 178-288, 752-882)
   - `backend/predictions/models.py` (lines 24-128)
   - `backend/predictions/serializers.py` (lines 19-53)
   - `backend/predictions/views.py` (lines 33-69)
   - `backend/telemetry/management/commands/seed_shelters.py` (lines 8-93)
   - `docs/vertex-ai-endpoint-contract.md` (lines 1-187)
