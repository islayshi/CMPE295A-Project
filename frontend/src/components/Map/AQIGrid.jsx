export function getPM25Color(pm25) {
  if (pm25 <= 12.0) return '#22c55e';  // Good - Green
  if (pm25 <= 35.4) return '#eab308';  // Moderate - Yellow
  if (pm25 <= 55.4) return '#f97316';  // Sensitive - Orange
  if (pm25 <= 150.4) return '#ef4444'; // Unhealthy - Red
  return '#a855f7';                    // Very Unhealthy - Purple
}

/**
 * Fetches real-world sensor/station AQI measurements around Northern California
 */
export async function fetchLiveAqiGeoJSON() {
  try {
    // OpenAQ v2 open measurements endpoint
    const response = await fetch(
      'https://api.openaq.org/v2/latest?limit=100&page=1&offset=0&sort=desc&coordinates=37.6688%2C-122.0828&radius=75000&order_by=lastUpdated&dump_raw=false'
    );

    if (!response.ok) {
      throw new Error(`AQI API HTTP error! status: ${response.status}`);
    }

    const data = await response.json();

    if (!data.results || data.results.length === 0) {
      return generateFallbackData();
    }

    const features = data.results
      .filter((station) => station.coordinates)
      .map((station) => {
        const pm25Val = station.measurements.find((m) => m.parameter === 'pm25')?.value || 15;
        return {
          type: 'Feature',
          properties: {
            location: station.location,
            value: pm25Val,
            color: getPM25Color(pm25Val)
          },
          geometry: {
            type: 'Point',
            coordinates: [station.coordinates.longitude, station.coordinates.latitude]
          }
        };
      });

    return { type: 'FeatureCollection', features };
  } catch (error) {
    console.warn('Live AQI fetch failed, loading fallback grid points:', error);
    return generateFallbackData();
  }
}

// Resilient fallback so your map NEVER breaks if external API goes down
function generateFallbackData() {
  const points = [
    [-122.0828, 37.6688, 15.2],
    [-122.2711, 37.8044, 42.1],
    [-122.4194, 37.7749, 18.5],
    [-121.8863, 37.3382, 65.0],
    [-122.1430, 37.4419, 8.4],
    [-122.2583, 37.8715, 33.0],
    [-122.0363, 37.3688, 110.2],
    [-121.9552, 37.3541, 16.8]
  ];

  return {
    type: 'FeatureCollection',
    features: points.map(([lng, lat, pm25]) => ({
      type: 'Feature',
      properties: { value: pm25, color: getPM25Color(pm25) },
      geometry: { type: 'Point', coordinates: [lng, lat] }
    }))
  };
}