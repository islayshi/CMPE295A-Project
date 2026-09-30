/**
 * Calculates official US EPA Air Quality Index (AQI) from raw PM2.5 concentration (µg/m³)
 */
export function pm25ToEPAAQI(pm25Raw) {
  if (pm25Raw < 0) return 0;
  // EPA truncates to 1 decimal place for PM2.5 breakpoints
  const pm25 = Math.floor(pm25Raw * 10) / 10;
  
  if (pm25 <= 12.0) return Math.round(((50 - 0) / (12.0 - 0.0)) * (pm25 - 0.0) + 0);
  if (pm25 <= 35.4) return Math.round(((100 - 51) / (35.4 - 12.1)) * (pm25 - 12.1) + 51);
  if (pm25 <= 55.4) return Math.round(((150 - 101) / (55.4 - 35.5)) * (pm25 - 35.5) + 101);
  if (pm25 <= 150.4) return Math.round(((200 - 151) / (150.4 - 55.5)) * (pm25 - 55.5) + 151);
  if (pm25 <= 250.4) return Math.round(((300 - 201) / (250.4 - 150.5)) * (pm25 - 150.5) + 201);
  if (pm25 <= 350.4) return Math.round(((400 - 301) / (350.4 - 250.5)) * (pm25 - 250.5) + 301);
  if (pm25 <= 500.4) return Math.round(((500 - 401) / (500.4 - 350.5)) * (pm25 - 350.5) + 401);
  return 500;
}

/**
 * Official EPA Color scale based on calculated AQI index (0 - 500)
 */
export function getAQIColor(aqi) {
  if (aqi <= 50) return '#22c55e';   // Good (0-50) -> Green
  if (aqi <= 100) return '#eab308';  // Moderate (51-100) -> Yellow
  if (aqi <= 150) return '#f97316';  // Sensitive Groups (101-150) -> Orange
  if (aqi <= 200) return '#ef4444';  // Unhealthy (151-200) -> Red
  if (aqi <= 300) return '#a855f7';  // Very Unhealthy (201-300) -> Purple
  return '#7e22ce';                  // Hazardous (301+) -> Maroon
}

/**
 * Core Inverse Distance Weighting logic used by the grid map and HUD.
 */
export function evaluateIDW(targetLat, targetLng, sensors, milesToLat, milesToLng) {
  let weightedSum = 0;
  let weightTotal = 0;

  sensors.forEach((s) => {
    const sLng = s.lng !== undefined ? s.lng : s.lon;
    const pm25 = s.pm25 || 0;

    const d = Math.sqrt(
      Math.pow((targetLat - s.lat) / milesToLat, 2) + 
      Math.pow((targetLng - sLng) / milesToLng, 2)
    );
    const w = 1 / Math.pow(Math.max(d, 0.5), 2);
    weightedSum += pm25 * w;
    weightTotal += w;
  });

  return weightTotal > 0 ? weightedSum / weightTotal : 0;
}

/**
 * Calculates the interpolated PM2.5 value for a specific coordinate based on Inverse Distance Weighting (IDW).
 * Evaluates at the center of the grid cell to ensure exact match with the rendered AQIGrid cells.
 */
export function calculateInterpolatedPM25(targetLat, targetLng, sensors, centerLat = 37.6688, centerLng = -122.0828, radiusMiles = 45) {
  if (!sensors || sensors.length === 0) return null;

  const stepMiles = 4;
  const milesToLat = 1 / 69;
  const milesToLng = 1 / (69 * Math.cos((centerLat * Math.PI) / 180));
  const stepLat = stepMiles * milesToLat;
  const stepLng = stepMiles * milesToLng;

  // The grid starts at centerLat - radiusMiles * milesToLat
  const startLat = centerLat - radiusMiles * milesToLat;
  const startLng = centerLng - radiusMiles * milesToLng;

  // Find the cell index
  const latIndex = Math.floor((targetLat - startLat) / stepLat);
  const lngIndex = Math.floor((targetLng - startLng) / stepLng);

  // Determine the bottom-left corner of the grid cell
  const latCorner = startLat + latIndex * stepLat;
  const lngCorner = startLng + lngIndex * stepLng;

  // Check if this grid cell actually exists in the map
  const distFromCenter = Math.sqrt(
    Math.pow((latCorner - centerLat) / milesToLat, 2) + Math.pow((lngCorner - centerLng) / milesToLng, 2)
  );

  if (distFromCenter > radiusMiles) {
    return null; // The map does not render a cell here
  }

  // Find the cell center (where IDW evaluates in AQIGrid.jsx)
  const cellCenterLat = latCorner + stepLat / 2;
  const cellCenterLng = lngCorner + stepLng / 2;

  return evaluateIDW(cellCenterLat, cellCenterLng, sensors, milesToLat, milesToLng);
}

/**
 * Returns the exact local AQI based on the user's location and sensor data
 */
export function getLocalizedAQI(targetLat, targetLng, sensors) {
    const interpolatedPM25 = calculateInterpolatedPM25(targetLat, targetLng, sensors);
    if (interpolatedPM25 === null) return null;
    return pm25ToEPAAQI(interpolatedPM25);
}
