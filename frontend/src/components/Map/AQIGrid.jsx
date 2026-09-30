import React, { useMemo } from 'react';
import { Source, Layer } from 'react-map-gl/mapbox';

/**
 * Calculates official US EPA Air Quality Index (AQI) from raw PM2.5 concentration (µg/m³)
 */
function pm25ToEPAAQI(pm25Raw) {
  if (pm25Raw < 0) return 0;
  // EPA truncates to 1 decimal place for PM2.5 breakpoints
  const pm25 = Math.floor(pm25Raw * 10) / 10;
  
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
function getAQIColor(aqi) {
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
function generateRadiusCircle(centerLat = 37.6688, centerLng = -122.0828, radiusMiles = 45, points = 64) {
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

export default function AQIGrid({ isAqiVisible, aqiSensors, centerLat = 37.6688, centerLng = -122.0828, radiusMiles = 45 }) {
  const coverage = useMemo(() => {
    if (!aqiSensors || aqiSensors.length === 0) {
      return { radiusCircle: null, gridGrid: null };
    }

    const circleCoverage = generateRadiusCircle(centerLat, centerLng, radiusMiles);

    const sensors = aqiSensors.map((item) => {
      const pm25 = item.pm25 || 0;
      return {
        lat: item.lat,
        lng: item.lon,
        pm25: pm25
      };
    });

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

          // IDW evaluates at the center of the grid cell to prevent alignment skew
          const cellCenterLat = lat + stepLat / 2;
          const cellCenterLng = lng + stepLng / 2;

          sensors.forEach((s) => {
            const d = Math.sqrt(Math.pow((cellCenterLat - s.lat) / milesToLat, 2) + Math.pow((cellCenterLng - s.lng) / milesToLng, 2));
            const w = 1 / Math.pow(Math.max(d, 0.5), 2);
            weightedSum += s.pm25 * w;
            weightTotal += w;
          });

          const interpolatedPM25 = weightTotal > 0 ? weightedSum / weightTotal : 0;
          const interpolatedAQI = pm25ToEPAAQI(interpolatedPM25);

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
  }, [aqiSensors, centerLat, centerLng, radiusMiles]);

  if (!isAqiVisible || !coverage.radiusCircle) return null;

  return (
    <>
      <Source id="aqi-radius-source" type="geojson" data={coverage.radiusCircle}>
        <Layer
          id="aqi-radius-outline"
          type="line"
          paint={{
            'line-color': '#38bdf8',
            'line-width': 2,
            'line-dasharray': [4, 2],
            'line-opacity': 0.8
          }}
        />
      </Source>

      {coverage.gridGrid?.features?.length > 0 && (
        <Source id="aqi-grid-source" type="geojson" data={coverage.gridGrid}>
          <Layer
            id="aqi-grid-fill"
            type="fill"
            paint={{
              'fill-color': ['get', 'color'],
              'fill-opacity': 0.35
            }}
          />
          <Layer
            id="aqi-grid-lines"
            type="line"
            paint={{
              'line-color': '#ffffff',
              'line-opacity': 0.08,
              'line-width': 0.5
            }}
          />
        </Source>
      )}
    </>
  );
}