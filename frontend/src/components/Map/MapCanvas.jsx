import { useRef, useState, useEffect } from 'react';
import Map, { Source, Layer, Marker } from 'react-map-gl/mapbox';
import 'mapbox-gl/dist/mapbox-gl.css';
import WindOverlay from './WindOverlay';
import { ShieldPlus, Activity } from 'lucide-react';
import { fetchLiveAqiCoverage } from './AQIGrid';

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_ACCESS_TOKEN || 'pk.eyJ1IjoiZXZlbiIsImEiOiJjbTFuMmluY3cwM2x3M2pyMGNvbzN2dngzIn0.mock';

export default function MapCanvas({ predictions, shelters, windData, alerts, userLocation }) {
  const mapRef = useRef();

  const [isAqiVisible, setIsAqiVisible] = useState(true);

  const [aqiCoverage, setAqiCoverage] = useState({
    radiusCircle: { type: 'FeatureCollection', features: [] },
    gridGrid: { type: 'FeatureCollection', features: [] }
  });

  useEffect(() => {
    async function loadData() {
      // Using Bay Area coordinates for AQI
      const data = await fetchLiveAqiCoverage(37.6688, -122.0828, 45);
      setAqiCoverage(data);
    }
    loadData();
  }, []);

  // Legend categories definition
  const aqiLegend = [
    { label: 'Good (0–50)', color: '#22c55e' },
    { label: 'Moderate (51–100)', color: '#eab308' },
    { label: 'Unhealthy (Sensitive) (101–150)', color: '#f97316' },
    { label: 'Unhealthy (151–200)', color: '#ef4444' },
    { label: 'Very Unhealthy (201–300)', color: '#a855f7' },
  ];

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

      <Map
        initialViewState={{
          longitude: -122.0828,
          latitude: 37.6688,
          zoom: 11,
          pitch: 0,
          bearing: 15
        }}
        ref={mapRef}
        reuseMaps
        mapStyle="mapbox://styles/mapbox/dark-v11"
        mapboxAccessToken={MAPBOX_TOKEN}
        maxBounds={[
          [-122.90, 36.90],
          [-121.50, 38.30]
        ]}
      >
        {windData && <WindOverlay data={windData} />}

        {/* Layer 1: 45-Mile AQI Radius Coverage & Grid Layer */}
        {isAqiVisible && aqiCoverage?.radiusCircle?.features?.length > 0 && (
          <>
            <Source id="aqi-radius-source" type="geojson" data={aqiCoverage.radiusCircle}>
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

            {aqiCoverage?.gridGrid?.features?.length > 0 && (
              <Source id="aqi-grid-source" type="geojson" data={aqiCoverage.gridGrid}>
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
        )}

        {/* Layer 1.5: Red Flag Warning */}
        {alerts && alerts.features?.length > 0 && (
          <Source id="red-flag" type="geojson" data={alerts}>
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

        {/* Predictions Heatmap Layer */}
        {predictions && (
          <Source id="predictions-heatmap" type="geojson" data={predictions}>
            <Layer
              id="predictions-fill"
              type="fill"
              paint={{
                'fill-color': [
                  'interpolate',
                  ['linear'],
                  ['get', 'fire_probability'],
                  0.0,  '#3f3f46',
                  0.05, '#713f12',
                  0.35, '#eab308',
                  0.60, '#ea580c',
                  0.80, '#dc2626',
                  1.0,  '#7f1d1d'
                ],
                'fill-opacity': [
                  'interpolate',
                  ['linear'],
                  ['get', 'fire_probability'],
                  0.0,  0.0,
                  0.05, 0.15,
                  0.35, 0.45,
                  0.70, 0.70,
                  1.0,  0.85
                ]
              }}
            />
            <Layer
              id="predictions-outline"
              type="line"
              paint={{
                'line-color': [
                  'interpolate',
                  ['linear'],
                  ['get', 'fire_probability'],
                  0.0,  'rgba(0,0,0,0)',
                  0.05, 'rgba(234,179,8,0.3)',
                  0.60, 'rgba(234,88,12,0.5)',
                  1.0,  'rgba(220,38,38,0.7)'
                ],
                'line-width': 0.5
              }}
            />
          </Source>
        )}

        {/* Layer 5: Evacuation Shelters */}
        {shelters?.features?.map((shelter) => (
          <Marker
            key={`shelter-${shelter.properties.id}`}
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

        {/* Layer 6: User Location */}
        {userLocation && (
          <Marker 
            longitude={userLocation.lon} 
            latitude={userLocation.lat} 
            anchor="bottom"
            color="#3b82f6" 
          />
        )}
      </Map>
    </div>
  );
}
