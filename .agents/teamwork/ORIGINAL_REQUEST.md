# Original User Request

## 2026-10-06T19:38:40Z

# Teamwork Project Prompt — Draft

> Status: Launched
> Goal: Craft prompt → get user approval → delegate to teamwork_preview
> Requested team: Full team

Review the `feature/ml-adapter-integration` branch to generate a comprehensive Merge Request description. The output must synthesize recent backend architectural changes, frontend UI updates, and documentation updates, expanding on the provided initial draft. 

Working directory: /Users/earlpadron/Desktop/Spring 2026 Courses/CMPE 295A/CMPE295A-Project
Integrity mode: development

Original Draft Information provided by user:
```
Goal Description
The ML team provided Jupyter notebooks detailing the U-Net and PINN models. Our goal is to architect a scalable integration between Django, FastAPI, and Vertex AI. We have shifted to a Scheduled Asynchronous Pipeline, utilizing Celery as a scout to query active fires and caching the resulting ML predictions for lightning-fast frontend delivery.

Architectural Decisions
Inference Cadence: Scheduled (Asynchronous). The backend runs predictions on a regular cadence via Celery, decoupling the ML processing from frontend HTTP requests.
Rolling Forecasts: While models predict up to +6 hours into the future, the frontend polls every 30 minutes to fetch the freshest calculations. This ensures the future forecasts adapt immediately to newly detected conditions (e.g., sudden wind shifts).
Active Fire Detection (The "Scout"): Celery acts as the scout, querying lightweight NASA FIRMS / NOAA APIs to find active fire coordinates, building bounding boxes, and sending them to Vertex AI.
Ingestion Boundary: Vertex Native Ingestion. ML endpoints handle their own data downloads based on the specific bounding boxes provided by Celery.
GeoJSON Payload Assembly: The FastAPI ML adapter acts as the orchestrator. It waits for Vertex AI to generate the separate +1, +3, and +6 hour predictions and stitches them into a single, unified GeoJSON FeatureCollection, shielding Django from heavy data-wrangling.
Frontend Querying Pattern: Static Payload Polling. The frontend makes one request every 30 minutes to fetch the pre-assembled payload of all Bay Area predictions.
Frontend Filtering Strategy: Mapbox Property Filtering. Because the unified GeoJSON tags every polygon with a horizon_hours property, Mapbox uses a WebGL filter (e.g., ['==', ['get', 'horizon_hours'], sliderValue]) to instantly show/hide polygons as the user drags the timeline slider, requiring zero network calls on panning or timeline scrubbing.
Data Lifecycle & Caching: Ephemeral Redis + Persistent PostGIS. Redis holds the pre-assembled GeoJSON payload with a 1-hour TTL for instant frontend loading. PostGIS permanently stores the polygons for historical analysis, with a nightly archival job for data older than 30 days.
```

## Requirements

### R1. Synthesize Merge Request Description
Generate a standard Markdown document containing the final Merge Request description. It must incorporate the original "Goal Description" and 8 "Architectural Decisions" provided above.

### R2. Detail Recent Codebase Additions
Expand the description to include recent work:
- **Backend**: Updates to the Celery pipeline, PostGIS models, and the `seed_shelters` management command.
- **Frontend**: The new continuous AQI interpolation layer and the interactive "Safe Haven" hover pop-ups for Emergency Shelters.
- **Documentation**: Summarize the specific updates made to `docs/vertex-ai-endpoint-contract.md`, `README.md`, and `docs/design-doc.md`.

## Acceptance Criteria

### Content Completeness (Agent-as-Judge)
- [ ] The generated document includes the original "Goal Description".
- [ ] The document lists at least 10 Architectural Decisions (the original 8, plus new entries for backend/data/frontend changes).
- [ ] The document explicitly highlights the UI updates to the AQI layer and Emergency Shelters.
- [ ] The document contains a section detailing the changes made to the three requested documentation files.
