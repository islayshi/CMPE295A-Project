import React, { useState, useEffect } from 'react';

export default function RtmaPanel() {
  const todayStr = new Date().toISOString().split('T')[0];
  const [selectedDate, setSelectedDate] = useState(todayStr);
  const [rtmaData, setRtmaData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchRtma();
  }, [selectedDate]);

  const fetchRtma = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/telemetry/rtma/?date=${selectedDate}`);
      if (!res.ok) throw new Error(`HTTP Error ${res.status}`);

      const json = await res.json();
      if (json.status === 'success') {
        setRtmaData(json.data);
      } else {
        setError(json.message || 'Failed to load RTMA telemetry.');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const zones = rtmaData?.zones || [];
  const summary = rtmaData?.summary;

  // Date constraints (Archive available up to 90 days back, no future dates)
  const maxDate = rtmaData?.max_available_date || todayStr;
  const minDate = rtmaData?.min_available_date || '';

  return (
    <div className="space-y-6">
      {/* Top Controls & Date Selector */}
      <div className="bg-slate-800 p-4 rounded-xl border border-slate-700 flex flex-wrap justify-between items-center gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-xl font-bold text-white flex items-center gap-2">
              <span className="h-3 w-3 rounded-full bg-cyan-400 inline-block animate-pulse"></span>
              NOAA RTMA 2.5km Real-Time Mesoscale Weather
            </h2>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-cyan-500/20 text-cyan-300 border border-cyan-500/40">
              HOURLY ANALYSIS
            </span>
          </div>
          <p className="text-sm text-slate-400 mt-1">
            2.5km spatial resolution hourly weather analysis (Temperature, Humidity, Wind Vectors & Peak Gusts).
          </p>
        </div>

        <div className="flex items-center gap-3">
          <label className="text-sm font-medium text-slate-300">Observation Date:</label>
          <input
            type="date"
            value={selectedDate}
            min={minDate}
            max={maxDate}
            onChange={(e) => setSelectedDate(e.target.value)}
            className="bg-slate-900 border border-slate-700 text-white text-sm rounded-lg p-2 focus:ring-cyan-500 focus:border-cyan-500"
          />
        </div>
      </div>

      {loading && (
        <div className="p-12 text-center text-slate-400">Fetching NOAA RTMA 2.5km surface mesh analysis...</div>
      )}

      {error && (
        <div className="p-4 bg-red-950/50 border border-red-800 rounded-xl text-red-200">{error}</div>
      )}

      {!loading && !error && rtmaData && (
        <>
          {/* Top KPI Summary */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-slate-800/80 p-4 rounded-xl border border-slate-700/80">
              <span className="text-xs font-semibold text-slate-400 uppercase">Analysis Time</span>
              <div className="text-lg font-bold text-cyan-400 mt-1">{rtmaData.observed_hour}</div>
              <span className="text-xs text-slate-400">Date: {rtmaData.observation_date}</span>
            </div>

            <div className="bg-slate-800/80 p-4 rounded-xl border border-slate-700/80">
              <span className="text-xs font-semibold text-slate-400 uppercase">Peak Regional Gust</span>
              <div className="text-2xl font-black text-amber-400 mt-1">{summary?.peakGust} <span className="text-xs text-slate-400 font-normal">km/h</span></div>
              <span className="text-xs text-slate-400">10m Wind Speed Field</span>
            </div>

            <div className="bg-slate-800/80 p-4 rounded-xl border border-slate-700/80">
              <span className="text-xs font-semibold text-slate-400 uppercase">Lowest Relative Humidity</span>
              <div className="text-2xl font-black text-teal-400 mt-1">{summary?.lowestRh}%</div>
              <span className="text-xs text-slate-400">Surface Air Dryness</span>
            </div>

            <div className="bg-slate-800/80 p-4 rounded-xl border border-slate-700/80">
              <span className="text-xs font-semibold text-slate-400 uppercase">Data Provider</span>
              <div className="text-sm font-bold text-blue-400 mt-2">{rtmaData.provider}</div>
            </div>
          </div>

          {/* Live Operational Status Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {zones.map((z) => (
              <div
                key={z.id}
                className="bg-slate-800 rounded-xl border border-slate-700 p-5 space-y-4 hover:border-slate-600 transition-all shadow-md"
              >
                {/* Zone Header */}
                <div className="flex justify-between items-start border-b border-slate-700/70 pb-3">
                  <div>
                    <h3 className="font-bold text-white text-md">{z.name}</h3>
                    <div className="text-xs text-slate-400 font-mono mt-0.5">
                      {z.lat}, {z.lng}
                    </div>
                  </div>
                  <span
                    className="px-2.5 py-1 rounded-full text-xs font-bold border"
                    style={{
                      borderColor: `${z.color}50`,
                      backgroundColor: `${z.color}15`,
                      color: z.color,
                    }}
                  >
                    {z.cardinal} @ {z.wind_kmh} km/h
                  </span>
                </div>

                {/* Weather Indicators */}
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div className="bg-slate-900/60 p-3 rounded-lg border border-slate-700/50">
                    <span className="text-xs text-slate-400 uppercase block font-medium">Temperature</span>
                    <span className="text-xl font-black text-white mt-1 block">
                      {z.temp_c}°C <span className="text-xs text-slate-400 font-normal">({z.temp_f}°F)</span>
                    </span>
                  </div>

                  <div className="bg-slate-900/60 p-3 rounded-lg border border-slate-700/50">
                    <span className="text-xs text-slate-400 uppercase block font-medium">Relative Humidity</span>
                    <span className="text-xl font-black text-teal-300 mt-1 block">
                      {z.rh}%
                    </span>
                  </div>

                  <div className="bg-slate-900/60 p-3 rounded-lg border border-slate-700/50">
                    <span className="text-xs text-slate-400 uppercase block font-medium">Wind Speed</span>
                    <span className="text-xl font-black text-blue-400 mt-1 block">
                      {z.wind_kmh} <span className="text-xs text-slate-400 font-normal">km/h</span>
                    </span>
                  </div>

                  <div className="bg-slate-900/60 p-3 rounded-lg border border-slate-700/50">
                    <span className="text-xs text-slate-400 uppercase block font-medium">Peak Gusts</span>
                    <span className="text-xl font-black text-amber-400 mt-1 block">
                      {z.gust_kmh} <span className="text-xs text-slate-400 font-normal">km/h</span>
                    </span>
                  </div>
                </div>

                {/* Operational Status Footer */}
                <div className="pt-2 border-t border-slate-700/70 flex justify-between items-center text-xs">
                  <span className="text-slate-400">Fire Weather Status:</span>
                  <span className="font-semibold" style={{ color: z.color }}>
                    {z.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}