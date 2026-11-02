import React, { useState, useEffect } from 'react';
import { MapContainer, TileLayer, CircleMarker, Popup } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

const YEARS = ['2020', '2021', '2022', '2023', '2024', '2025', '2026'];

const CYCLES = [
  { id: '01', label: 'Jan (Cycle 01)' },
  { id: '05', label: 'Mar (Cycle 05)' },
  { id: '09', label: 'May (Cycle 09)' },
  { id: '13', label: 'Jul (Cycle 13)' },
  { id: '17', label: 'Sep (Cycle 17)' },
  { id: '21', label: 'Nov (Cycle 21)' },
];

export default function ViirsPanel() {
  const [selectedYear, setSelectedYear] = useState('2024');
  const [selectedCycle, setSelectedCycle] = useState('17');
  const [viirsData, setViirsData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchViirsTelemetry();
  }, [selectedYear, selectedCycle]);

  const fetchViirsTelemetry = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/telemetry/viirs/?year=${selectedYear}&cycle=${selectedCycle}`);
      if (!res.ok) throw new Error(`HTTP Error ${res.status}`);
      const result = await res.json();
      if (result.status === 'success') {
        setViirsData(result.data);
      } else {
        setError('Failed to query NASA Earthdata API.');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const bayAreaCenter = [38.10, -122.40];

  return (
    <div className="space-y-6">
      {/* Top Header & Date Pickers */}
      <div className="bg-slate-800 p-4 rounded-xl border border-slate-700 flex flex-wrap justify-between items-center gap-4">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <span className="h-3 w-3 rounded-full bg-emerald-500 inline-block animate-pulse"></span>
            NASA VIIRS Telemetry Stream (VNP13A1)
          </h2>
          <p className="text-sm text-slate-400">
            500m 16-day canopy sampling via NASA Earthdata CMR API.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <select
            value={selectedYear}
            onChange={(e) => setSelectedYear(e.target.value)}
            className="bg-slate-900 border border-slate-700 text-white text-xs rounded-lg p-2.5 font-bold"
          >
            {YEARS.map((yr) => (
              <option key={yr} value={yr}>{yr}</option>
            ))}
          </select>

          <div className="flex items-center gap-1 bg-slate-900 p-1 rounded-xl border border-slate-700 text-xs">
            {CYCLES.map((c) => (
              <button
                key={c.id}
                onClick={() => setSelectedCycle(c.id)}
                className={`px-2.5 py-1.5 rounded-lg font-semibold transition-all ${
                  selectedCycle === c.id
                    ? 'bg-emerald-600 text-white shadow-md'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                {c.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {loading && (
        <div className="p-12 text-center text-slate-400">Connecting to NASA Earthdata CMR STAC API...</div>
      )}

      {error && (
        <div className="p-4 bg-red-950/50 border border-red-800 rounded-xl text-red-200">{error}</div>
      )}

      {!loading && !error && viirsData && (
        <div className="space-y-6">
          {/* Metadata Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-slate-800 p-4 rounded-xl border border-slate-700">
              <span className="text-xs font-semibold text-slate-400 uppercase">NASA Granule Handle</span>
              <div className="text-xs font-mono font-bold text-emerald-400 truncate mt-2">
                {viirsData.granule_id}
              </div>
            </div>

            <div className="bg-slate-800 p-4 rounded-xl border border-slate-700">
              <span className="text-xs font-semibold text-slate-400 uppercase">Observation Window</span>
              <div className="text-xs font-bold text-white mt-2">{viirsData.datetime_range}</div>
            </div>

            <div className="bg-slate-800 p-4 rounded-xl border border-slate-700">
              <span className="text-xs font-semibold text-slate-400 uppercase">Data Provider</span>
              <div className="text-sm font-bold text-blue-400 mt-2">{viirsData.provider}</div>
            </div>
          </div>

          {/* Leaflet Map Renderer */}
          <div className="bg-slate-800 p-5 rounded-xl border border-slate-700">
            <div className="flex justify-between items-center mb-3">
              <span className="text-sm font-bold text-white uppercase">
                Regional Vegetation Risk Map ({viirsData.year} - Cycle {viirsData.cycle})
              </span>
              <span className="text-xs font-mono bg-slate-900 text-emerald-400 px-3 py-1 rounded border border-slate-700">
                Direct LP DAAC Stream
              </span>
            </div>

            <div className="w-full h-96 rounded-lg overflow-hidden border border-slate-700">
              <MapContainer center={bayAreaCenter} zoom={8} style={{ height: '100%', width: '100%' }}>
                <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />

                {viirsData.zones.map((z) => (
                  <CircleMarker
                    key={z.id}
                    center={[z.lat, z.lng]}
                    radius={20}
                    pathOptions={{
                      color: z.color,
                      fillColor: z.color,
                      fillOpacity: 0.65,
                      weight: 2,
                    }}
                  >
                    <Popup>
                      <div className="p-1 space-y-1 text-slate-900 font-sans">
                        <div className="font-bold text-sm">{z.name}</div>
                        <div className="text-xs">
                          <span className="font-semibold">NDVI Score: </span>
                          <span className="font-mono font-bold">{z.ndvi}</span>
                        </div>
                        <div className="text-xs">
                          <span className="font-semibold">Status: </span>
                          <span>{z.status}</span>
                        </div>
                      </div>
                    </Popup>
                  </CircleMarker>
                ))}
              </MapContainer>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}