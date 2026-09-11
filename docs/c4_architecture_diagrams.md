# Fight Fire With AI — C4 Architecture Diagrams

> Following the C4 model: **Context → Containers → Components**. Code level omitted per project scope.

---

## Level 1 — System Context Diagram

*Who uses the system and what external systems does it interact with?*

```mermaid
flowchart TD
    USER["👤 **End User**\n(Bay Area Resident)\nMobile / Desktop Browser"]
    ADMIN["🛠️ **System Admin /\nData Engineer**\nMonitors pipeline & predictions"]

    FFWAI["🔥 **Fight Fire With AI**\nWildfire Prediction &\nDynamic Evacuation Routing Platform\n(fightfirewAI — Python/Django + FastAPI)"]

    GEE["🛰️ **Google Earth Engine**\nNDVI / EVI / NDWI\nsatellite vegetation indices"]
    USGS["🏔️ **USGS 3DEP**\nDigital Elevation Model\n(elevation, slope, aspect)"]
    NWS["🌩️ **NWS Alerts API**\nRed Flag Warnings"]
    OPENWEATHER["💨 **OpenWeather / NOAA**\nWind speed, direction,\ntemperature, humidity"]
    OPENAQ["💨 **OpenAQ / PurpleAir**\nLive PM2.5 / AQI\n(deferred)"]
    MAPBOX["🗺️ **Mapbox GL JS**\nBase map tiles &\n3D terrain"]
    FEMA["🏥 **FEMA/CalOES**\nEmergency shelter\nlocations (static)"]
    BAY511["🚗 **511 SF Bay**\nReal-time road incidents\n& closures"]
    CALENERGY["⚡ **CA Energy Commission**\nPowerline GIS data\n(static, one-time)"]

    USER -->|"Views fire risk,\nevacuation routes"| FFWAI
    ADMIN -->|"Monitors Celery tasks,\nprediction metrics"| FFWAI

    FFWAI -->|"Pulls NDVI/EVI\nvia API"| GEE
    FFWAI -->|"Downloads DEM\n(one-time)"| USGS
    FFWAI -->|"Polls for active\nalerts"| NWS
    FFWAI -->|"Daily weather\nfetch"| OPENWEATHER
    FFWAI -->|"AQI data\n(deferred)"| OPENAQ
    FFWAI -->|"Renders map\ntiles"| MAPBOX
    FFWAI -->|"Loads shelter\nlocations (static)"| FEMA
    FFWAI -->|"Real-time road\nincident feed"| BAY511
    FFWAI -->|"Loads powerline\ndata (static)"| CALENERGY
```

---

## Level 2 — Container Diagram

*What are the deployable units and how do they talk to each other?*

```mermaid
flowchart TD
    USER["👤 **End User**\nWeb Browser"]

    subgraph SYSTEM["Fight Fire With AI — Deployed System"]
        direction TB

        REACT["⚛️ **React Frontend**\nReact 19, Vite\nMapbox GL JS, Deck.gl\nTailwind CSS v4\n\n[Browser SPA]"]

        DJANGO["🐍 **Django Backend**\n(fightfirewAI Django project)\nDjango 5.x + DRF\nDjango Channels\nGeoDjango\n\n[Python Web Server — Gunicorn/Daphne]"]

        CELERY["⚙️ **Celery Workers**\nData harvesters\nInference trigger\nScheduled tasks\n\n[Python Workers]"]

        FASTAPI["🤖 **FastAPI ML Adapter**\nML inference engine\n/predict/progression\n(U-Net + PINN)\n\n[Python ASGI Server — Uvicorn]"]

        POSTGRES["🗄️ **PostgreSQL + PostGIS + pgvector**\nFireRiskPrediction\nBayAreaGrid\nTerrainFeature\nVegetationIndex\n\n[Relational + Spatial DB]"]

        REDIS["⚡ **Redis**\n- Celery task broker\n- Django Channels WS store\n- GeoJSON cache\n\n[In-memory store]"]
    end

    USER -->|"HTTPS\nREST API calls\nWebSocket (WS)"| REACT
    REACT -->|"REST API calls"| DJANGO
    REACT <-->|"WebSocket\nFIRE_UPDATE events"| DJANGO

    DJANGO -->|"Enqueues tasks"| REDIS
    CELERY -->|"Reads tasks\nfrom broker"| REDIS
    CELERY -->|"HTTP POST\n/predict/progression"| FASTAPI
    FASTAPI -->|"GeoJSON\nFeatureCollection"| CELERY
    CELERY -->|"Writes predictions"| POSTGRES
    DJANGO -->|"Reads/Writes\nFireRiskPrediction\nA* spatial queries"| POSTGRES
    DJANGO -->|"Reads/Writes\ncurrent_risk_map cache"| REDIS
```

---

## Level 3 — Component Diagram: Django Backend

*What are the internal components of the Django backend container?*

```mermaid
flowchart TD
    REACT_C["⚛️ React Frontend\n[Container]"]
    CELERY_C["⚙️ Celery Workers\n[Container]"]
    FASTAPI_C["🤖 FastAPI ML Adapter\n[Container]"]
    POSTGRES_C["🗄️ PostgreSQL/PostGIS\n[Container]"]
    REDIS_C["⚡ Redis\n[Container]"]

    subgraph DJANGO_BACKEND["Django Backend — fightfirewAI"]
        direction TB

        subgraph ROUTING["URL Router / ASGI"]
            URL["urls.py\nRoutes HTTP → views\nRoutes WS → Channels"]
        end

        subgraph GRID_APP["grid app"]
            GRID_MODEL["BayAreaGrid model\nTerrainFeature model\nVegetationIndex model\n\nPostGIS PolygonField\nFloatFields per cell"]
            GRID_CMD["Management Commands\ngenerate_grid.py\nload_terrain.py\nload_powerlines.py\nseed_czu_fire.py"]
        end

        subgraph PREDICTIONS_APP["predictions app"]
            PRED_MODEL["FireRiskPrediction model\nModelPerformanceMetric model\n\nForeignKey → BayAreaGrid\nfire_probability, risk_label\nsource_model: unet/pinn/ensemble"]
            PRED_SERIAL["GeoJSON Serializer\nSpatial REST endpoint\n/api/predictions/current/\n/api/predictions/history/"]
            PRED_STORE["store_geojson_result()\nParses GeoJSON → DB rows\nUpdates Redis cache\nTriggers WS broadcast"]
        end

        subgraph HARVESTER_APP["harvester app"]
            HARV_TRIGGER["trigger_daily_inference()\n[Celery daily cron]\nOrchestrates full pipeline"]
            HARV_WEATHER["fetch_weather_data()\n[PLACEHOLDER]\nOpenWeather / NOAA HRRR"]
            HARV_FIRE["fetch_fire_perimeter_update()\n[PLACEHOLDER]\nNASA FIRMS / CAL FIRE"]
            HARV_VEG["fetch_vegetation_indices()\nGoogle Earth Engine API\nNDVI / EVI / NDWI\n→ VegetationIndex table"]
            HARV_ALERTS["fetch_nws_alerts()\nNWS Alerts API\n→ Redis cache"]
            HARV_ROADS["fetch_road_incidents()\n511 SF Bay API\n→ Redis cache"]
        end

        subgraph ROUTING_APP["routing app"]
            ASTAR["A* Engine\nGeoDjango spatial query\nBayAreaGrid danger zones\n→ Evacuation path GeoJSON"]
            ROUTE_API["REST endpoint\nPOST /api/routing/evacuate/\n{origin, destination}\n→ route GeoJSON"]
        end

        subgraph CHANNELS_APP["Django Channels / WebSocket"]
            WS_CONSUMER["FireUpdateConsumer\nBroadcasts FIRE_UPDATE\n{predictions, risk_map}\nto all connected clients"]
            WS_TELEMETRY["TelemetryConsumer\nBroadcasts wind, AQI,\nNWS alerts in real time"]
        end

        subgraph TELEMETRY_APP["telemetry app"]
            WIND_API["REST endpoint\nGET /api/telemetry/wind/\nWind speed/direction\nfor Deck.gl particles"]
            AQI_API["REST endpoint\nGET /api/telemetry/aqi/\n(deferred — OpenAQ)"]
            POI_API["REST endpoint\nGET /api/telemetry/shelters/\nFEMA/CalOES POIs\nfrom PostGIS"]
        end

        subgraph METRICS_APP["metrics app"]
            METRICS_API["REST endpoint\nGET /api/metrics/\nModelPerformanceMetric\nROC-AUC, F1, accuracy\nfor Performance Dashboard"]
        end

        subgraph AUTH_APP["accounts app\n(deferred — other developer)"]
            AUTH["User model\nHealth profile\nJWT auth\n\n[FR-D03, FR-D04 — Desired]"]
        end
    end

    REACT_C -->|"HTTP GET/POST"| URL
    REACT_C <-->|"WebSocket"| WS_CONSUMER
    REACT_C <-->|"WebSocket"| WS_TELEMETRY

    URL --> PRED_SERIAL
    URL --> ROUTE_API
    URL --> WIND_API
    URL --> AQI_API
    URL --> POI_API
    URL --> METRICS_API

    CELERY_C --> HARV_TRIGGER
    HARV_TRIGGER --> HARV_WEATHER
    HARV_TRIGGER --> HARV_FIRE
    HARV_TRIGGER --> HARV_VEG
    HARV_TRIGGER --> HARV_ALERTS
    HARV_TRIGGER --> HARV_ROADS
    HARV_TRIGGER -->|"HTTP POST /predict/progression"| FASTAPI_C
    FASTAPI_C -->|"GeoJSON FeatureCollection"| PRED_STORE

    PRED_STORE --> PRED_MODEL
    PRED_STORE --> REDIS_C
    PRED_STORE --> WS_CONSUMER

    HARV_VEG --> GRID_MODEL
    GRID_CMD --> GRID_MODEL

    PRED_MODEL --> POSTGRES_C
    ASTAR --> POSTGRES_C
    PRED_SERIAL --> POSTGRES_C
```

---

## Level 3 — Component Diagram: FastAPI ML Adapter

```mermaid
flowchart TD
    CELERY_C["⚙️ Celery Workers\n[Container]"]
    MODEL_FILES["📁 Model Files\n.keras (U-Net)\n.pkl (PINN — TBD)\nstored locally or mounted volume"]

    subgraph FASTAPI["FastAPI ML Adapter"]
        direction TB

        ROUTER["FastAPI Router\nPOST /predict/progression\nPOST /predict/ensemble\nGET /health"]

        MOCK["Mock Adapter\nMOCK_INFERENCE=true\nReturns static\nbay_area_fixture.json"]

        UNET["U-Net Adapter\nLoads .keras model\nAccepts (64×64×N) tensor\nOutputs fire mask\n→ GeoJSON polygons"]

        PINN["PINN Adapter\n(TBD / Aspirational)\nPhysics-constrained\nspread prediction\n→ GeoJSON polygons"]

        ENSEMBLE["Ensemble Layer\nCombines U-Net + PINN\noutputs via voting\nor probability averaging"]

        SCHEMA["Pydantic Schemas\nGeoJSONFeatureCollection\nFeaturePayload\nHealthResponse"]
    end

    CELERY_C -->|"HTTP POST\nfeature payload"| ROUTER
    ROUTER -->|"MOCK_INFERENCE=true"| MOCK
    ROUTER -->|"MOCK_INFERENCE=false"| UNET
    ROUTER -->|"MOCK_INFERENCE=false\n+ PINN available"| PINN
    UNET --> ENSEMBLE
    PINN --> ENSEMBLE
    ENSEMBLE -->|"GeoJSON\nFeatureCollection"| CELERY_C
    MOCK -->|"GeoJSON\nFeatureCollection"| CELERY_C
    MODEL_FILES -->|"model.predict()"| UNET
    MODEL_FILES -->|"pinn.predict()"| PINN
    SCHEMA -.->|"validates I/O"| ROUTER
```

---

## Cloud Architecture Diagram (Student Budget)

*Recommended AWS deployment using student-tier credits + always-free services.*

```mermaid
flowchart TD
    subgraph CLIENT["Client"]
        BROWSER["👤 Browser"]
    end

    subgraph AWS["☁️ AWS (Student Credits ~$200)"]
        direction TB

        CF["🌐 Amazon CloudFront\n[Always-free tier]\nCDN for React static assets\n+ SSL termination"]

        S3["🪣 Amazon S3\n[Always-free: 5GB]\nHosts React build output\nStores processed .npz feature files\nfor ML team access"]

        subgraph EC2_GROUP["Amazon EC2 (t3.micro — cheapest)"]
            NGINX["Nginx\nReverse proxy\nRoutes to Django/FastAPI"]
            DJANGO_PROC["Django / Daphne\n(ASGI — handles HTTP + WS)"]
            CELERY_PROC["Celery Worker\n+ Celery Beat (cron)"]
            FASTAPI_PROC["FastAPI / Uvicorn\nML Adapter (mock → real)"]
        end

        RDS["🗄️ Amazon RDS\nPostgreSQL + PostGIS\nt3.micro, 20GB SSD\n[Free tier: 750 hrs/mo]"]

        ELASTICACHE["⚡ ElastiCache (Redis)\ncache.t3.micro\n[Student credits]"]
    end

    subgraph EXTERNAL["External / Free Services"]
        GEE_EXT["🛰️ Google Earth Engine\n(free academic use)\nNDVI / EVI / NDWI"]
        HF["🤗 Hugging Face Hub\n(free, public repo)\nStore trained model files\n.keras / PINN weights\nML team uploads → backend downloads"]
        GITHUB["📦 GitHub\nSource code only\nNo large binary files"]
    end

    BROWSER -->|"HTTPS"| CF
    CF -->|"Static assets"| S3
    CF -->|"API / WS proxy"| NGINX
    NGINX --> DJANGO_PROC
    NGINX --> FASTAPI_PROC
    DJANGO_PROC --> RDS
    DJANGO_PROC --> ELASTICACHE
    CELERY_PROC --> ELASTICACHE
    CELERY_PROC -->|"Reads feature data"| S3
    CELERY_PROC -->|"Pulls NDVI data"| GEE_EXT
    FASTAPI_PROC -->|"Downloads model\non startup"| HF
```

---

## Data Storage Decision Guide

| Data Type | Size Estimate | Recommended Storage | Cost |
|---|---|---|---|
| **React build** | ~5 MB | AWS S3 | Free tier |
| **Processed `.npz` feature files** (daily, Bay Area) | ~100–500 MB/day | AWS S3 | ~\$0.023/GB/mo |
| **PostGIS spatial data** (grid, terrain, predictions) | ~2–5 GB | AWS RDS | Free tier (20GB) |
| **Trained U-Net `.keras` model** | ~50–200 MB | **Hugging Face Hub** | Free (public repo) |
| **PINN model weights** | ~10–50 MB | **Hugging Face Hub** | Free |
| **Raw satellite imagery** (Landsat, GOES) | **Terabytes** | **Google Earth Engine** — do NOT download | Free academic |
| **Historical fire perimeters** (CAL FIRE FRAP) | ~1 GB | AWS S3 or local | Minimal |
| **USGS DEM** (Bay Area) | ~2 GB | AWS S3 or local | Minimal |

> [!IMPORTANT]
> **Key recommendation**: Never download raw satellite imagery to your own storage. Use **Google Earth Engine** (free for academic use) to query, process, and extract only the computed indices (NDVI, EVI) you need. This avoids terabytes of storage costs.

> [!TIP]
> **Hugging Face Hub for model files**: The ML team uploads trained model files to a Hugging Face repo → the FastAPI ML Adapter downloads the latest model on container startup. Zero storage cost, zero coordination overhead.

---

## Open Questions Before Week 1 Scaffold

| Question | Decision |
|---|---|
| Grid resolution | **1×1 km** (18,000 cells, aligns with papers — revisit 0.5km later) |
| Django project name | **`fightfirewAI`** |
| Python version | **Python 3.12** (stable LTS, most Django/TF support) |
| Google Colab / Drive | **Deferred** — use GEE + Hugging Face Hub instead |
| RAG chatbot | **Deferred** — out of scope until core features work |
| XGBoost/RF in FastAPI | **Removed** — not needed for now |
