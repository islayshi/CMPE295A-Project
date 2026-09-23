# PyroSentinel
**Project Name:** PyroSentinel
**Document Title:** Frontend MVP Design Specification
**Document Type:** Design Specification
**Version:** 1.0
**Author:** CMPE 295A Project Team

---

## Version History
| Version | Changes | 
| :--- | :--- | 
| 1.0 | Initial draft of the Frontend MVP Design Specification for PyroSentinel. |

## Introduction
This document describes the design and implementation of the Frontend Minimum Viable Product (MVP) for **PyroSentinel**, a real-time wildfire detection and predictive routing system scoped to the San Francisco Bay Area. The frontend serves as an interactive showcase, enabling users to visualize current fire perimeters, view AI-generated spread predictions (+1 to +6 hours), receive dynamic A* routing avoiding compromised roads, and interact with a context-aware RAG Chatbot for safety and health guidance.

## References
* **Master System Design Document:** `docs/design-doc.md`
* **Mapbox GL JS Documentation:** [https://docs.mapbox.com/mapbox-gl-js/](https://docs.mapbox.com/mapbox-gl-js/)
* **React Documentation:** [https://react.dev/](https://react.dev/)
* **Tailwind CSS v4:** [https://tailwindcss.com/](https://tailwindcss.com/)

## Requirements
### Functional Requirements (Essential MVP Core)
* **FR-E01 [Prediction Visualization]:** Visualize current fire perimeters and ConvLSTM deep learning-predicted spread polygons on a 3D interactive map.
* **FR-E02 [Dynamic Routing]:** Display optimal evacuation routes and re-route paths that avoid dynamically compromised road polygons.
* **FR-E03 [Confidence Metrics / Time Scrubbing]:** Provide an interactive time slider (0 to +6 hrs) to view prediction windows and associated confidence metrics.
* **FR-E04 [Telemetry & Environmental Hazards]:** Display live telemetry (AQI, Wind Speed/Direction), render Deck.gl animated wind particle arrays reflecting live vectors, and overlay NWS Red Flag Warning polygons when active.
* **FR-E05 [Emergency POIs]:** Display static Points of Interest using custom Lucide-react HTML markers (e.g., FEMA Evacuation Shelters) anchored securely to the map.
* **FR-E07 [Context-Aware Chat]:** Provide a simulated RAG-backed chatbot interface answering queries with contextual health data (e.g., asthma risks, AQI, shelter routing) and explicit citations (e.g., NWS, CalOES).

### Non-Functional Requirements
* **Styling Mandate:** Utilize "Glassmorphism" for UI elements (`bg-slate-900/60 backdrop-blur-md`) to maximize map visibility.
* **Base Map Style:** Must strictly use the high-contrast `mapbox://styles/mapbox/dark-v11` style with 3D terrain exaggeration.
* **Performance:** Ensure sub-2.0-second map rendering responses when states transition.

## Functional Overview
The Frontend MVP is built as a Single-Page Application (SPA) using **React.js** (via Vite) and **Tailwind CSS v4**. It utilizes **Mapbox GL JS** (`react-map-gl/mapbox`) to render high-fidelity geospatial data over 3D terrain. 

For the purposes of the MVP showcase, the frontend relies on an internal mock data generator (`geojsonStates.js`) to simulate three discrete operational states—`NORMAL`, `AI_UPDATE`, and `REROUTE`—allowing presenters to execute the "Golden Path" script without requiring the live Python/Django backend.

## Configuration/ External Interfaces
### Configuration
* **Environment Variables:** The application requires a `.env` file containing a valid Mapbox token (`VITE_MAPBOX_ACCESS_TOKEN`).
* **Styling Framework:** Configured natively with `@tailwindcss/vite` and `@tailwindcss/postcss` for utility-class styling.

### External Interfaces (Future State Integration)
* **REST APIs (GeoDjango):** Will be consumed for initial telemetry, vulnerability scores, and initial routing.
* **WebSockets (Django Channels):** Will be integrated to stream live `FIRE_UPDATE` GeoJSON pushes and RAG Chatbot token streams.
* **Mapbox APIs:** Uses native Mapbox vector tile endpoints and `mapbox-dem` for raster terrain mapping.

## Debug
### Logging
* **React DevTools:** Utilize browser extensions to trace state transitions within the `App.jsx` context (`scenarioState`, `timeScrub`).
* **Mapbox Events:** Mapbox load/error events can be attached to the `<Map>` component to trace tile-fetching failures or invalid GeoJSON shapes.

### Counters / Simulation States
* **ScenarioController:** A floating UI component that forcibly toggles application state between the three predefined modes to bypass external API dependencies and isolate frontend rendering logic for debugging.

**Final Production Application Clarification:**
In the final production application:
1. That floating UI component will be completely removed.
2. The `App.jsx` state (which we currently call `scenarioState`) will be driven entirely by **Django Channels WebSockets**.
3. When the Python Inference Engine finishes running ConvLSTM and generates a new prediction, it will push a WebSocket event to the React frontend containing the new GeoJSON polygons and the compromised road data.
4. The React app will automatically receive that data, transition its internal state, render the orange/yellow polygons, and update the Heads-Up Display (Telemetry Card) in real-time—all without the user ever clicking a "state" button.

*Think of the current `ScenarioController` as a remote control that lets you "fast-forward" through what the AI backend would eventually do automatically.*

## Implementation
### Architecture / Component Design
* **`App.jsx` (Global Orchestrator):** Manages shared state (`scenarioState`, `timeScrub`) and handles absolute layout positioning.
* **`MapCanvas.jsx` (Geospatial View):** Renders the Mapbox container overlaid with a **Deck.gl** WebGL canvas. Configures 3D pitch/bearing (Hayward, CA context), handles dynamic wind particle animations via `TextLayer`, and enforces strict Z-Index layering (Red Flag Warning -> Fire Pixels -> +3hr Spread -> +1hr Spread -> Safe Route -> Compromised Route -> Custom Shelter Markers).
* **HUD Overlay Components:**
  * **`TelemetryCard.jsx`:** Reacts to state changes (e.g., pulsing red during `AI_UPDATE`) to show simulated AQI, rotating wind vectors, and active Red Flag Warning banners.
  * **`TimeScrubber.jsx`:** An interactive slider bound to the global `timeScrub` state, controlling layer visibility in the MapCanvas.
  * **`ChatDrawer.jsx`:** A floating action button (FAB) that triggers a `framer-motion` slide-out panel, housing a simulated chat interaction logic triggering on specific prompt keywords.
  * **`Legend.jsx`:** Static visual key mapping styles to their real-world entity types.

### Sub-tasks / Development Phases
1. **Scaffolding:** Vite initialization, dependency installation (`react-map-gl`, `tailwindcss`), environment setup.
2. **Mock Data Engine:** Defining rigid GeoJSON features encompassing Hayward coordinates for all phases.
3. **Map Canvas Construction:** Assembling the layered `MapCanvas.jsx`.
4. **UI Overlay Construction:** Building the Tailwind glassmorphism components.
5. **State Orchestration:** Wiring global state down into prop drilling and validating visual fidelity across the "Golden Path".

## Testing
### General Approach
* **Manual "Golden Path" Testing:** The primary validation metric is ensuring the frontend smoothly steps through the three scenario states in sequential order, accurately reflecting the expected visual UI updates (e.g., route changing from solid blue to dashed red to new blue path).

### Unit Tests
* *(To be implemented)*:
  * **State Logic Tests:** Validation that specific `scenarioState` values correctly extract the accurate active GeoJSON collection.
  * **Component Render Tests:** React Testing Library setups to ensure UI elements like the pulsing `border-red-500` on the `TelemetryCard` mount appropriately when the `AI_UPDATE` state is active.

## Appendix
* **Mapbox Token:** Required for execution; freely available from `mapbox.com`.
* **Golden Path Script Reference:**
  1. Start `NORMAL` (Ambient West winds, User Location marker visible, Vulnerability: Low, no evacuation routes shown).
  2. Toggle `AI_UPDATE` (Winds shift to 45 mph SW, Red Flag Warning zone activates, Vulnerability: High. Fire polygons render alongside the dashed red compromised highway route).
  3. Toggle `REROUTE` (A* pathfinding draws a safe solid blue detour originating from the User Location to the Chabot College Evacuation Center).
  4. Engage Chat (Input: "Where should I go?" -> Bot outputs localized routing advice referencing the active NWS Red Flag warning, current AQI, and cites [NWS] and [CalOES]).