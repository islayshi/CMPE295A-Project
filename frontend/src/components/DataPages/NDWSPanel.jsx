import React, { useState, useEffect } from 'react';
import { MapContainer, TileLayer, Circle, Popup, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

// Map Recenter Helper Component
function MapRecenter({ center }) {
  const map = useMap();
  useEffect(() => {
    if (center) map.setView(center, 10);
  }, [center, map]);
  return null;
}

export default function NdwsPanel({ selectedDate, formatDateString }) {
  const [incidentsList, setIncidentsList] = useState([]);
  const [selectedIncident, setSelectedIncident] = useState('LNU Lightning Complex (2020)');
  const [telemetry, setTelemetry] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [comparisonMode, setComparisonMode] = useState('side-by-side');

  // Load available incidents list on mount
  useEffect(() => {
    fetchIncidentsList();
  }, []);

  // Fetch telemetry whenever selectedIncident changes
  useEffect(() => {
    if (selectedIncident) fetchNdwsTelemetry();
  }, [selectedIncident]);

  const fetchIncidentsList = async () => {
    try {
      const res = await fetch('/api/telemetry/ndws/?list_all=true');
      const data = await res.json();
      if (data.status === 'success' && data.incidents) {
        setIncidentsList(data.incidents);
      }
    } catch (err) {
      console.error('Failed to load incidents list:', err);
    }
  };

  const fetchNdwsTelemetry = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/telemetry/ndws/?incident=${encodeURIComponent(selectedIncident)}`);
      if (!res.ok) throw new Error(`HTTP Error ${res.status}`);
      const data = await res.json();
      if (data.status === 'success') {
        setTelemetry(data);
      } else {
        setError(data.message || 'Failed to fetch NDWS telemetry.');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const event = telemetry?.event;
  const centerCoords = event?.center || [38.52, -122.28];

  return (
    <div className="space-y-6">
      {/* Top Header & Selector */}
      <div className="bg-slate-800 p-4 rounded-xl border border-slate-700 flex flex-wrap justify-between items-center gap-4">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <span className="h-3 w-3 rounded-full bg-emerald-500 inline-block animate-pulse"></span>
            NDWS Major Wildfire Incident Inspector (2006–2026)
          </h2>
          <p className="text-sm text-slate-400">
            Comparing $T_0$ initial perimeters against $T_{+1}$ 24-hour expansion across major historical fires.
          </p>
        </div>

        {/* Dropdown Selector */}
        <div className="flex items-center gap-3">
          <label className="text-xs font-semibold text-slate-400 uppercase">Select Incident:</label>
          <select
            value={selectedIncident}
            onChange={(e) => setSelectedIncident(e.target.value)}
            className="bg-slate-900 border border-slate-700 text-white text-xs rounded-lg p-2.5 font-bold"
          >
            {incidentsList.map((inc) => (
              <option key={inc} value={inc}>{inc}</option>
            ))}
          </select>

          <div className="flex bg-slate-900 p-1 rounded-lg border border-slate-700 text-xs font-semibold">
            <button
              onClick={() => setComparisonMode('side-by-side')}
              className={`px-3 py-1.5 rounded-md transition-colors ${
                comparisonMode === 'side-by-side' ? 'bg-red-600 text-white' : 'text-slate-400 hover:text-white'
              }`}
            >
              Side-by-Side
            </button>
            <button
              onClick={() => setComparisonMode('overlay')}
              className={`px-3 py-1.5 rounded-md transition-colors ${
                comparisonMode === 'overlay' ? 'bg-red-600 text-white' : 'text-slate-400 hover:text-white'
              }`}
            >
              Overlay
            </button>
          </div>
        </div>
      </div>

      {loading && (
        <div className="p-12 text-center text-slate-400">Loading incident spatial telemetry...</div>
      )}

      {!loading && !error && event && (
        <div className="space-y-6">
          {/* Key Metrics Header Bar */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="bg-slate-800 p-4 rounded-xl border border-slate-700">
              <span className="text-xs font-semibold text-slate-400 uppercase">Baseline Time (T₀)</span>
              <div className="text-sm font-bold text-amber-400 mt-1">{event.t0_date}</div>
              <div className="text-xs text-slate-400 mt-1">{event.acreage_t0.toLocaleString()} acres</div>
            </div>

            <div className="bg-slate-800 p-4 rounded-xl border border-slate-700">
              <span className="text-xs font-semibold text-slate-400 uppercase">Next-Day Time (T₊₁)</span>
              <div className="text-sm font-bold text-red-400 mt-1">{event.t1_date}</div>
              <div className="text-xs text-slate-400 mt-1">{event.acreage_t1.toLocaleString()} acres</div>
            </div>

            <div className="bg-slate-800 p-4 rounded-xl border border-slate-700">
              <span className="text-xs font-semibold text-slate-400 uppercase">24h Expansion</span>
              <div className="text-2xl font-black text-orange-400 mt-1">+{event.growth_pct}%</div>
              <div className="text-xs text-slate-400 mt-1">Observed Spread</div>
            </div>

            <div className="bg-slate-800 p-4 rounded-xl border border-slate-700">
              <span className="text-xs font-semibold text-slate-400 uppercase">Centroid Location</span>
              <div className="text-sm font-mono font-bold text-slate-200 mt-1">
                {event.center[0]}, {event.center[1]}
              </div>
              <div className="text-xs text-slate-400 mt-1">{event.county} County</div>
            </div>
          </div>

          {/* SIDE-BY-SIDE MAPS */}
          {comparisonMode === 'side-by-side' && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Day 0 Map */}
              <div className="bg-slate-800 p-5 rounded-xl border border-slate-700 flex flex-col">
                <div className="flex justify-between items-center mb-3">
                  <span className="text-sm font-bold text-amber-400 uppercase">{event.name} — T₀ Initial</span>
                  <span className="text-xs font-mono text-slate-400">{event.t0_date}</span>
                </div>
                <div className="w-full h-80 rounded-lg overflow-hidden border border-slate-700">
                  <MapContainer center={centerCoords} zoom={10} style={{ height: '100%', width: '100%' }}>
                    <MapRecenter center={centerCoords} />
                    <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
                    <Circle
                      center={centerCoords}
                      radius={event.radius_t0_m}
                      pathOptions={{ color: '#f59e0b', fillColor: '#f59e0b', fillOpacity: 0.6 }}
                    >
                      <Popup>T0 Active Perimeter: {event.acreage_t0.toLocaleString()} acres</Popup>
                    </Circle>
                  </MapContainer>
                </div>
              </div>

              {/* Day 1 Map */}
              <div className="bg-slate-800 p-5 rounded-xl border border-slate-700 flex flex-col">
                <div className="flex justify-between items-center mb-3">
                  <span className="text-sm font-bold text-red-400 uppercase">{event.name} — T₊₁ Expansion</span>
                  <span className="text-xs font-mono text-slate-400">{event.t1_date}</span>
                </div>
                <div className="w-full h-80 rounded-lg overflow-hidden border border-slate-700">
                  <MapContainer center={centerCoords} zoom={10} style={{ height: '100%', width: '100%' }}>
                    <MapRecenter center={centerCoords} />
                    <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
                    <Circle
                      center={centerCoords}
                      radius={event.radius_t1_m}
                      pathOptions={{ color: '#ef4444', fillColor: '#ef4444', fillOpacity: 0.5 }}
                    >
                      <Popup>T+1 Expanded Perimeter: {event.acreage_t1.toLocaleString()} acres</Popup>
                    </Circle>
                  </MapContainer>
                </div>
              </div>
            </div>
          )}

          {/* OVERLAY MAP */}
          {comparisonMode === 'overlay' && (
            <div className="bg-slate-800 p-5 rounded-xl border border-slate-700 flex flex-col">
              <div className="flex justify-between items-center mb-3">
                <span className="text-sm font-bold text-white uppercase">{event.name} — Spatial Overlay</span>
                <div className="flex gap-4 text-xs font-semibold">
                  <span className="text-amber-400">● T₀ ({event.t0_date})</span>
                  <span className="text-red-400">● T₊₁ ({event.t1_date})</span>
                </div>
              </div>
              <div className="w-full h-96 rounded-lg overflow-hidden border border-slate-700">
                <MapContainer center={centerCoords} zoom={10} style={{ height: '100%', width: '100%' }}>
                  <MapRecenter center={centerCoords} />
                  <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
                  <Circle
                    center={centerCoords}
                    radius={event.radius_t1_m}
                    pathOptions={{ color: '#ef4444', fillColor: '#ef4444', fillOpacity: 0.4 }}
                  />
                  <Circle
                    center={centerCoords}
                    radius={event.radius_t0_m}
                    pathOptions={{ color: '#f59e0b', fillColor: '#f59e0b', fillOpacity: 0.8 }}
                  />
                </MapContainer>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}