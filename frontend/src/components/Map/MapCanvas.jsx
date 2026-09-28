import { useRef } from 'react';
import Map, { Source, Layer, Marker } from 'react-map-gl/mapbox';
import 'mapbox-gl/dist/mapbox-gl.css';
import WindOverlay from './WindOverlay';
import { ShieldPlus } from 'lucide-react';

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_ACCESS_TOKEN || 'pk.eyJ1IjoiZGV2IiwiYSI6ImNrbXZ6bHcyZDBhMTEydm8wc3Nqd3o1ZWUifQ.mock';

export default function MapCanvas({ predictions, shelters, windData, alerts, userLocation }) {
  const mapRef = useRef();
  
  // Animation state for the Deck.gl wind particles
  

  // Deck.gl WebGL layer for rendering animated wind particles
  // Backend returns windData as array of { position: [lon, lat], u, v }
  

  return (
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
          [-122.90, 36.90], // Southwest coordinates (lng, lat) (Aligned with BayAreaGrid)
          [-121.50, 38.30]  // Northeast coordinates (lng, lat) (Aligned with BayAreaGrid)
        ]}
      >
        {windData && <WindOverlay data={windData} />}



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

        {/* Predictions Heatmap Layer — color AND opacity scale with fire_probability */}
        {predictions && (
          <Source id="predictions-heatmap" type="geojson" data={predictions}>
            <Layer
              id="predictions-fill"
              type="fill"
              paint={{
                // Red-orange-yellow gradient: higher probability = deeper red
                'fill-color': [
                  'interpolate',
                  ['linear'],
                  ['get', 'fire_probability'],
                  0.0,  '#3f3f46',  // Very low:  dark gray (nearly invisible)
                  0.05, '#713f12',  // Low:       dark brown-orange
                  0.35, '#eab308',  // Medium:    yellow
                  0.60, '#ea580c',  // High:      orange
                  0.80, '#dc2626',  // Critical:  red
                  1.0,  '#7f1d1d'   // Extreme:   deep red
                ],
                // Opacity also scales so high-risk cells stand out
                'fill-opacity': [
                  'interpolate',
                  ['linear'],
                  ['get', 'fire_probability'],
                  0.0,  0.0,   // Zero probability: fully transparent
                  0.05, 0.15,  // Low:  barely visible
                  0.35, 0.45,  // Med:  clearly visible
                  0.70, 0.70,  // High: prominent
                  1.0,  0.85   // Extreme: near-solid
                ]
              }}
            />
            {/* Subtle stroke so 1x1 km cell borders are discernible at zoom 11 */}
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
    
  );
}
