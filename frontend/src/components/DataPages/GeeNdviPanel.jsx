import React, { useState, useEffect } from 'react';
import { MapContainer, TileLayer, LayersControl } from 'react-leaflet';
import DatePicker from 'react-datepicker';
import 'leaflet/dist/leaflet.css';
import 'react-datepicker/dist/react-datepicker.css';

export default function GeeNdviPanel({ selectedDate, setSelectedDate, formatDateString }) {
  const [availableDates, setAvailableDates] = useState([]);
  const [ndviTileUrl, setNdviTileUrl] = useState(null);
  const [isGeeLoading, setIsGeeLoading] = useState(false);
  const [geeError, setGeeError] = useState(null);

  // 1. Fetch available dates from API
  useEffect(() => {
    const fetchAvailableDates = async () => {
      try {
        const res = await fetch('http://127.0.0.1:8000/api/telemetry/gee/available-dates/');
        const data = await res.json();
        if (res.ok && data.status === 'success') {
          const dateObjects = data.dates.map(dateStr => new Date(dateStr + 'T00:00:00'));
          setAvailableDates(dateObjects);
          if (dateObjects.length > 0) {
            setSelectedDate(dateObjects[dateObjects.length - 1]);
          }
        }
      } catch (err) {
        console.error('Failed to fetch GEE available dates:', err);
      }
    };

    fetchAvailableDates();
  }, [setSelectedDate]);

  // 2. Fetch GEE Tile when selectedDate updates
  useEffect(() => {
    const fetchGeeTile = async () => {
      setIsGeeLoading(true);
      setGeeError(null);

      try {
        const dateStr = formatDateString(selectedDate);
        const startDate = new Date(selectedDate.getTime() - 15 * 24 * 60 * 60 * 1000);
        const startDateStr = formatDateString(startDate);

        const url = `http://127.0.0.1:8000/api/telemetry/gee/ndvi-tile/?start_date=${startDateStr}&end_date=${dateStr}`;
        
        const res = await fetch(url);
        const data = await res.json();
        
        if (res.ok && data.status === 'success') {
          setNdviTileUrl(data.tile_url);
        } else {
          throw new Error(data.message || 'Failed to fetch satellite layer.');
        }
      } catch (err) {
        setGeeError(err.message);
      } finally {
        setIsGeeLoading(false);
      }
    };

    fetchGeeTile();
  }, [selectedDate, formatDateString]);

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden p-6">
      <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
        <div>
          <h2 className="text-xl font-semibold text-gray-800">
            Google Earth Engine (GEE) - Sentinel-2 NDVI
          </h2>
          <p className="text-sm text-gray-600">
            Multi-spectral surface reflectance and vegetation dryness index for fuel assessment.
          </p>
        </div>

        <div className="flex items-center gap-2 relative z-10">
          <label className="text-sm font-medium text-gray-700">Target Date:</label>
          <DatePicker
            selected={selectedDate}
            onChange={(date) => setSelectedDate(date)}
            includeDates={availableDates}
            dateFormat="yyyy-MM-dd"
            placeholderText="Select date with data"
            className="px-3 py-1.5 border border-gray-300 rounded-lg text-sm bg-white shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 cursor-pointer"
          />
        </div>
      </div>

      {isGeeLoading && (
        <div className="p-8 text-center text-sm font-semibold text-blue-600 bg-blue-50 rounded-xl border border-blue-100 animate-pulse mb-4">
          Fetching live satellite raster composite from Google Earth Engine...
        </div>
      )}

      {geeError && (
        <div className="p-4 text-sm text-red-700 bg-red-50 rounded-xl border border-red-200 mb-4">
          Failed to load satellite tiles: {geeError}
        </div>
      )}

      <div className="h-[550px] w-full rounded-lg overflow-hidden border border-gray-200 relative">
        <MapContainer center={[37.6, -122.1]} zoom={9} style={{ height: '100%', width: '100%' }}>
          <LayersControl position="topright">
            <LayersControl.BaseLayer checked name="OpenStreetMap Standard">
              <TileLayer
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
              />
            </LayersControl.BaseLayer>

            <LayersControl.BaseLayer name="Esri World Imagery">
              <TileLayer
                url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
                attribution="Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community"
              />
            </LayersControl.BaseLayer>

            <LayersControl.Overlay checked name="Sentinel-2 Vegetation Dryness (NDVI)">
              {ndviTileUrl && (
                <TileLayer
                  url={ndviTileUrl}
                  opacity={0.75}
                  maxZoom={18}
                  attribution="Google Earth Engine | Sentinel-2"
                />
              )}
            </LayersControl.Overlay>
          </LayersControl>
        </MapContainer>
      </div>
    </div>
  );
}