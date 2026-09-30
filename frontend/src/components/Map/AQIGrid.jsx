import React, { useMemo } from 'react';
import { Source, Layer } from 'react-map-gl/mapbox';

import { pm25ToEPAAQI, getAQIColor, evaluateIDW } from '../../utils/aqiMath';

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
          // IDW evaluates at the center of the grid cell to prevent alignment skew
          const cellCenterLat = lat + stepLat / 2;
          const cellCenterLng = lng + stepLng / 2;

          const interpolatedPM25 = evaluateIDW(cellCenterLat, cellCenterLng, sensors, milesToLat, milesToLng);
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