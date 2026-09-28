// AQIGrid.jsx

/**
 * Calculates official US EPA Air Quality Index (AQI) from raw PM2.5 concentration (µg/m³)
 */
export function pm25ToEPAAQI(pm25) {
  if (pm25 < 0) return 0;
  if (pm25 <= 12.0) return Math.round(((50 - 0) / (12.0 - 0.0)) * (pm25 - 0.0) + 0);
  if (pm25 <= 35.4) return Math.round(((100 - 51) / (35.4 - 12.1)) * (pm25 - 12.1) + 51);
  if (pm25 <= 55.4) return Math.round(((150 - 101) / (55.4 - 35.5)) * (pm25 - 35.5) + 101);
  if (pm25 <= 150.4) return Math.round(((200 - 151) / (150.4 - 55.5)) * (pm25 - 55.5) + 151);
  if (pm25 <= 250.4) return Math.round(((300 - 201) / (250.4 - 150.5)) * (pm25 - 150.5) + 201);
  return Math.round(((500 - 301) / (500.4 - 250.5)) * (pm25 - 250.5) + 301);
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
 * Generates the 45-mile coverage boundary circle
 */
export function generateRadiusCircle(centerLat = 37.6688, centerLng = -122.0828, radiusMiles = 45, points = 64) {
  const milesToLat = 1 / 69;
  const milesToLng = 1 / (69 * Math.cos((centerLat * Math.PI) / 180));
  const coordinates = [];

  for (let i = 0; i <= points; i++) {
    const theta = (i / points) * (2 * Math.PI);
    const lat = centerLat + (radiusMiles * milesToLat) * Math.sin(theta);
    const lng = centerLng + (radiusMiles * milesToLng) * Math.cos(theta);
    coordinates.push([lng, lat]);
  }

  return {
    type: 'FeatureCollection',
    features: [{
      type: 'Feature',
      properties: { radiusMiles },
      geometry: { type: 'Polygon', coordinates: [coordinates] }
    }]
  };
}

/**
 * Fetches accurate live ambient air quality measurements from real-time meteorological models
 */
/*export async function fetchLiveAqiCoverage(centerLat = 37.6688, centerLng = -122.0828, radiusMiles = 45) {
  const circleCoverage = generateRadiusCircle(centerLat, centerLng, radiusMiles);

  // Key monitoring hubs around the Bay Area
  const sampleLocations = [
    { name: 'San Jose', lat: 37.3382, lng: -121.8863 },
    { name: 'San Francisco', lat: 37.7749, lng: -122.4194 },
    { name: 'Oakland', lat: 37.8044, lng: -122.2711 },
    { name: 'Hayward', lat: 37.6688, lng: -122.0828 },
    { name: 'Palo Alto', lat: 37.4419, lng: -122.1430 },
    { name: 'Berkeley', lat: 37.8715, lng: -122.2583 }
  ]; */
export async function fetchLiveAqiCoverage(centerLat = 39.9042, centerLng = 116.4074, radiusMiles = 45) {
  const circleCoverage = generateRadiusCircle(centerLat, centerLng, radiusMiles);

  // Key monitoring hubs around Beijing
  const sampleLocations = [
    { name: 'Beijing Central (Dongcheng)', lat: 39.9042, lng: 116.4074 },
    { name: 'Chaoyang District', lat: 39.9219, lng: 116.4431 },
    { name: 'Haidian District', lat: 39.9593, lng: 116.2985 },
    { name: 'Fengtai District', lat: 39.8585, lng: 116.2862 },
    { name: 'Shijingshan District', lat: 39.9056, lng: 116.2229 },
    { name: 'Tongzhou District', lat: 39.9082, lng: 116.6572 }
  ];

  try {
    const lats = sampleLocations.map(l => l.lat).join(',');
    const lngs = sampleLocations.map(l => l.lng).join(',');

    // Live Open-Meteo Air Quality API (free, open CORS, live US EPA model data)
    const url = `https://air-quality-api.open-meteo.com/v1/air-quality?latitude=${lats}&longitude=${lngs}&current=pm2_5,us_aqi`;
    const res = await fetch(url);

    if (!res.ok) throw new Error('Live AQI fetch failed');

    const data = await res.json();
    const results = Array.isArray(data) ? data : [data];

    const sensors = results.map((item, idx) => {
      const pm25 = item.current?.pm2_5 || 0;
      const calculatedAQI = item.current?.us_aqi || pm25ToEPAAQI(pm25);
      return {
        lat: sampleLocations[idx].lat,
        lng: sampleLocations[idx].lng,
        aqi: calculatedAQI
      };
    });

    // Build grid cells interpolated strictly from live sensor queries
    const gridFeatures = [];
    const stepMiles = 4;
    const milesToLat = 1 / 69;
    const milesToLng = 1 / (69 * Math.cos((centerLat * Math.PI) / 180));
    const stepLat = stepMiles * milesToLat;
    const stepLng = stepMiles * milesToLng;

    for (let lat = centerLat - radiusMiles * milesToLat; lat < centerLat + radiusMiles * milesToLat; lat += stepLat) {
      for (let lng = centerLng - radiusMiles * milesToLng; lng < centerLng + radiusMiles * milesToLng; lng += stepLng) {
        const distFromCenter = Math.sqrt(
          Math.pow((lat - centerLat) / milesToLat, 2) + Math.pow((lng - centerLng) / milesToLng, 2)
        );

        if (distFromCenter <= radiusMiles) {
          let weightedSum = 0;
          let weightTotal = 0;

          sensors.forEach((s) => {
            const d = Math.sqrt(Math.pow((lat - s.lat) / milesToLat, 2) + Math.pow((lng - s.lng) / milesToLng, 2));
            const w = 1 / Math.pow(Math.max(d, 0.5), 2);
            weightedSum += s.aqi * w;
            weightTotal += w;
          });

          const interpolatedAQI = Math.round(weightTotal > 0 ? weightedSum / weightTotal : 0);

          gridFeatures.push({
            type: 'Feature',
            properties: {
              aqi: interpolatedAQI,
              color: getAQIColor(interpolatedAQI)
            },
            geometry: {
              type: 'Polygon',
              coordinates: [[
                [lng, lat],
                [lng + stepLng, lat],
                [lng + stepLng, lat + stepLat],
                [lng, lat + stepLat],
                [lng, lat]
              ]]
            }
          });
        }
      }
    }

    return {
      radiusCircle: circleCoverage,
      gridGrid: { type: 'FeatureCollection', features: gridFeatures }
    };
  } catch (error) {
    console.error('Could not fetch live AQI data:', error);
    // Return EMPTY features so map shows blank instead of fake data
    return {
      radiusCircle: circleCoverage,
      gridGrid: { type: 'FeatureCollection', features: [] }
    };
  }
}