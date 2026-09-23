# 🧠 Gemini CLI Context Reference: Frontend MVP Implementation History

**Document Purpose:** 
This document serves as a persistent context and reasoning reference for future AI assistant (Gemini CLI) sessions. It comprehensively outlines the specific steps, design decisions, and debugging processes involved in building the **PyroSentinel Frontend MVP Prototype** (React + Mapbox + Deck.gl). If a session is cut off or a new workspace is initialized, the AI should ingest this file to understand *why* the codebase looks the way it does.

---

## 1. Project Context & Goals
**PyroSentinel** is a Master's project focused on real-time wildfire detection (FireGAN) and prediction (ConvLSTM) paired with dynamic A* evacuation routing in the San Francisco Bay Area. 
Because the backend requires heavy GPU/PostGIS infrastructure, we built a standalone **Frontend MVP Prototype** to simulate the entire system for a defense presentation. The goal was to create a highly polished, interactive UI that visually proves the AI's value proposition without requiring a live Python/Django backend.

---

## 2. Initial Setup & Styling Architecture
*   **Framework:** React 19 via Vite.
*   **Styling:** We utilized **Tailwind CSS v4** to enforce a "Glassmorphism" aesthetic (`bg-slate-900/60 backdrop-blur-md`) for all floating HUD overlays, ensuring the 3D map remains visible underneath.
*   **Critical Setup Bug (Resolved):** Initially, the Mapbox canvas collapsed and the UI rendered as raw text. This was because the project originally attempted to use a legacy Tailwind v3 PostCSS configuration. We resolved this by migrating fully to the `@tailwindcss/vite` plugin and using the `@import "tailwindcss";` directive in `index.css`.

---

## 3. The Core Map (`MapCanvas.jsx`)
We used `react-map-gl/mapbox` to render the Mapbox canvas.
*   **Vite Import Bug (Resolved):** Vite failed to resolve standard `react-map-gl` imports in v8+. We explicitly changed the import to `import Map, ... from 'react-map-gl/mapbox';` to fix the ESM export issue.
*   **Visual Hierarchy:** The map relies on a strict Z-Index layering strategy to prevent visual clutter:
    1. Base Map (`dark-v11`) with 3D terrain (`mapbox-dem` exaggerated 1.5x).
    2. NWS Red Flag Warning Polygon (Translucent Red).
    3. FireGAN Detection Pixels (Solid Red Circles).
    4. ConvLSTM Predictions (Orange +1hr, Yellow +3hr).
    5. A* Routing (Blue safe route, Dashed Red compromised route).
    6. Deck.gl Wind Particles.
    7. Custom HTML Markers (User Location & Shelters).

---

## 4. WebGL Wind Animation (`Deck.gl`)
To visualize environmental covariates, we overlaid a `DeckGL` canvas on top of Mapbox.
*   **The Data:** `mockData/windGrids.js` generates a grid of `u` (longitude) and `v` (latitude) velocity vectors.
*   **The Animation:** We used a Deck.gl `TextLayer` rendering Unicode arrows (`➔`).
*   **Critical Physics & Rendering Bugs (Resolved):**
    *   **Invisible Particles:** Deck.gl's font atlas didn't natively include the Unicode arrow. We fixed this by adding `characterSet: ['➔']`.
    *   **Hyper-Speed Teleportation:** The initial `requestAnimationFrame` loop was calculating geographical degrees too fast. We slowed the `elapsed` multiplier drastically (`time * 0.000002 * speed`) to create a smooth, ambient flow.
    *   **Directional Accuracy:** Standard weather terminology (e.g., "45 mph NE") means wind originates in the NE and blows SW. We updated the underlying vectors to `u = -20, v = -20` and fixed the `Math.atan2` rotation matrix so the arrows physically flow South-West, pushing the fire from the hills down into Hayward.

---

## 5. Scenario Orchestration (The "Golden Path")
We built a floating `ScenarioController.jsx` to manually step through three predefined states, fetching dynamic mock data from `geojsonStates.js`. We deliberately evolved this narrative to maximize the "wow" factor for the defense:

### State 1: `NORMAL`
*   **Visuals:** Clean map. No fire, no routes, no warnings. Gentle westerly wind particles flowing east.
*   **Telemetry:** AQI 45 (Good). Wind 10 mph W. Vulnerability: Low. 
*   **Design Decision:** We explicitly removed the fire pixels and evacuation routes from this state to establish a calm baseline before the disaster strikes.

### State 2: `AI_UPDATE`
*   **Visuals:** The wind violently shifts SW. The Red Flag Warning polygon activates (anchored at the fire origin in Fairview and blanketing downwind Hayward). Fire pixels and ConvLSTM predictive spread polygons bloom. A **dashed red line** appears on the highway.
*   **Telemetry:** AQI 150 (Unhealthy). Wind 45 mph SW. Vulnerability: High. Red Flag banner pulses.
*   **Design Decision:** The dashed red line proves that the AI detected the standard highway route is now compromised by the predicted fire spread.

### State 3: `REROUTE`
*   **Visuals:** The dashed red line disappears. A new **solid blue line** is drawn via PostGIS A* pathfinding.
*   **Design Decision:** The route was explicitly corrected to anchor exactly at the User's Location (a bright blue Mapbox `<Marker>`) and weave south through local roads, terminating perfectly at the Chabot College shelter (a custom HTML marker utilizing the Lucide-react `<ShieldPlus />` icon). 

---

## 6. RAG Chatbot Integration (`ChatDrawer.jsx`)
*   **Implementation:** A Framer Motion slide-out drawer containing a simulated chat interface.
*   **Interaction:** If the user types *"Where should I go?"*, the bot synthesizes the live environmental data (NWS Red Flag status, AQI 150) and recommends the Chabot College route, appending explicit citation badges `[NWS] [CalOES]`. This demonstrates the RAG (Retrieval-Augmented Generation) capabilities of the broader Python architecture.

---

## 7. Master Documentation Alignment
Throughout the build, we rigorously updated `docs/design-doc.md` and `docs/design-spec.md` to reflect the frontend realities.
*   Added the explicit comparison to **Watch Duty**, defending the academic scope by emphasizing PyroSentinel's **Predictive AI** and **Dynamic Routing** advantages over Watch Duty's reactive, human-in-the-loop radio scanning.
*   Appended comprehensive QA, Performance, and Deployment plans (AWS, Docker, PostGIS benchmarking) to the master design doc to satisfy Master's defense requirements.