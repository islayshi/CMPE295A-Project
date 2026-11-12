import React, { useState, useEffect } from 'react';
import { MapContainer, TileLayer, CircleMarker, Popup } from 'react-leaflet';
import DatePicker from 'react-datepicker';
import 'leaflet/dist/leaflet.css';
import 'react-datepicker/dist/react-datepicker.css';

export default function FirmsHotspotMap({ selectedDate, setSelectedDate, formatDateString }) {
  const [availableDates, setAvailableDates] = useState([]);
  const [hotspots, setHotspots] = useState([]);
  const [loading, setLoading] = useState(false);
  const [datesLoading, setDatesLoading] = useState(true);
  const [error, setError] = useState(null);

  // 1. Fetch available dates containing active hotspots dynamically
  useEffect(() => {
    const fetchFirmsDates = async () => {
      setDatesLoading(true);
      try {
        const res = await fetch('/api/telemetry/firms/available-dates/');
        const data = await res.json();
        if (res.ok && data.status === 'success' && data.dates.length > 0) {
          const dateObjs = data.dates.map((d) => new Date(d + 'T00:00:00'));
          setAvailableDates(dateObjs);
          setSelectedDate(dateObjs[0]);
        }
      } catch (err) {
        console.error('Failed to load FIRMS dates:', err);
      } finally {
        setDatesLoading(false);
      }
    };

    fetchFirmsDates();
  }, [setSelectedDate]);

  // 2. Fetch Hotspots when selectedDate changes
  useEffect(() => {
    if (!selectedDate) return;

    const fetchHotspots = async () => {
      setLoading(true);
      setError(null);
      try {
        const dateStr = formatDateString(selectedDate);
        const res = await fetch(`/api/telemetry/firms/?date=${dateStr}`);
        const data = await res.json();

        if (res.ok && data.status === 'success') {
          setHotspots(data.hotspots || []);
        } else {
          throw new Error(data.message || 'Failed to fetch NASA FIRMS telemetry.');
        }
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchHotspots();
  }, [selectedDate, formatDateString]);

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6 relative">
      {/* Header & Controls - High Z-Index Container */}
      <div className="flex flex-wrap items-center justify-between gap-4 mb-6 relative z-[1000]">
        <div>
          <h2 className="text-xl font-semibold text-gray-800">
            NASA FIRMS Active Thermal Anomalies (MODIS / VIIRS)
          </h2>
          <p className="text-sm text-gray-600">
            Near-real-time thermal satellite detections filtered for California WUI zones.
          </p>
        </div>

        {/* Dynamic Dropdown & Custom DatePicker Controls */}
        <div className="flex flex-wrap items-center gap-4 relative z-[1000]">
          <div className="flex items-center gap-2">
            <label className="text-xs font-semibold text-gray-700 uppercase tracking-wider">
              Most recent hotspot sightings:
            </label>
            <select
              value={selectedDate ? formatDateString(selectedDate) : ''}
              onChange={(e) => setSelectedDate(new Date(e.target.value + 'T00:00:00'))}
              disabled={datesLoading || availableDates.length === 0}
              className="px-3 py-1.5 border border-gray-300 rounded-lg text-sm bg-white shadow-sm focus:outline-none focus:ring-2 focus:ring-red-500 font-mono font-medium text-gray-800 cursor-pointer disabled:bg-gray-100 relative z-[1000]"
            >
              {datesLoading ? (
                <option>Loading dates...</option>
              ) : availableDates.length === 0 ? (
                <option>No recent hotspots found</option>
              ) : (
                availableDates.map((d) => {
                  const dateStr = formatDateString(d);
                  return (
                    <option key={dateStr} value={dateStr}>
                      {dateStr}
                    </option>
                  );
                })
              )}
            </select>
          </div>
        </div>
      </div>

      {loading && (
        <div className="p-4 text-center text-sm font-semibold text-red-600 bg-red-50 rounded-xl border border-red-100 animate-pulse mb-4">
          Querying NASA FIRMS telemetry for {selectedDate ? formatDateString(selectedDate) : ''}...
        </div>
      )}

      {error && (
        <div className="p-4 text-sm text-red-700 bg-red-50 rounded-xl border border-red-200 mb-4">
          {error}
        </div>
      )}

      {/* Map Display with lower stack context */}
      <div className="h-[550px] w-full rounded-lg overflow-hidden border border-gray-200 relative z-0">
        <MapContainer center={[37.7, -122.2]} zoom={9} style={{ height: '100%', width: '100%' }}>
          <TileLayer
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          />
          {hotspots.map((h, i) => (
            <CircleMarker
              key={i}
              center={[h.lat, h.lon]}
              radius={Math.max(4, h.brightness ? h.brightness / 70 : 6)}
              pathOptions={{
                color: '#ef4444',
                fillColor: '#f97316',
                fillOpacity: 0.8,
              }}
            >
              <Popup>
                <div className="text-xs space-y-1">
                  <strong className="text-red-600 block text-sm">Thermal Detection</strong>
                  <div>Brightness: <strong>{h.brightness} K</strong></div>
                  <div>FRP: <strong>{h.frp} MW</strong></div>
                  <div>Confidence: <strong>{h.confidence}%</strong></div>
                  <div>Coord: <strong>{h.lat.toFixed(3)}, {h.lon.toFixed(3)}</strong></div>
                </div>
              </Popup>
            </CircleMarker>
          ))}
        </MapContainer>
      </div>

      <div className="mt-3 flex justify-between items-center text-xs text-gray-500">
        <span>Showing <strong>{hotspots.length}</strong> active detection points for {selectedDate ? formatDateString(selectedDate) : ''}</span>
        <span>Source: NASA LANCE / FIRMS VIIRS & MODIS</span>
      </div>
    </div>
  );
}