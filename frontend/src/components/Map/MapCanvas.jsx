import { useRef, useState, useEffect, useMemo } from 'react';
import Map, { Source, Layer, Marker } from 'react-map-gl/mapbox';
import DeckGL from '@deck.gl/react';
import { TextLayer } from '@deck.gl/layers';
import 'mapbox-gl/dist/mapbox-gl.css';
import { getMapData } from '../../mockData/geojsonStates';
import { ShieldPlus, Activity } from 'lucide-react';
import { fetchLiveAqiGeoJSON } from './AQIGrid';

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_ACCESS_TOKEN || 'pk.eyJ1IjoiZXZlbiIsImEiOiJjbTFuMmluY3cwM2x3M2pyMGNvbzN2dngzIn0.mock';

export default function MapCanvas({ scenarioState, timeScrub }) {
  const mapRef = useRef();
  const data = getMapData(scenarioState, timeScrub);
  
  // AQI Layer toggle state
  const [isAqiVisible, setIsAqiVisible] = useState(true);

  // State for AQI data
  const [aqiGridData, setAqiGridData] = useState({ type: 'FeatureCollection', features: [] });

  // ADD THIS EFFECT HERE TO TRIGGER THE FETCH:
  useEffect(() => {
    async function loadAqiData() {
      const data = await fetchLiveAqiGeoJSON();
      setAqiGridData(data);
    }
    loadAqiData();
  }, []);

  // Legend categories definition
  const aqiLegend = [
    { label: 'Good (0–50)', color: '#22c55e' },
    { label: 'Moderate (51–100)', color: '#eab308' },
    { label: 'Unhealthy (Sensitive) (101–150)', color: '#f97316' },
    { label: 'Unhealthy (151–200)', color: '#ef4444' },
    { label: 'Very Unhealthy (201–300)', color: '#a855f7' },
  ];

  // Animation state for the Deck.gl wind particles
  const [time, setTime] = useState(0);

  useEffect(() => {
    let animationFrame;
    const animate = (timestamp) => {
      setTime(timestamp); // Use high-res timestamp natively provided by rAF
      animationFrame = requestAnimationFrame(animate);
    };
    animationFrame = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(animationFrame);
  }, []);

  // Deck.gl WebGL layer for rendering animated wind particles
  const windLayer = new TextLayer({
    id: 'wind-particles',
    data: data.envState.activeWindGrid,
    pickable: false,
    characterSet: ['➔'],
    getText: d => '➔', // Standard arrow character for particle
    getSize: 12, // Reduced size for visual clarity
    getColor: [150, 200, 255, 120], // Light blue with heavy transparency so it doesn't block the map
    getAngle: d => Math.atan2(d.v, d.u) * (180 / Math.PI), // Fixed: Removed negative sign to rotate Counter-Clockwise to North-East
    getPosition: d => {
      const speed = Math.sqrt(d.u * d.u + d.v * d.v);
      const elapsed = time * 0.000002 * speed; 
      
      const offsetX = Math.sign(d.u) * (Math.abs((d.u / speed) * elapsed) % 0.04);
      const offsetY = Math.sign(d.v) * (Math.abs((d.v / speed) * elapsed) % 0.04);
      
      return [d.position[0] + offsetX, d.position[1] + offsetY];
    },
    updateTriggers: {
      getPosition: [time, data.envState.activeWindGrid]
    }
  });

  return (
    <div className="relative w-full h-full">
      {/* AQI Toggle UI Overlay */}
      <div className="absolute top-130 left-4 z-50 pointer-events-auto bg-slate-900/95 text-white px-5 py-3.5 rounded-xl border border-slate-700 shadow-2xl backdrop-blur-md">
        <button
          onClick={() => setIsAqiVisible(!isAqiVisible)}
          className="flex items-center gap-3 select-none cursor-pointer hover:opacity-90 transition-opacity"
        >
          <Activity size={22} className={isAqiVisible ? 'text-emerald-400' : 'text-slate-400'} />
          <span className="text-base font-bold tracking-wide">AQI Grid Layer</span>
          <span className={`ml-2 text-xs font-extrabold px-3 py-1 rounded-md ${isAqiVisible ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40' : 'bg-slate-800 text-slate-400 border border-slate-700'}`}>
            {isAqiVisible ? 'ON' : 'OFF'}
          </span>
        </button>
      </div>

      {/* Bottom-Left: AQI Color Legend */}
      {isAqiVisible && (
        <div className="absolute bottom-6 left-4 z-20 bg-slate-950/90 text-white p-3 rounded-lg border border-slate-800 shadow-2xl backdrop-blur-md w-60">
          <div className="text-[11px] font-bold uppercase tracking-wider text-slate-300 mb-2 border-b border-slate-800 pb-1">
            Air Quality Index (AQI)
          </div>
          <div className="flex flex-col gap-1.5">
            {aqiLegend.map((item, idx) => (
              <div key={idx} className="flex items-center gap-2">
                <span
                  className="w-3.5 h-3.5 rounded-sm border border-black/20 shrink-0"
                  style={{ backgroundColor: item.color }}
                />
                <span className="text-[11px] text-slate-200 font-medium">{item.label}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <DeckGL
        initialViewState={{
          longitude: -122.0828,
          latitude: 37.6688,
          zoom: 11,
          pitch: 60,
          bearing: 15
        }}
        controller={true}
        layers={[windLayer]} // Overlay Deck.gl layer on top of Mapbox
      >
        <Map
          ref={mapRef}
          reuseMaps
          mapStyle="mapbox://styles/mapbox/dark-v11"
          mapboxAccessToken={MAPBOX_TOKEN}
          terrain={{ source: 'mapbox-dem', exaggeration: 1.5 }}
        >
          <Source
            id="mapbox-dem"
            type="raster-dem"
            url="mapbox://mapbox.mapbox-terrain-dem-v1"
            tileSize={512}
            maxzoom={14}
          />

          {/* Layer 1: Real-World AQI Live Sensors */}
          {isAqiVisible && aqiGridData.features.length > 0 && (
            <Source id="aqi-grid-source" type="geojson" data={aqiGridData}>
              {/* Outer glow for heat impact */}
              <Layer
                id="aqi-sensor-glow"
                type="circle"
                paint={{
                  'circle-color': ['get', 'color'],
                  'circle-radius': 28,
                  'circle-blur': 0.8,
                  'circle-opacity': 0.4
                }}
              />
              {/* Sharp sensor center point */}
              <Layer
                id="aqi-sensor-point"
                type="circle"
                paint={{
                  'circle-color': ['get', 'color'],
                  'circle-radius': 8,
                  'circle-stroke-width': 2,
                  'circle-stroke-color': '#ffffff'
                }}
              />
            </Source>
          )}

          {/* Layer 1.5: Red Flag Warning (Renders below fire pixels due to React DOM ordering) */}
          {data.envState.redFlagActive && (
            <Source id="red-flag" type="geojson" data={data.redFlagWarning}>
              <Layer
                id="red-flag-fill"
                type="fill"
                paint={{
                  'fill-color': '#dc2626',
                  'fill-opacity': 0.1
                }}
              />
              <Layer
                id="red-flag-outline"
                type="line"
                paint={{
                  'line-color': '#dc2626',
                  'line-width': 2,
                  'line-dasharray': [2, 2]
                }}
              />
            </Source>
          )}

          <Source id="fire-pixels" type="geojson" data={data.firePixels}>
            <Layer
              id="fire-pixels-layer"
              type="circle"
              paint={{
                'circle-color': '#dc2626',
                'circle-radius': 8,
                'circle-blur': 0.5,
                'circle-opacity': 0.8
              }}
            />
          </Source>

          <Source id="spread-3hr" type="geojson" data={data.spread3Hr}>
            <Layer
              id="spread-3hr-layer"
              type="fill"
              paint={{
                'fill-color': '#eab308',
                'fill-opacity': 0.3
              }}
            />
          </Source>

          <Source id="spread-1hr" type="geojson" data={data.spread1Hr}>
            <Layer
              id="spread-1hr-layer"
              type="fill"
              paint={{
                'fill-color': '#ea580c',
                'fill-opacity': 0.4
              }}
            />
          </Source>

          <Source id="route-safe" type="geojson" data={data.routeSafe}>
            <Layer
              id="route-safe-layer"
              type="line"
              paint={{
                'line-color': '#3b82f6',
                'line-width': 6,
                'line-blur': 1
              }}
            />
          </Source>

          <Source id="route-compromised" type="geojson" data={data.routeCompromised}>
            <Layer
              id="route-compromised-layer"
              type="line"
              paint={{
                'line-color': '#ef4444',
                'line-width': 4,
                'line-dasharray': [2, 2]
              }}
            />
          </Source>

          {/* Layer 5: Evacuation Shelters (Custom HTML Markers) */}
          {data.shelters.features.map((shelter, index) => (
            <Marker
              key={`shelter-${index}`}
              longitude={shelter.geometry.coordinates[0]}
              latitude={shelter.geometry.coordinates[1]}
              anchor="bottom"
            >
              <div className="flex flex-col items-center pointer-events-none">
                <div className="w-8 h-8 bg-green-600 rounded-full flex items-center justify-center border-2 border-white shadow-lg text-white">
                  <ShieldPlus size={18} />
                </div>
                <div className="bg-black/80 backdrop-blur-sm text-white text-xs font-bold px-2 py-1 rounded mt-1 border border-slate-700 shadow-xl whitespace-nowrap">
                  {shelter.properties.name}
                </div>
              </div>
            </Marker>
          ))}

          {/* Layer 6: User Location (Native Mapbox Marker) */}
          {data.userLocation.features[0] && (
            <Marker 
              longitude={data.userLocation.features[0].geometry.coordinates[0]} 
              latitude={data.userLocation.features[0].geometry.coordinates[1]} 
              anchor="bottom"
              color="#3b82f6"
            />
          )}
        </Map>
      </DeckGL>
    </div>
  );
}