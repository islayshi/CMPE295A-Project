import React, { useEffect, useState } from 'react';
import { MapContainer, TileLayer, LayersControl } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

const DEFAULT_CENTER = [37.5, -122.1]; // Bay Area / NorCal center
const DEFAULT_ZOOM = 9;

export default function WildfireMap() {
  const [ndviTileUrl, setNdviTileUrl] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    // Fetch live tile URL template from Django backend
    fetch('http://127.0.0.1:8000/api/telemetry/gee/ndvi-tile/')
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
        return res.json();
      })
      .then((data) => {
        if (data.status === 'success' && data.tile_url) {
          setNdviTileUrl(data.tile_url);
        } else {
          throw new Error(data.message || 'Failed to retrieve NDVI tile URL');
        }
      })
      .catch((err) => {
        console.error('Error fetching GEE tile layer:', err);
        setError(err.message);
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <div style={{ height: '100vh', width: '100%' }}>
      <MapContainer 
        center={DEFAULT_CENTER} 
        zoom={DEFAULT_ZOOM} 
        style={{ height: '100%', width: '100%' }}
      >
        <LayersControl position="topright">
          {/* Base Map */}
          <LayersControl.BaseLayer checked name="CartoDB Dark Matter">
            <TileLayer
              url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
              attribution='&copy; <a href="https://carto.com/">CARTO</a>'
            />
          </LayersControl.BaseLayer>

          {/* Dynamic GEE Vegetation Dryness Overlay */}
          <LayersControl.Overlay checked name="Sentinel-2 Vegetation Dryness (NDVI)">
            {ndviTileUrl && (
              <TileLayer
                url={ndviTileUrl}
                opacity={0.7}
                maxZoom={18}
                attribution="Google Earth Engine | Sentinel-2"
              />
            )}
          </LayersControl.Overlay>
        </LayersControl>
      </MapContainer>

      {loading && (
        <div style={overlayStatusStyle}>Loading GEE Satellite Layer...</div>
      )}
      {error && (
        <div style={{ ...overlayStatusStyle, color: '#f44336' }}>
          Failed to load vegetation layer: {error}
        </div>
      )}
    </div>
  );
}

const overlayStatusStyle = {
  position: 'absolute',
  top: '10px',
  left: '50px',
  zIndex: 1000,
  background: 'rgba(0,0,0,0.8)',
  color: '#fff',
  padding: '8px 12px',
  borderRadius: '4px',
  fontSize: '14px',
};