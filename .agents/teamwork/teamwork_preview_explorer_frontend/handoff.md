# Handoff Report: Frontend Investigation on `feature/ml-adapter-integration`

## 1. Observation

Direct observations from git history, diff inspection, and file reads between `main` (`5730412`) and `feature/ml-adapter-integration` (`e046b11`):

### A. Git History & Scope
- Commits modifying the frontend on branch `feature/ml-adapter-integration`:
  - `e046b11`: "chore: cleanup and checkpoint ML adapter integration"
  - `9716769`: "style: overhaul Time Scrubber UI, align with California Ember theme, snap to valid horizons, update map legend, and remove outdated 24h mock file"
  - `ead0603`: "feat: complete ML adapter integration, chronological fire tracking, and robust UI updates"
- Files modified across `frontend/`:
  1. `frontend/src/components/Map/AQIGrid.jsx` (190 lines changed)
  2. `frontend/src/components/Map/MapCanvas.jsx` (106 lines changed)
  3. `frontend/src/components/HUD/TimeScrubber.jsx` (77 lines changed)
  4. `frontend/src/components/HUD/LayersLegend.jsx` (67 lines changed)
  5. `frontend/src/components/Navbar.jsx` (60 lines changed)
  6. `frontend/src/pages/Dashboard.jsx` (17 lines changed)
  7. `frontend/src/utils/aqiMath.js` (9 lines changed)

---

### B. Continuous AQI Interpolation Layer
- **Component File**: `frontend/src/components/Map/AQIGrid.jsx`
- **Math Utility**: `frontend/src/utils/aqiMath.js`
- **Render Engine**: Built natively with **Mapbox GL JS** (`react-map-gl/mapbox` `Source` and `Layer` components), **not Deck.gl**.
- **Data Source & Ingestion**:
  - Polled via REST from backend endpoint `/telemetry/aqi/` (`frontend/src/api/telemetry.js` lines 11–13: `fetchAqiData`).
  - Polled every 5 minutes (300,000 ms) in `Dashboard.jsx` (lines 66–71) using TanStack React Query (`queryKey: ['aqi']`).
  - Sensor payload format: Array of items with `{ lat, lon, pm25 }`.
- **Interpolation Algorithm (IDW)** (`aqiMath.js` lines 34–52):
  - Uses Inverse Distance Weighting:
    ```javascript
    const d = Math.sqrt(
      Math.pow((targetLat - s.lat) / milesToLat, 2) + 
      Math.pow((targetLng - sLng) / milesToLng, 2)
    );
    const w = 1 / Math.pow(Math.max(d, 0.5), 2);
    weightedSum += pm25 * w;
    weightTotal += w;
    ```
- **Grid Configuration Changes** (`AQIGrid.jsx` lines 27–41):
  - Center: `centerLat = 37.6688`, `centerLng = -122.0828` (Hayward / SF Bay Area).
  - Coverage Radius: Expanded from 45 miles to 70 miles (`radiusMiles = 70`) to envelope the entire Bay Area viewport.
  - Spatial Resolution: Step size cut in half from 4 miles to 2 miles (`stepMiles = 2`), resulting in a 4x denser polygon grid.
  - Bounding box loop evaluates IDW at cell center (`cellCenterLat = lat + stepLat / 2`, `cellCenterLng = lng + stepLng / 2`) to eliminate alignment skew.
- **Continuous Rendering Technique & Shader Optimizations** (`AQIGrid.jsx` lines 79–90):
  - Fill layer definition:
    ```jsx
    <Source id="aqi-grid-source" type="geojson" data={coverage.gridGrid}>
      <Layer
        id="aqi-grid-fill"
        type="fill"
        paint={{
          'fill-color': ['get', 'color'],
          'fill-opacity': 0.40,
          'fill-antialias': false // helps smooth the grid edges so it looks continuous
        }}
      />
    </Source>
    ```
  - Crucial rendering details:
    - `'fill-antialias': false`: Disables Mapbox sub-pixel border smoothing lines between adjacent polygons, preventing polygon seam artifacts and creating a smooth, continuous raster-like cloud gradient.
    - Removed `aqi-radius-outline` (the old 45-mile dashed blue boundary circle).
    - Removed `aqi-grid-lines` (the 0.5px white cell grid mesh that previously made the display look like a chess board).
- **Exact Station Ground-Truth Overlay** (`AQIGrid.jsx` lines 93–121):
  - Added station bubble point source (`id="aqi-sensor-points"`):
    - Circle Layer (`id="aqi-sensor-bubbles"`): `'circle-radius': 14`, `'circle-color': ['get', 'color']`, `'circle-stroke-width': 2`, `'circle-stroke-color': '#ffffff'`, `'circle-opacity': 0.95`.
    - Symbol Layer (`id="aqi-sensor-labels"`): `'text-field': ['to-string', ['get', 'aqi']]`, `'text-font': ['Open Sans Bold', 'Arial Unicode MS Bold']`, `'text-size': 12`, `'text-allow-overlap': true`, `'text-color': '#ffffff'`.
- **Color Scale & Mapping** (`aqiMath.js` lines 4–29):
  - Official US EPA PM2.5 breakpoints converted via `pm25ToEPAAQI`:
    - 0–50: `#22c55e` (Green / Good)
    - 51–100: `#eab308` (Yellow / Moderate)
    - 101–150: `#f97316` (Orange / Unhealthy for Sensitive Groups)
    - 151–200: `#ef4444` (Red / Unhealthy)
    - 201–300: `#a855f7` (Purple / Very Unhealthy)
    - 301+: `#7e22ce` (Maroon / Hazardous)
- **UI Controls**:
  - `LayersLegend.jsx` lines 49–60: Interactive toggle switch with Lucide `Activity` icon and smooth animated slider (`bg-orange-600` active state).
  - Legend display inside `LayersLegend.jsx` details all 6 EPA color tiers.

---

### C. Interactive "Safe Haven" Hover Pop-ups for Emergency Shelters
- **Component File**: `frontend/src/components/Map/MapCanvas.jsx` (lines 10, 92–146)
- **Data Source**: Polled via TanStack React Query from `/telemetry/shelters/` (`frontend/src/api/telemetry.js` lines 3–5: `fetchShelters`, 5-minute interval). Seeded in backend via `seed_shelters` command into PostGIS model `EmergencyShelter`.
- **Marker Implementation** (`MapCanvas.jsx` lines 92–109):
  - Rendered conditionally: `{isSheltersVisible && shelters?.features?.map((shelter) => ...)}`.
  - Built with `react-map-gl/mapbox` `<Marker>` component anchored to `[coordinates[0], coordinates[1]]` with `anchor="bottom"`.
  - Circular badge styling:
    `className="flex items-center justify-center bg-blue-500 text-white rounded-full border-2 border-white shadow-md hover:scale-110 hover:shadow-lg hover:bg-blue-600 transition-all cursor-pointer p-1.5"`
  - Icon: Lucide `Tent` icon (`<Tent size={14} strokeWidth={2.5} />`).
  - Interactive hover handlers:
    - `onMouseEnter={() => setSelectedShelter(shelter)}`
    - `onMouseLeave={() => setSelectedShelter(null)}`
  - Replaces previous bulky UI: Previous version used a permanent green `ShieldPlus` icon with an always-visible black text card that heavily cluttered the map.
- **Hover Pop-up Component** (`MapCanvas.jsx` lines 109–146):
  - Uses `react-map-gl/mapbox` `<Popup>` component:
    ```jsx
    <Popup
      longitude={selectedShelter.geometry.coordinates[0]}
      latitude={selectedShelter.geometry.coordinates[1]}
      anchor="bottom"
      offset={30}
      closeButton={false}
      closeOnClick={false}
      className="z-50 pointer-events-none"
    >
    ```
  - Card Layout & Styling:
    - Outer wrapper: `flex flex-col min-w-[200px] -m-3`
    - Frosted Blue Header: `bg-blue-50/80 px-3 py-2 border-b border-blue-100/50 rounded-t-lg backdrop-blur-sm`
    - Name: `<h3 className="font-bold text-slate-800 text-sm leading-tight">{selectedShelter.properties.name}</h3>`
    - Card Body: `p-3 bg-white/95 backdrop-blur-sm rounded-b-lg flex flex-col gap-2`
  - Displayed Metadata:
    - **Physical Address**: Rendered with Lucide `MapPin` icon (`size={14}`, `text-blue-500`):
      `selectedShelter.properties.address`
    - **Capacity**: Rendered with Lucide `Users` icon (`size={14}`, `text-blue-500`):
      `Capacity: {selectedShelter.properties.capacity}`
    - **Data Source**: Source attribution badge at bottom:
      `<span className="text-[10px] bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded font-bold">{selectedShelter.properties.source}</span>` (e.g. Red Cross / FEMA / local OES).
    - **Coordinates**: Shelter latitude and longitude anchor the popup marker directly on the Mapbox canvas at `[coordinates[0], coordinates[1]]`.
- **UI Visibility Control**:
  - `LayersLegend.jsx` lines 62–73: New toggle switch for "Emergency Shelters" featuring Lucide `Tent` icon and blue active state (`bg-blue-500`).
  - State managed in `Dashboard.jsx` (`isSheltersVisible`, defaulting to `false` for clean initial load).
  - Map Legend in `LayersLegend.jsx` updated with blue "Official Emergency Shelter" badge and `Tent` icon.

---

### D. Timeline Slider & Mapbox Property Filtering
- **Component Files**:
  - `frontend/src/components/HUD/TimeScrubber.jsx`
  - `frontend/src/pages/Dashboard.jsx` (lines 73–80, 112)
  - `frontend/src/components/Map/MapCanvas.jsx` (lines 49, 73)
- **Dynamic Horizon Detection & State Management** (`Dashboard.jsx` lines 73–80):
  ```javascript
  const parsedHorizons = predictions?.features 
    ? [...new Set(predictions.features.map(f => f.properties.horizon_hours ?? f.properties.lead_time_hours ?? 0))].sort((a, b) => a - b)
    : [];
  const availableHorizons = parsedHorizons.length > 0 ? parsedHorizons : [0, 1, 3, 6];
  const activeHorizon = [...availableHorizons].reverse().find(h => h <= timeScrub) ?? 0;
  ```
- **Mapbox WebGL GPU Property Filtering** (`MapCanvas.jsx` lines 49, 73):
  ```javascript
  filter={['==', ['coalesce', ['get', 'horizon_hours'], ['get', 'lead_time_hours'], 0], timeScrub]}
  ```
  - Highlights:
    - Uses Mapbox GL JS native WebGL expression filtering (`['==', ...]`).
    - Uses `coalesce` to safely handle schema migrations: Checks `horizon_hours` first, falls back to `lead_time_hours`, and defaults to `0`.
    - Static payload polling: The entire GeoJSON FeatureCollection containing all horizons (+0h, +1h, +3h, +6h) is polled once every 5 minutes from `/predictions/current/`. Dragging the slider filters polygons entirely on the GPU in WebGL with **0ms network delay**.
- **TimeScrubber UI Overhaul** (`TimeScrubber.jsx` lines 1–60):
  - Allowed horizons strictly constrained: `const allowed = [0, 1, 3, 6]`. Outdated +12h and +24h options removed to align with actual model horizons.
  - Step slider: `min="0" max={maxIndex} step="1"`, mapped to the indices of `horizonsToUse`.
  - Concrete Clock ETA:
    - Calculates target time: `targetDate = new Date(Date.now() + timeScrub * 60 * 60 * 1000)`
    - Formats to user locale: `targetTimeStr = targetDate.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })`
  - Active Forecast Pill Badge:
    - Centered pill: `Forecast: +{timeScrub} Hour(s) ({timeScrub === 0 ? 'Current' : targetTimeStr})`
    - Live radar animation: When `timeScrub === 0`, renders a pulsing beacon (`animate-ping`).
  - Tick mark indicators: Visual labels below the track (`+0h`, `+1h`, `+3h`, `+6h`) with active tick expansion (`scale-110 font-bold text-orange-700`).
- **Continuous Fire Probability Color Ramp** (`MapCanvas.jsx` lines 51–69, 75–86):
  - Replaced discrete spread hour color steps with continuous linear interpolation across `fire_probability` (0.0 to 1.0):
    ```javascript
    'fill-color': [
      'interpolate',
      ['linear'],
      ['get', 'fire_probability'],
      0.0, '#eab308', // Yellow
      0.2, '#eab308',
      0.5, '#f97316', // Orange
      0.8, '#dc2626', // Red
      1.0, '#991b1b'  // Dark Maroon
    ],
    'fill-opacity': [
      'interpolate',
      ['linear'],
      ['get', 'fire_probability'],
      0.0, 0.2,
      1.0, 0.8
    ]
    ```
  - Synced with `LayersLegend.jsx` (line 98) using a continuous gradient bar:
    `background: 'linear-gradient(to right, #eab308 0%, #eab308 20%, #f97316 50%, #dc2626 80%, #991b1b 100%)'`.

---

### E. Navigation, Theme Adherence & Quality Checks
- **Segmented Control Navbar** (`frontend/src/components/Navbar.jsx` lines 1–46):
  - Modern pill segmented control (`bg-slate-100 p-1.5 rounded-full border border-slate-200/60 shadow-inner`).
  - Clean routing links: `Live Map` (`/`, `Map` icon), `Model` (`/model`, `Cpu` icon), `Data` (`/data`, `Database` icon).
  - Active tab elevates with white card background, drop shadow, and orange accent icon (`text-orange-500`, `scale-105`).
  - Removed outdated Chatbot toggle and Login button placeholders.
- **"California Ember" Palette Compliance**:
  - Neutrals (60%): Slate-50, Slate-100, Slate-200, White backdrop blur.
  - Secondary/Text (30%): Slate-800, Slate-600, Slate-500.
  - Ember Accents (10%): Warm orange-500, orange-600, orange-700, orange-100 pill highlights.
  - Emergency Accents: Blue-500, blue-600, blue-50 for emergency shelters.
- **Build Verification**:
  - Command: `npm run build` in `frontend/`
  - Result: **Success** in 1.13s (Vite v8.3.1 produced production bundles in `dist/`).
- **Lint Verification**:
  - Command: `npm run lint` in `frontend/`
  - Result: 2 ESLint errors found:
    1. `frontend/src/components/HUD/TimeScrubber.jsx:11`: Calling `Date.now()` directly during render triggers `react-hooks/purity` (`Cannot call impure function during render`).
    2. `frontend/src/components/WeatherForecast.jsx:56`: Calling `setLoading(true)` directly in `useEffect` triggers `react-hooks/set-state-in-effect`.

---

## 2. Logic Chain

1. **AQI Implementation**:
   - The user requested investigation into whether AQI interpolation is implemented via Deck.gl or Mapbox, data sources, and rendering approach.
   - *Observation A & B* confirm that `AQIGrid.jsx` uses `react-map-gl/mapbox` `<Source>` and `<Layer>` components. It does not use Deck.gl for AQI.
   - The continuous cloud effect is achieved by coupling a fine 2-mile IDW grid with Mapbox's `'fill-antialias': false` paint property. By turning off antialiasing borders between neighboring polygons and stripping the old grid lines and perimeter ring, adjacent cells blend seamlessly into an organic continuous heat field.
   - Ground-truth validation is retained by adding a dedicated symbol and bubble layer displaying the exact EPA AQI at sensor coordinates.

2. **Emergency Shelter Pop-ups**:
   - *Observation C* demonstrates the transition from a clutter-inducing permanent marker label to a sleek interactive hover card.
   - The circular `Tent` icon marker acts as the hover target, cleanly firing `onMouseEnter` and `onMouseLeave`.
   - The `react-map-gl/mapbox` `<Popup>` is configured with `pointer-events-none`, `closeButton={false}`, and `offset={30}`, ensuring smooth hover interactions without jitter.
   - The popup displays essential emergency metadata: Shelter Name, Street Address, Capacity, and Source badge.
   - Added user opt-in control via an Emergency Shelters switch in `LayersLegend.jsx`, preventing visual overload on initial map load.

3. **Timeline Slider & Property Filtering**:
   - *Observation D* shows how the frontend connects to the asynchronous scheduled prediction pipeline.
   - The ML adapter bundles +0h, +1h, +3h, and +6h forecasts into a single GeoJSON FeatureCollection.
   - The frontend loads this single payload every 5 minutes.
   - As the user scrubs `TimeScrubber`, `MapCanvas` uses Mapbox's WebGL expression `['==', ['coalesce', ['get', 'horizon_hours'], ['get', 'lead_time_hours'], 0], timeScrub]`.
   - This filters polygons entirely in GPU memory, providing instantaneous 60fps scrubbing with zero HTTP requests.
   - Obsolete +12h and +24h mock horizons were removed, locking the slider to valid model horizons `[0, 1, 3, 6]`, supplemented by a live ETA clock display.

4. **Code Quality and Architectural Cohesion**:
   - *Observation E* confirms that the UI adheres strictly to the California Ember design system and that the Vite production build succeeds.
   - The ESLint check exposed that `TimeScrubber.jsx` calculates `Date.now()` within the component render body rather than inside a hook or memo, which is flagged by React 19 / ESLint compiler rules.

---

## 3. Caveats

- **ESLint Rule Failure**: `TimeScrubber.jsx:11` calls `Date.now()` directly in the render body. In React 19, this violates pure render principles (`react-hooks/purity`). While `npm run build` succeeds, running `npm run lint` fails. A small refactor (e.g., storing the base timestamp in `useMemo` or calculating it in an effect) will be needed when modifying code.
- **AQI Grid Boundaries**: While the AQI grid radius was expanded to 70 miles to cover the Bay Area, it remains bounded by a bounding box from Hayward coordinates `(37.6688, -122.0828)`. Outer peripheries beyond 70 miles (e.g., far Northern California or Central Valley) will not render AQI polygons.
- **Shelter Coordinates**: The shelter coordinates are used by the Mapbox marker placement itself; numerical latitude/longitude coordinates are not printed as text inside the popup card (the popup displays shelter name, address, capacity, and source).
- **Read-only Investigation**: In accordance with explorer subagent instructions, no code was altered or committed during this review.

---

## 4. Conclusion

The frontend updates on branch `feature/ml-adapter-integration` deliver a major upgrade in interactive GIS capabilities, visual design, and data contract fidelity:
1. **AQI Interpolation Layer**: High-resolution 2-mile IDW interpolation rendered natively in Mapbox GL JS using `'fill-antialias': false` for a seamless raster-like heat map, augmented with ground-truth sensor bubble labels and official 6-tier EPA AQI colors.
2. **Safe Haven Shelter Pop-ups**: Modernized emergency shelter beacons with Lucide `Tent` icons, fluid hover pop-ups displaying shelter name, physical address, capacity, and data source, complete with a dedicated toggle in `LayersLegend`.
3. **Timeline Scrubbing & WebGL Filtering**: Frictionless zero-network timeline scrubbing powered by Mapbox GPU property filtering (`horizon_hours` / `lead_time_hours`), strictly snapped to valid model intervals `[0, 1, 3, 6]` with dynamic ETA clock calculation and continuous fire probability gradient rendering (`0.0 -> #eab308` to `1.0 -> #991b1b`).
4. **Design System & Navigation**: Segmented control pill navigation in `Navbar.jsx` and full visual harmony with the "California Ember" design palette. Production build is fully operational (`vite build` passes in 1.13s).

---

## 5. Verification Method

To independently verify these findings:

1. **Verify Git History and Diff**:
   ```bash
   git diff --stat main..feature/ml-adapter-integration -- frontend/
   git log --oneline main..feature/ml-adapter-integration
   ```

2. **Verify Frontend Build**:
   ```bash
   cd frontend
   npm run build
   ```
   *Expected outcome*: Vite compiles cleanly, creating production bundles in `frontend/dist/`.

3. **Verify Frontend Linting**:
   ```bash
   cd frontend
   npm run lint
   ```
   *Expected outcome*: ESLint identifies the 2 known purity/effect warnings in `TimeScrubber.jsx:11` and `WeatherForecast.jsx:56`.

4. **Inspect Key Component Files**:
   - `frontend/src/components/Map/AQIGrid.jsx`: Verify 2-mile step size, 70-mile radius, `fill-antialias: false`, and sensor bubble layers.
   - `frontend/src/components/Map/MapCanvas.jsx`: Verify shelter `Marker` + `Popup` implementation and WebGL filter expression `['==', ['coalesce', ...], timeScrub]`.
   - `frontend/src/components/HUD/TimeScrubber.jsx`: Verify allowed horizons `[0, 1, 3, 6]`, slider mapping, and ETA badge.
   - `frontend/src/components/HUD/LayersLegend.jsx`: Verify Emergency Shelter toggle and continuous fire probability gradient bar.
