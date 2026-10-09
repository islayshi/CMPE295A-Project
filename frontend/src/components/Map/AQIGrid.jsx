import React, { useMemo } from 'react';
import { Source, Layer } from 'react-map-gl/mapbox';
import { pm25ToEPAAQI, getAQIColor, evaluateIDW } from '../../utils/aqiMath';

export default function AQIGrid({ isAqiVisible, aqiSensors }) {
  const coverage = useMemo(() => {
    if (!aqiSensors || aqiSensors.length === 0) return { gridGrid: null, sensorPoints: null };

    // Format sensors for IDW and Point layers
    const sensors = aqiSensors.map((item) => {
      const pm25 = item.pm25 || 0;
      const aqi = pm25ToEPAAQI(pm25);
      return { lat: item.lat, lng: item.lon, pm25, aqi };
    });

    // Create Sensor Point Features (for labels)
    const sensorFeatures = sensors.map((s) => ({
      type: 'Feature',
      properties: {
        aqi: s.aqi,
        color: getAQIColor(s.aqi)
      },
      geometry: { type: 'Point', coordinates: [s.lng, s.lat] }
    }));

    // Create High-Res IDW Grid Covering Bay Area
    const centerLat = 37.6688;
    const centerLng = -122.0828;
    const radiusMiles = 70; // Expanded to cover whole map
    const stepMiles = 2;    // Higher resolution (smaller pixels)

    const milesToLat = 1 / 69;
    const milesToLng = 1 / (69 * Math.cos((centerLat * Math.PI) / 180));
    const stepLat = stepMiles * milesToLat;
    const stepLng = stepMiles * milesToLng;

    const gridFeatures = [];

    // Bounding Box iteration
    for (let lat = centerLat - radiusMiles * milesToLat; lat < centerLat + radiusMiles * milesToLat; lat += stepLat) {
      for (let lng = centerLng - radiusMiles * milesToLng; lng < centerLng + radiusMiles * milesToLng; lng += stepLng) {
        
        // Evaluate at cell center
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

    return {
      gridGrid: { type: 'FeatureCollection', features: gridFeatures },
      sensorPoints: { type: 'FeatureCollection', features: sensorFeatures }
    };
  }, [aqiSensors]);

  if (!isAqiVisible || !coverage.gridGrid) return null;

  return (
    <>
      {/* Interpolated AQI Grid (Cloud Fill) */}
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

      {/* Sensor Exact Values */}
      <Source id="aqi-sensor-points" type="geojson" data={coverage.sensorPoints}>
        {/* Sensor Bubble Background */}
        <Layer 
          id="aqi-sensor-bubbles"
          type="circle"
          paint={{
            'circle-radius': 14,
            'circle-color': ['get', 'color'],
            'circle-stroke-width': 2,
            'circle-stroke-color': '#ffffff',
            'circle-opacity': 0.95
          }}
        />
        {/* Sensor Number Text */}
        <Layer
          id="aqi-sensor-labels"
          type="symbol"
          layout={{
            'text-field': ['to-string', ['get', 'aqi']],
            'text-font': ['Open Sans Bold', 'Arial Unicode MS Bold'],
            'text-size': 12,
            'text-allow-overlap': true
          }}
          paint={{
            'text-color': '#ffffff'
          }}
        />
      </Source>
    </>
  );
}