import { useRef, useState, useEffect } from 'react';
import Map, { Source, Layer, Marker } from 'react-map-gl/mapbox';
import DeckGL from '@deck.gl/react';
import { TextLayer } from '@deck.gl/layers';
import 'mapbox-gl/dist/mapbox-gl.css';
import { ShieldPlus } from 'lucide-react';

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_ACCESS_TOKEN || 'pk.eyJ1IjoiZGV2IiwiYSI6ImNrbXZ6bHcyZDBhMTEydm8wc3Nqd3o1ZWUifQ.mock';

export default function MapCanvas({ predictions, shelters, windData, alerts, routeData, userLocation }) {
  const mapRef = useRef();
  
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
  // Backend returns windData as array of { position: [lon, lat], u, v }
  const windLayer = new TextLayer({
    id: 'wind-particles',
    data: windData || [],
    pickable: false,
    characterSet: ['➔'],
    getText: () => '➔', 
    getSize: 12, 
    getColor: [150, 200, 255, 120], 
    getAngle: d => Math.atan2(d.v, d.u) * (180 / Math.PI),
    getPosition: d => {
      const speed = Math.sqrt(d.u * d.u + d.v * d.v);
      const elapsed = time * 0.000002 * speed; 
      
      const offsetX = Math.sign(d.u) * (Math.abs((d.u / speed) * elapsed) % 0.04);
      const offsetY = Math.sign(d.v) * (Math.abs((d.v / speed) * elapsed) % 0.04);
      
      return [d.position[0] + offsetX, d.position[1] + offsetY];
    },
    updateTriggers: {
      getPosition: [time, windData]
    }
  });

  return (
    <DeckGL
      initialViewState={{
        longitude: -122.0828,
        latitude: 37.6688,
        zoom: 11,
        pitch: 60,
        bearing: 15
      }}
      controller={true}
      layers={[windLayer]}
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
                // Color scale based on fire_probability
                'fill-color': [
                  'interpolate',
                  ['linear'],
                  ['get', 'fire_probability'],
                  0.0, '#3f3f46',    // Low risk: gray
                  0.4, '#eab308',    // Med risk: yellow
                  0.7, '#ea580c',    // High risk: orange
                  0.9, '#dc2626'     // Critical: red
                ],
                'fill-opacity': 0.4
              }}
            />
          </Source>
        )}

        {/* Safe Evacuation Route from A* */}
        {routeData && (
          <Source id="route-safe" type="geojson" data={routeData}>
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
    </DeckGL>
  );
}
