import { useRef } from 'react';
import Map, { Source, Layer, Marker } from 'react-map-gl/mapbox';
import 'mapbox-gl/dist/mapbox-gl.css';
import WindOverlay from './WindOverlay';
import { ShieldPlus } from 'lucide-react';
import AQIGrid from './AQIGrid';

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_ACCESS_TOKEN || 'pk.eyJ1IjoiZXZlbiIsImEiOiJjbTFuMmluY3cwM2x3M2pyMGNvbzN2dngzIn0.mock';

export default function MapCanvas({ predictions, shelters, windData, userLocation, isAqiVisible, aqiData }) {
  const mapRef = useRef();

  return (
    <div className="relative w-full h-full">

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
        mapStyle="mapbox://styles/mapbox/outdoors-v12"
        mapboxAccessToken={MAPBOX_TOKEN}
        maxBounds={[
          [-122.90, 36.90],
          [-121.50, 38.30]
        ]}
      >
        {windData && <WindOverlay data={windData} />}

        {/* Layer 1: 45-Mile AQI Radius Coverage & Grid Layer */}
        <AQIGrid 
          isAqiVisible={isAqiVisible} 
          aqiSensors={aqiData?.sensors} 
        />

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
