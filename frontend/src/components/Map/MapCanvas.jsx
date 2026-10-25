import { useRef, useState } from 'react';
import Map, { Source, Layer, Marker, Popup } from 'react-map-gl/mapbox';
import 'mapbox-gl/dist/mapbox-gl.css';
import WindOverlay from './WindOverlay';
import { Tent, MapPin, Users, Factory, Flame } from 'lucide-react';
import AQIGrid from './AQIGrid';

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_ACCESS_TOKEN || 'pk.eyJ1IjoiZXZlbiIsImEiOiJjbTFuMmluY3cwM2x3M2pyMGNvbzN2dngzIn0.mock';

export default function MapCanvas({
  predictions,
  shelters,
  windData,
  hotspotsData,
  userLocation,
  isFireRiskVisible = true,
  isHotspotsVisible = true,
  isAqiVisible,
  isSheltersVisible,
  aqiData,
  timeScrub,
}) {
  const mapRef = useRef();
  const [selectedShelter, setSelectedShelter] = useState(null);
  const [selectedHotspot, setSelectedHotspot] = useState(null);

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
              layout={{ visibility: isFireRiskVisible ? 'visible' : 'none' }}
              filter={['==', ['coalesce', ['get', 'horizon_hours'], ['get', 'lead_time_hours'], 0], timeScrub]}
              paint={{
                'fill-color': [
                  'interpolate',
                  ['linear'],
                  ['get', 'fire_probability'],
                  0.0, '#eab308',
                  0.2, '#eab308',
                  0.5, '#f97316',
                  0.8, '#dc2626',
                  1.0, '#991b1b'
                ],
                'fill-opacity': [
                  'interpolate',
                  ['linear'],
                  ['get', 'fire_probability'],
                  0.0, 0.2,
                  1.0, 0.8
                ]
              }}
            />
            <Layer
              id="predictions-outline"
              type="line"
              layout={{ visibility: isFireRiskVisible ? 'visible' : 'none' }}
              filter={['==', ['coalesce', ['get', 'horizon_hours'], ['get', 'lead_time_hours'], 0], timeScrub]}
              paint={{
                'line-color': [
                  'interpolate',
                  ['linear'],
                  ['get', 'fire_probability'],
                  0.0, '#eab308',
                  0.2, '#eab308',
                  0.5, '#f97316',
                  0.8, '#dc2626',
                  1.0, '#991b1b'
                ],
                'line-width': 1
              }}
            />
          </Source>
        )}

        {/* Layer: NASA FIRMS Satellite Hotspots (ground truth across all time horizons) */}
        {isHotspotsVisible && hotspotsData?.features?.map((feature, idx) => {
          const coords = feature.geometry?.coordinates;
          if (!coords || coords.length < 2 || typeof coords[0] !== 'number' || typeof coords[1] !== 'number' || isNaN(coords[0]) || isNaN(coords[1])) {
            return null;
          }
          const isFlare = feature.properties?.is_industrial_flare;
          const key = `firms-hotspot-${idx}-${coords[0]}-${coords[1]}`;

          return (
            <Marker
              key={key}
              longitude={coords[0]}
              latitude={coords[1]}
              anchor="center"
            >
              {isFlare ? (
                <div
                  className="flex items-center justify-center bg-slate-700 text-slate-100 rounded-full border border-slate-300 shadow-md hover:scale-125 hover:bg-slate-800 transition-all cursor-pointer p-1"
                  onMouseEnter={() => {
                    setSelectedShelter(null);
                    setSelectedHotspot(feature);
                  }}
                  onMouseLeave={() => setSelectedHotspot(null)}
                  onClick={(e) => {
                    e.originalEvent?.stopPropagation();
                    setSelectedShelter(null);
                    setSelectedHotspot(feature);
                  }}
                >
                  <Factory size={12} strokeWidth={2.2} />
                </div>
              ) : (
                <div
                  className="relative flex items-center justify-center cursor-pointer p-1"
                  onMouseEnter={() => {
                    setSelectedShelter(null);
                    setSelectedHotspot(feature);
                  }}
                  onMouseLeave={() => setSelectedHotspot(null)}
                  onClick={(e) => {
                    e.originalEvent?.stopPropagation();
                    setSelectedShelter(null);
                    setSelectedHotspot(feature);
                  }}
                >
                  <span className="animate-ping absolute inline-flex h-4 w-4 rounded-full bg-rose-500 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-3 w-3 bg-rose-600 border border-white shadow-md"></span>
                </div>
              )}
            </Marker>
          );
        })}

        {/* Hotspot Hover Popup */}
        {isHotspotsVisible && selectedHotspot && (
          <Popup
            longitude={selectedHotspot.geometry.coordinates[0]}
            latitude={selectedHotspot.geometry.coordinates[1]}
            anchor="bottom"
            offset={15}
            closeButton={false}
            closeOnClick={false}
            className="z-50 pointer-events-none"
          >
            <div className="flex flex-col min-w-[220px] -m-3">
              <div className={`px-3 py-2 border-b rounded-t-lg backdrop-blur-sm ${
                selectedHotspot.properties?.is_industrial_flare
                  ? 'bg-slate-100 border-slate-200 text-slate-800'
                  : 'bg-rose-50 border-rose-200 text-rose-900'
              }`}>
                <h3 className="font-bold text-xs leading-tight flex items-center gap-1.5">
                  {selectedHotspot.properties?.is_industrial_flare ? (
                    <>
                      <Factory size={13} className="text-slate-600 shrink-0" />
                      <span>Industrial Heat Source (Suppressed)</span>
                    </>
                  ) : (
                    <>
                      <Flame size={13} className="text-rose-600 shrink-0" />
                      <span>Active Wildland Detection</span>
                    </>
                  )}
                </h3>
              </div>
              <div className="p-3 bg-white/95 backdrop-blur-sm rounded-b-lg flex flex-col gap-1.5 text-xs text-slate-700">
                {selectedHotspot.properties?.is_industrial_flare && (
                  <div className="bg-slate-100 p-1.5 rounded text-[11px] text-slate-600 border border-slate-200">
                    Suppressed: <span className="font-semibold text-slate-800">{selectedHotspot.properties?.flare_site_name || 'Industrial Facility'}</span> (Flaring Zone)
                  </div>
                )}
                <div className="flex justify-between items-center">
                  <span className="text-slate-500 text-[11px]">Sensor / Satellite:</span>
                  <span className="font-semibold">{selectedHotspot.properties?.satellite || 'VIIRS'}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-slate-500 text-[11px]">Fire Radiative Power:</span>
                  <span className="font-semibold">{selectedHotspot.properties?.frp ? `${selectedHotspot.properties.frp} MW` : 'N/A'}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-slate-500 text-[11px]">Confidence:</span>
                  <span className="capitalize font-semibold">{selectedHotspot.properties?.confidence || 'Nominal'}</span>
                </div>
                {(selectedHotspot.properties?.acq_date || selectedHotspot.properties?.acq_time) && (
                  <div className="flex justify-between items-center text-[10px] text-slate-400 pt-1 border-t border-slate-100">
                    <span>Acquisition:</span>
                    <span>{selectedHotspot.properties.acq_date} {selectedHotspot.properties.acq_time ? `${selectedHotspot.properties.acq_time} UTC` : ''}</span>
                  </div>
                )}
              </div>
            </div>
          </Popup>
        )}

        {/* Layer 5: Evacuation Shelters */}
        {isSheltersVisible && shelters?.features?.map((shelter) => (
          <Marker
            key={`shelter-${shelter.properties.id}`}
            longitude={shelter.geometry.coordinates[0]}
            latitude={shelter.geometry.coordinates[1]}
            anchor="bottom"
          >
            <div 
              className="flex items-center justify-center bg-blue-500 text-white rounded-full border-2 border-white shadow-md hover:scale-110 hover:shadow-lg hover:bg-blue-600 transition-all cursor-pointer p-1.5"
              onMouseEnter={() => {
                setSelectedHotspot(null);
                setSelectedShelter(shelter);
              }}
              onMouseLeave={() => setSelectedShelter(null)}
              onClick={(e) => {
                e.originalEvent?.stopPropagation();
                setSelectedHotspot(null);
                setSelectedShelter(shelter);
              }}
            >
              <Tent size={14} strokeWidth={2.5} />
            </div>
          </Marker>
        ))}

        {/* Shelter Info Hover Popup */}
        {isSheltersVisible && selectedShelter && (
          <Popup
            longitude={selectedShelter.geometry.coordinates[0]}
            latitude={selectedShelter.geometry.coordinates[1]}
            anchor="bottom"
            offset={30}
            closeButton={false}
            closeOnClick={false}
            className="z-50 pointer-events-none"
          >
            <div className="flex flex-col min-w-[200px] -m-3">
              <div className="bg-blue-50/80 px-3 py-2 border-b border-blue-100/50 rounded-t-lg backdrop-blur-sm">
                <h3 className="font-bold text-slate-800 text-sm leading-tight">{selectedShelter.properties.name}</h3>
              </div>
              <div className="p-3 bg-white/95 backdrop-blur-sm rounded-b-lg flex flex-col gap-2">
                {selectedShelter.properties.address && (
                  <div className="flex items-start gap-2 text-slate-600">
                    <MapPin size={14} className="shrink-0 mt-0.5 text-blue-500" />
                    <span className="text-xs leading-tight">{selectedShelter.properties.address}</span>
                  </div>
                )}
                {selectedShelter.properties.capacity && (
                  <div className="flex items-center gap-2 text-slate-600">
                    <Users size={14} className="shrink-0 text-blue-500" />
                    <span className="text-xs font-medium">Capacity: {selectedShelter.properties.capacity}</span>
                  </div>
                )}
                {selectedShelter.properties.source && (
                  <div className="mt-1 pt-2 border-t border-slate-100 flex items-center justify-between">
                    <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">Source</span>
                    <span className="text-[10px] bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded font-bold">{selectedShelter.properties.source}</span>
                  </div>
                )}
              </div>
            </div>
          </Popup>
        )}

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
