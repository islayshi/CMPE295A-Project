# 🛠️ PyroSentinel: Frontend Prototype Implementation Guide for gemini-cli

**Target Environment:** React.js (Vite), Tailwind CSS, `react-map-gl` (Mapbox GL JS wrapper).
**Objective:** Build an interactive, high-fidelity frontend prototype for a Master's defense showcasing a real-time wildfire prediction and dynamic routing system. 

The application must be modular, highly performant, and pre-configured with mock data states to seamlessly execute the "Golden Path" demonstration script in the San Francisco Bay Area (specifically centered around Hayward, CA).

---
## Global Set-up and Configuration

**Dependencies**

Ensure the project is initialized with the following core dependencies:

react, react-dom

react-map-gl, mapbox-gl (For the map canvas and 3D rendering)

tailwindcss, postcss, autoprefixer (For UI styling and glassmorphism)

lucide-react (For HUD and Chatbot icons)

framer-motion (For smooth transitions of the Chat Drawer and Telemetry Card)

**Environment Variables**
The application must expect a .env file containing:

VITE_MAPBOX_ACCESS_TOKEN

## 1. Deep-Dive Specification & Design Philosophy

Here is a deep-dive specification for the React + Mapbox GL JS Frontend Prototype, structured specifically to impress a review committee.

### 2. The Design Philosophy: "Dark Mode" & 3D Terrain
Wildfire data is inherently bright (reds, oranges, yellows). If you use a standard Google Maps-style light background, the data washes out.

* **The Base Map:** You should use the `mapbox://styles/mapbox/dark-v11` or a custom dark-satellite style. This provides high contrast, making the fire detection pixels and spread polygons glow.
* **3D Terrain:** Mapbox GL JS natively supports 3D terrain (`map.setTerrain`). Enabling this is a massive visually impressive feature for a California-based project. Showing the fire polygons draping over the Santa Cruz Mountains or the Diablo Range instantly proves why topographical data is so important to your model.

### 3. The Map Layers (Z-Index Hierarchy)
Mapbox works on a strict layering system. To prevent visual clutter, your layers must be stacked logically from bottom to top:

* **Layer 1 (Bottom):** Topography & Base Map (The dark map).
* **Layer 2: Current Fire Detection (FireGAN 500m Pixels)**
  * *Visuals:* Rendered as a Mapbox heatmap layer or discrete 500m square polygons (fill layer).
  * *Coloring:* Deep, solid crimson with a slight outer glow to denote confirmed thermal anomalies.
* **Layer 3: Predicted Spread Polygons (ConvLSTM Isochrones)**
  * *Visuals:* These should be concentric polygons representing time.
  * *Coloring:* High transparency (e.g., 30% opacity). Use a gradient: Orange for +1 Hour, Yellow for +3 Hours, dashed outlines for +6 Hours.
* **Layer 4: Dynamic Evacuation Route (GeoDjango A*)**
  * *Visuals:* A thick, highly visible line (e.g., neon blue or bright green) using a line layer.
  * *Behavior:* If the route recalculates, use Mapbox's native animation tools to smoothly interpolate the line shifting to the new path.
* **Layer 5 (Top):** Markers & POIs
  * Custom SVG icons for the User's GPS location, Evacuation Shelters, and Hospitals.

### 4. The UI Overlays (The "HUD")
The React components that float above the Mapbox canvas need to provide context without blocking the map.

**A. The Critical Legend (Bottom Left or Right)**
You absolutely need a legend. Raw data is useless without a key. It should cleanly define:
* 🔥 Current Fire Line (Solid Red Pixel)
* ⏱️ +1 Hour Spread Risk (Orange Polygon, 80% Confidence)
* ⏱️ +3 Hour Spread Risk (Yellow Polygon, 60% Confidence)
* 🚗 Safe Evacuation Route (Blue Line)
* ⛔ Compromised Road (Red 'X' or Dashed Line)

**B. The "Time Scrubber" / Playback Tool (Bottom Center)**
Since your AI predicts spread over time, give the user a slider.
* *Action:* When the user drags the slider from "Now" to "+3 Hours," the React state updates the Mapbox layer filters, fading out the +1 hour polygon and fading in the +3 hour polygon. This makes the prediction interactive.

**C. The Telemetry Card (Top Right)**
A translucent, glassmorphism-styled card displaying the live environmental context driving the AI model:
* *Current Location:* e.g., "Hayward, CA"
* *AQI / PM2.5:* "150 (Unhealthy)"
* *Live Wind:* "25 mph, NE (Diablo Wind Conditions Active)"
* *Vulnerability Score:* "High"

**D. The RAG Chatbot Drawer (Floating Action Button)**
A persistent chat icon that, when clicked, slides out a side-panel for the RAG LLM.
* *Contextual Greeting:* "I see you are in Hayward with an active fire warning 5 miles away. How can I help you prepare?"
* *Citation Links:* When the chatbot answers, it should include clickable footnote badges (e.g., [CDC], [CalFire]) that link out to the vector source documents.

### 4. The Prototype "Golden Path" (Showcase Script)
When you stand in front of your committee, you should have a specific sequence of interactions planned to show off the system's capabilities.

* **The Start:** Open the map showing the Bay Area with normal wind. A simulated small fire sits in the hills. The safe route directs the user normally down the highway.
* **The Wind Shift:** Trigger a simulated "Diablo Wind Event" button. The Telemetry Card flashes.
* **The AI Update:** The PyTorch model pushes a new GeoJSON. A massive orange polygon suddenly blooms across the map, intersecting the user's highway.
* **The Reroute:** The map automatically deletes the compromised route and draws a new safe path avoiding the orange polygon, proving the A* spatial logic.
* **The Chat:** You open the RAG chatbot and type, "I have mild asthma, should I leave now?" and the bot uses the PM2.5 data and PubMed vectors to provide a personalized, cited answer.

---

## 2. Component Architecture

Generate the following folder structure and component files. All components must use Tailwind CSS for styling.

```text
/src
 ├── /components
 │    ├── /Map
 │    │    └── MapCanvas.jsx (Core Mapbox instance & Layers)
 │    ├── /HUD
 │    │    ├── TelemetryCard.jsx
 │    │    ├── Legend.jsx
 │    │    ├── TimeScrubber.jsx
 │    │    └── ChatDrawer.jsx
 │    └── /DevTools
 │         └── ScenarioController.jsx (Hidden UI to trigger demo states)
 ├── /mockData
 │    └── geojsonStates.js (Pre-calculated GeoJSON for Hayward, CA)
 └── App.jsx (Main Layout orchestrator)