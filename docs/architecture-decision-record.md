## ADR-001: Replace FireGAN with UNET model and Physics informed neural network. 

**Date:** 2026-09-08

**Context:** FireGAN was designed for downscaling GOES data to 500m resolution,
but we are now changing machine learning models for fire detection/spread prediction.
The two AI and machine learning students on my 4-person team have decided to migrate to different techniques rather than downscaling satellite imagery. 

Here are some of the data sources they are considering in researching to include as features for the models :"| Factor                                  | Recommended current source                                      | What we should take from it                                                                             | Project role                                                   | Priority                            |
| --------------------------------------- | --------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------- | ----------------------------------- |
| **1. Real-time thermal/fire detection** | **NASA FIRMS – VIIRS NOAA-20/21 + MODIS + Landsat active fire** | Active-fire coordinates, confidence, acquisition time, FRP/fire pixels                                  | Ground truth for current burning status; detection validation  | **Essential**                       |
| **2. Continuous geostationary imagery** | **NOAA GOES-18 ABI via NOAA Open Data/AWS**                     | Thermal bands, brightness temperature, fire/hotspot information, smoke/cloud context                    | Fast temporal input to ConvLSTM/detection model                | **Essential — already planned**     |
| **3. Lightning**                        | **GOES-18 GLM**                                                 | Flash/event location and timing                                                                         | Ignition feature, especially dry-lightning events              | **Add immediately**                 |
| **4. Short-range weather**              | **NOAA HRRR**                                                   | Wind speed/direction, temperature, RH, precipitation and surface fields                                 | Fire-spread prediction and forecast covariates                 | **Essential**                       |
| **5. Historical weather**               | **NOAA NCEI LCDv2**                                             | Hourly station temperature, humidity, precipitation, wind, pressure                                     | Historical model training/backtesting                          | **Essential**                       |
| **6. Vegetation condition**             | **NASA HLS v2.0 / HLS-VI**                                      | NDVI and other vegetation indices from harmonized Landsat 8/9 + Sentinel-2 A/B/C                        | Fuel greenness/dryness, vegetation stress                      | **Add immediately**                 |
| **7. Fuel type / canopy structure**     | **LANDFIRE 2025**                                               | FBFM40/13 fuel models, canopy height, canopy cover, canopy bulk density, canopy base height, vegetation | Fire propagation and spread potential                          | **Add immediately**                 |
| **8. Fuel moisture / fire danger**      | **USFS NFDRS / WFAS / RAWS**                                    | 10-, 100-, 1000-hour dead fuel moisture, live fuel estimates, ERC, BI, ignition/spread indices          | Much stronger fire-risk features than AQI alone                | **Add immediately**                 |
| **9. Terrain**                          | **USGS 3DEP**                                                   | DEM → elevation, slope, aspect                                                                          | Controls spread direction/rate and wind interaction            | **Essential**                       |
| **10. Historical fire footprints**      | **CAL FIRE FRAP + NIFC WFIGS**                                  | Historical California fire perimeters, current interagency incident perimeters                          | Labels, fire recurrence, hold-out events and spread validation | **Essential**                       |
| **11. Power infrastructure**            | **California Energy Commission transmission-line GIS**          | Transmission-line geometry, voltage, owner/status                                                       | Human/infrastructure ignition-risk feature                     | **Add**                             |
| **12. Soil moisture/drought**           | **NASA SMAP + USFS fire-danger products**                       | Surface/root-zone soil moisture and drought state                                                       | Antecedent dryness / vegetation-water-stress feature           | **Very useful**                     |
| **13. Smoke / PM2.5**                   | **EPA AirNow + AirData**                                        | Current PM2.5/AQI plus historical monitor data                                                          | Health-risk output and smoke validation                        | **Keep, but use official EPA feed** |
| **14. Road incidents/closures**         | **511 SF Bay Open Data**                                        | Real-time traffic incidents, road closures and detours                                                  | Dynamic evacuation routing                                     | **Add for AAWRP**                   |
| **15. Emergency shelters**              | **FEMA ESF6 Open Shelters service**                             | Currently open shelters, capacity-related attributes, accessibility/pet information                     | Destination generation for evacuation routes                   | **Add for AAWRP**                   |
| **16. Hazard alerts**                   | **NWS Alerts API**                                              | Red Flag Warnings and other fire-weather alerts                                                         | Dashboard/context feature and model validation                 | **Keep — already planned**          |"

**Expected Output From ML models(Unet and PINN)** "{
  "type": "FeatureCollection",
  "timestamp": "2026-08-28T20:00:00Z",
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
        "fire_probability": 0.73,
        "risk_label": "HIGH_RISK"
      }
    }
  ]
}
"

**Decision:** We will use Unet model and Physics-informed neural networks rather than FireGAN for downscaling GOES data to 500m resolution.

**Consequences:**
- "design-doc.md" will require a major overhaul based on the expected output from ML models
- The FastAPI inference engine input contract changes(will have to understand what sort of input Unet and PINN models will need)
- Training pipeline now requires new data sources, which the AI and ML students have not provided fully 
- "GEMINI.md" will also need major chagnes based on our plan


**What can be built right now**
- database engine : define the django model to ingest the backend contract
- The A* routing just needs to query danger_zone polygons — it doesn't care whether those came from a U-Net, PINN, or a mock. Build it against mock GeoJSON first.
- Build the FastAPI endpoint that receives the GeoJSON contract and POSTs it to Django. You can mock the model call itself with a static fixture.
- WebSocket broadcast (Django Channels) - The FIRE_UPDATE event just serializes whatever FireRiskMap objects are in the DB.
- RAG chatbot : It consumes risk_label and fire_probability from PostGIS queries — no ML dependency.
## ADR-002: Treat ML Inference as a Plug-and-Play Black Box

**Status:** Accepted
**Date:** 2026-09-09

**Context:** The AI/ML team's model development timeline extends 1–2 months into the project. The backend and frontend must be developed in parallel without blocking on a trained model. The ML team has agreed on a standard GeoJSON FeatureCollection output contract.

**Decision:** The ML Inference Engine (U-Net + PINN) is treated as a black box that integrates with the backend exclusively via a GeoJSON FeatureCollection output contract:
- `fire_probability` (float, 0.0–1.0)
- `risk_label` (HIGH_RISK | MEDIUM_RISK | LOW_RISK)
- `geometry` (Polygon, WGS84)
- `timestamp` (ISO-8601 UTC)

A `MOCK_INFERENCE=true` environment flag enables the FastAPI ML Adapter to return a static fixture, enabling full end-to-end development and CI/CD without a trained model.

**Consequences:**
- Backend and frontend development can proceed immediately without ML team dependencies
- The FastAPI ML Adapter is designed for zero-rework model swapping: replace the mock fixture with `model.predict()` when the model is ready
- The input contract (feature tensor shape and data sources) remains PENDING and will be documented in `docs/ml-model-spec.md` once the ML team confirms

## ADR-003: Daily Celery Cron for Inference Cadence

**Status:** Accepted  
**Date:** 2026-09-09

**Context:** The ML team has not yet confirmed whether inference should run on a fixed schedule or on-demand. The U-Net model outputs daily (next-day) fire risk predictions, making a sub-hourly schedule unnecessary.

**Decision:** ML inference is triggered by a **daily Celery beat cron job**. The cadence is configurable via environment variable (`INFERENCE_CRON_SCHEDULE`). The frontend reads pre-computed results from Redis cache, resulting in sub-100ms read latency regardless of model inference time.

**Consequences:**
- Removes the sub-5-second synchronous inference SLA (NFR-P01 revised to async background task)
- Celery beat schedule is easily adjusted to hourly or on-demand without architectural changes
- On-demand inference can be added as a separate Celery task in a future iteration
