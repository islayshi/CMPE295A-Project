import { useRef } from 'react';
import Map, { Source, Layer, Marker } from 'react-map-gl/mapbox';
import 'mapbox-gl/dist/mapbox-gl.css';
import WindOverlay from './WindOverlay';
import { ShieldPlus } from 'lucide-react';
import AQIGrid from './AQIGrid';

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_ACCESS_TOKEN || 'pk.eyJ1IjoiZXZlbiIsImEiOiJjbTFuMmluY3cwM2x3M2pyMGNvbzN2dngzIn0.mock';

export default function MapCanvas({ predictions, shelters, windData, userLocation, isAqiVisible, aqiData, timeScrub }) {
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
        projection="mercator"
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
              filter={['<=', ['coalesce', ['get', 'horizon_hours'], ['get', 'lead_time_hours'], 0], timeScrub]}
              paint={{
                'fill-color': [
                  'match',
                  ['get', 'risk_label'],
                  'ACTIVE_FIRE', '#dc2626',
                  'HIGH_RISK', '#f97316',
                  'MODERATE_RISK', '#eab308',
                  'LOW_RISK', '#4ade80',
                  '#dc2626'
                ],
                'fill-opacity': [
                  'match',
                  ['get', 'risk_label'],
                  'ACTIVE_FIRE', 0.8,
                  'HIGH_RISK', 0.6,
                  'MODERATE_RISK', 0.4,
                  'LOW_RISK', 0.2,
                  0.5
                ]
              }}
            />
            <Layer
              id="predictions-outline"
              type="line"
              filter={['<=', ['coalesce', ['get', 'horizon_hours'], ['get', 'lead_time_hours'], 0], timeScrub]}
              paint={{
                'line-color': [
                  'match',
                  ['get', 'risk_label'],
                  'ACTIVE_FIRE', '#dc2626',
                  'HIGH_RISK', '#f97316',
                  'MODERATE_RISK', '#eab308',
                  'LOW_RISK', '#4ade80',
                  '#dc2626'
                ],
                'line-width': 1
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
