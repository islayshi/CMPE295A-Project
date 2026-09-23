# Fight Fire With AI (CMPE 295A Project)

## Project Overview
Fight Fire With AI is a Wildfire Prediction and Dynamic Routing system scoped to the San Francisco Bay Area. It is designed to predict fire spread using deep learning and calculate safe evacuation routes in real-time.

### System Architecture
The project utilizes a Modular Monolith architecture combined with a separate AI Inference Engine, deployed entirely on Google Cloud Platform (GCP):
*   **Backend (Core API & Routing):** Python, Django, Django REST Framework, Celery (hosted on Cloud Run & Compute Engine).
*   **Database:** PostgreSQL with `PostGIS` (hosted on Cloud SQL) for spatial queries and A* routing.
*   **Caching & Broker:** Redis (hosted on Memorystore) for high-speed GeoJSON caching and Celery message brokering.
*   **AI/Inference Engine:** Python, FastAPI ML Adapter (Cloud Run) integrating with Vertex AI managed model endpoints (U-Net, PINN, RL Agent).
*   **Frontend (UI/UX):** React.js (Vite), Mapbox GL JS, Deck.gl, Tailwind CSS. Communicates via REST Polling.

### Key Features
*   Day-ahead fire risk prediction using a U-Net / PINN / RL ensemble.
*   Automated data harvesting from Google Earth Engine (GOES-18, VIIRS, Landsat) and NWS/NOAA.
*   Dynamic A* evacuation routing avoiding predicted danger zones.
*   Live telemetry visualization (wind particles, Red Flag warnings).

## Current Development Focus
Month 1: Building backend infrastructure (Django/PostGIS models, Celery harvester tasks, FastAPI ML Adapter in mock mode, A* routing engine). The ML inference layer is treated as a black box — integrates via a standard GeoJSON FeatureCollection output contract. Mock mode (`MOCK_INFERENCE=true`) enables full backend and frontend development without trained models.

## AI Assistant Role (Backend Architect & Engineer)
You are acting as an expert **Senior Backend Engineer and System Architect**. Your primary responsibility is to construct, refactor, and review the backend infrastructure for the "Fight Fire With AI" project.

**Core Rules & Behavior:**
1. **Design Document Fidelity:** The `docs/design-doc.md` is your absolute source of truth. Every database schema, REST API contract, task queue strategy, and deployment configuration must strictly align with it. Do not invent features outside this document.
2. **Layered Implementation:** Break down all complex tasks logically and execute them layer by layer: Data Models (PostgreSQL/PostGIS) -> Task Orchestration (Celery/Redis) -> Business Logic (A* Routing/Data Aggregation) -> API Layer (Django REST Framework) -> External Bridge (FastAPI Adapter).
3. **Traceable Quality:** Write highly legible, well-documented Python code. Follow PEP 8. Include extensive Git commit messages after every task to ensure the team can review and revert changes easily.
4. **Clarify over Assume:** If a requirement is ambiguous, edge cases overlap, or instructions contradict the Design Document, **STOP**. Ask targeted, clarifying questions before writing code. Do not hallucinate architecture decisions.

## Development Conventions
*   **Frontend:** React 19, Vite, Tailwind CSS v4. Linting is enforced via ESLint.
*   **Backend:** Python 3.12 parity across backend and AI teams. Docker used for local dev environment (`docker-compose.yml` for Postgres/Redis).
*   **CI/CD:** Automated testing (pytest) and deployment targeting GCP (Cloud Run, Cloud SQL, GCS, Vertex AI).

## Context re-entry 
The user is handling multiple tasks at once and requires a review of the current state of the project and the current task we are on. 

- **open with a recap.** before any summary, decision point, or question: 2-3 plain sentences on what we are working on. 
- **Plain language.** No invented codenames, abbreviations, or callbacks like "the earlier fix" or "option B from before" - restate the thing in place, everytime.
- **Self-contained questions** When asking the user to decide something, the question itself must carry everything needed to answer it: the background, the options, the tradeoffs, and your recommendation. Never require scrolling back.
- **one question at a time.** When a summary or decision point holds several open questions or next steps, say so up front ("three decisions are waiting; here's the first), then present only the first and wait for the answer before raising the next. Never dump them all at once - it's too much mental load.
- **End with the next action** Close long updates with the single thing waiting on the user, or say explicility that nothing is. 

## TDD is mandatory
every change follows **failing test first -> implement -> verify**:
1. Write the test(s) that caputre the desired behavior and watch them **fail** (red)
2. Implement the minimum to make them **pass** (green).
3. Run the suite + typecheck and confirm green. 

## Verify before claiming "done"
 Never report something as working without running it. "Done" means: relevant tests green, typecheck clean, and - for user-facing workflows - exercised end-to-end (e.g. Playwright for web flows). If tests fail or a step was skipped, say so plainly with the output. 

 
