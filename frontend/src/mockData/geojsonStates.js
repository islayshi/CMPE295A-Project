import { normalWind, severeWind } from './windGrids';

export const getMapData = (scenarioState, timeScrub) => {
  const isNormal = scenarioState === 'NORMAL';
  const isAiUpdate = scenarioState === 'AI_UPDATE';
  const isReroute = scenarioState === 'REROUTE';
  
  const firePixels = (isAiUpdate || isReroute) ? {
    type: 'FeatureCollection',
    features: [
      { type: 'Feature', geometry: { type: 'Point', coordinates: [-122.0428, 37.6888] } },
      { type: 'Feature', geometry: { type: 'Point', coordinates: [-122.0450, 37.6850] } },
    ]
  } : { type: 'FeatureCollection', features: [] };

  const spread1Hr = (isAiUpdate || isReroute) && timeScrub >= 1 ? {
    type: 'FeatureCollection',
    features: [{
      type: 'Feature',
      geometry: {
        type: 'Polygon',
        coordinates: [[
          [-122.06, 37.70],
          [-122.02, 37.70],
          [-122.02, 37.66],
          [-122.06, 37.66],
          [-122.06, 37.70]
        ]]
      }
    }]
  } : { type: 'FeatureCollection', features: [] };

  const spread3Hr = (isAiUpdate || isReroute) && timeScrub >= 3 ? {
    type: 'FeatureCollection',
    features: [{
      type: 'Feature',
      geometry: {
        type: 'Polygon',
        coordinates: [[
          [-122.08, 37.72],
          [-122.00, 37.72],
          [-122.00, 37.64],
          [-122.08, 37.64],
          [-122.08, 37.72]
        ]]
      }
    }]
  } : { type: 'FeatureCollection', features: [] };

  const normalRoute = {
    type: 'FeatureCollection',
    features: [{
      type: 'Feature',
      geometry: {
        type: 'LineString',
        coordinates: [
          [-122.0828, 37.6688], // User
          [-122.0700, 37.6800], // Highway
          [-122.0500, 37.6900]
        ]
      }
    }]
  };

  const reroute = {
    type: 'FeatureCollection',
    features: [{
      type: 'Feature',
      geometry: {
        type: 'LineString',
        coordinates: [
          [-122.0828, 37.6688], // User Location
          [-122.0900, 37.6600], // Hesperian Blvd
          [-122.1000, 37.6400], // Southward away from fire
          [-122.1068, 37.6298]  // Chabot College Evacuation Center
        ]
      }
    }]
  };

  let routeSafe = { type: 'FeatureCollection', features: [] };
  let routeCompromised = { type: 'FeatureCollection', features: [] };

  if (isNormal) {
    // No routes shown in Normal state
  } else if (isAiUpdate) {
    routeCompromised = normalRoute; // Show the dashed red compromised highway
  } else if (isReroute) {
    routeSafe = reroute; // Show the safe blue detour
  }

  // NEW: Evacuation Shelters (FEMA)
  const userLocation = {
    type: 'FeatureCollection',
    features: [
      {
        type: 'Feature',
        properties: { name: 'You are here' },
        geometry: { type: 'Point', coordinates: [-122.0828, 37.6688] }
      }
    ]
  };

  const shelters = {
    type: 'FeatureCollection',
    features: [
      {
        type: 'Feature',
        properties: { name: 'Hayward High School Shelter' },
        geometry: { type: 'Point', coordinates: [-122.0650, 37.6600] }
      },
      {
        type: 'Feature',
        properties: { name: 'Chabot College Evacuation Center' },
        geometry: { type: 'Point', coordinates: [-122.1068, 37.6298] }
      }
    ]
  };

  // NEW: Red Flag Warning (NWS)
  const redFlagWarning = {
    type: 'FeatureCollection',
    features: [
      {
        type: 'Feature',
        geometry: {
          type: 'Polygon',
          coordinates: [[
            [-122.10, 37.69], // North-West boundary
            [-122.03, 37.69], // North-East boundary (Fairview area fire origin)
            [-122.03, 37.64], // South-East boundary
            [-122.10, 37.64], // South-West boundary (stopping before Chabot College shelter)
            [-122.10, 37.69]
          ]]
        }
      }
    ]
  };

  // NEW: Environmental Metrics based on Scenario State
  const isCritical = isAiUpdate || isReroute;
  const envState = {
    aqi: isCritical ? 150 : 45,
    aqiStatus: isCritical ? 'Unhealthy' : 'Good',
    windText: isCritical ? '45 mph SW' : '10 mph W',
    redFlagActive: isCritical,
    activeWindGrid: isCritical ? severeWind : normalWind,
    vulnerability: isCritical ? 'High' : 'Low'
  };

  return { firePixels, spread1Hr, spread3Hr, routeSafe, routeCompromised, shelters, redFlagWarning, envState, userLocation };
};
