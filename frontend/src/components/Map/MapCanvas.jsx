import { useRef, useState, useEffect } from 'react';
import Map, { Source, Layer, Marker } from 'react-map-gl/mapbox';
import DeckGL from '@deck.gl/react';
import { TextLayer } from '@deck.gl/layers';
import 'mapbox-gl/dist/mapbox-gl.css';
import { getMapData } from '../../mockData/geojsonStates';
import { ShieldPlus } from 'lucide-react';

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_ACCESS_TOKEN || 'pk.eyJ1IjoiZGV2IiwiYSI6ImNrbXZ6bHcyZDBhMTEydm8wc3Nqd3o1ZWUifQ.mock';

export default function MapCanvas({ scenarioState, timeScrub }) {
  const mapRef = useRef();
  const data = getMapData(scenarioState, timeScrub);
  
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
      // Drastically slowed down modifier to create a gentle, ambient flow
      const elapsed = time * 0.000002 * speed; 
      
      // Calculate offset so arrows "flow" continuously across their grid bounds
      // using modulo. Math.sign handles negative vectors smoothly.
      const offsetX = Math.sign(d.u) * (Math.abs((d.u / speed) * elapsed) % 0.04);
      const offsetY = Math.sign(d.v) * (Math.abs((d.v / speed) * elapsed) % 0.04);
      
      return [d.position[0] + offsetX, d.position[1] + offsetY];
    },
    updateTriggers: {
      getPosition: [time, data.envState.activeWindGrid]
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
            color="#3b82f6" // Nice vibrant blue to match the route
          />
        )}
      </Map>
    </DeckGL>
  );
}
