import React, { useState, useEffect } from 'react';

export default function PalisadesTimelinePanel() {
  // Preset historical Palisades fire event dates
  const eventPresets = [
    { label: 'Jan 2021 Palisades Event', date: '2021-01-19' },
    { label: 'May 2021 Palisades Fire Peak', date: '2021-05-15' },
    { label: 'Jan 2025 Pacific Palisades Wind Event', date: '2025-01-07' },
  ];

  const [selectedDate, setSelectedDate] = useState('2021-01-19');
  const [eventData, setEventData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [currentHour, setCurrentHour] = useState(14); // Default to peak fire window (2 PM)
  const [isPlaying, setIsPlaying] = useState(false);

  useEffect(() => {
    fetchPalisadesData();
  }, [selectedDate]);

  // Time-slider auto-play loop (1.2s per hour)
  useEffect(() => {
    let timer;
    if (isPlaying) {
      timer = setInterval(() => {
        setCurrentHour((prev) => (prev >= 23 ? 0 : prev + 1));
      }, 1200);
    }
    return () => clearInterval(timer);
  }, [isPlaying]);

  const fetchPalisadesData = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/telemetry/palisades/?date=${selectedDate}`);
      if (!res.ok) throw new Error(`HTTP Error ${res.status}`);

      const json = await res.json();
      if (json.status === 'success') {
        setEventData(json.data);
      } else {
        setError(json.message || 'Failed to load historical telemetry.');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const timeline = eventData?.timeline || [];
  const activeFrame = timeline.find((t) => t.hour === currentHour) || timeline[0];
  const activeZones = activeFrame?.zones || [];

  return (
    <div className="space-y-6">
      {/* Event Header & Controls */}
      <div className="bg-slate-800 p-5 rounded-xl border border-slate-700 flex flex-wrap justify-between items-center gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-xl font-bold text-white flex items-center gap-2">
              <span className="h-3 w-3 rounded-full bg-red-500 inline-block animate-ping"></span>
              {eventData?.event_name || 'Palisades Fire Multi-Modal Analysis'}
            </h2>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-red-500/20 text-red-300 border border-red-500/40">
              HISTORICAL TELEMETRY REPLAY
            </span>
          </div>
          <p className="text-sm text-slate-400 mt-1">
            Real historical atmospheric reanalysis (NOAA ERA5) combined with USGS 30m DEM terrain slope vectors.
          </p>
        </div>

        {/* Date Selector & Presets */}
        <div className="flex flex-wrap items-center gap-3">
          <label className="text-sm font-medium text-slate-300">Incident Date:</label>
          <input
            type="date"
            value={selectedDate}
            onChange={(e) => {
              setIsPlaying(false);
              setSelectedDate(e.target.value);
            }}
            className="bg-slate-900 border border-slate-700 text-white text-sm rounded-lg p-2 focus:ring-red-500 focus:border-red-500 font-mono"
          />
          <div className="flex gap-1.5">
            {eventPresets.map((preset) => (
              <button
                key={preset.date}
                onClick={() => {
                  setIsPlaying(false);
                  setSelectedDate(preset.date);
                }}
                className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
                  selectedDate === preset.date
                    ? 'bg-red-600 text-white'
                    : 'bg-slate-900 text-slate-400 hover:text-white border border-slate-700'
                }`}
              >
                {preset.label.split(' ')[0]} {preset.label.split(' ')[1]}
              </button>
            ))}
          </div>
        </div>
      </div>

      {loading && (
        <div className="p-12 text-center text-slate-400">
          Querying NOAA ERA5 historical reanalysis archives for {selectedDate}...
        </div>
      )}

      {error && (
        <div className="p-4 bg-red-950/50 border border-red-800 rounded-xl text-red-200">{error}</div>
      )}

      {!loading && !error && activeFrame && (
        <>
          {/* Interactive 24-Hour Timeline Scrubber */}
          <div className="bg-slate-800 p-6 rounded-xl border border-slate-700 space-y-4">
            <div className="flex flex-wrap justify-between items-center gap-4">
              <div className="flex items-center gap-4">
                <button
                  onClick={() => setIsPlaying(!isPlaying)}
                  className={`px-4 py-2 rounded-lg text-sm font-bold flex items-center gap-2 transition-colors ${
                    isPlaying
                      ? 'bg-amber-600 hover:bg-amber-500 text-white'
                      : 'bg-emerald-600 hover:bg-emerald-500 text-white'
                  }`}
                >
                  {isPlaying ? '⏸ Pause Replay' : '▶ Play 24-Hour Loop'}
                </button>
                <div className="text-lg font-mono font-bold text-amber-400">
                  Hour Snapshot: <span className="text-white">{activeFrame.hour_label} Local Time</span>
                </div>
              </div>

              <div className="flex items-center gap-3 text-xs">
                <span className="bg-slate-900 px-3 py-1.5 rounded-lg border border-slate-700 text-slate-300">
                  Target Date: <strong className="text-white font-mono">{eventData.event_date}</strong>
                </span>
                <span className="bg-slate-900 px-3 py-1.5 rounded-lg border border-slate-700 text-slate-300">
                  Max Regional Gust: <strong className="text-amber-400 font-mono">{activeFrame.regional_max_gust} km/h</strong>
                </span>
                <span className="bg-slate-900 px-3 py-1.5 rounded-lg border border-slate-700 text-slate-300">
                  Min RH: <strong className="text-teal-300 font-mono">{activeFrame.regional_min_rh}%</strong>
                </span>
              </div>
            </div>

            {/* Range Input Slider */}
            <div className="space-y-2 pt-2">
              <input
                type="range"
                min="0"
                max="23"
                value={currentHour}
                onChange={(e) => {
                  setIsPlaying(false);
                  setCurrentHour(parseInt(e.target.value));
                }}
                className="w-full h-3 bg-slate-900 rounded-lg appearance-none cursor-pointer accent-red-500 border border-slate-700"
              />
              <div className="flex justify-between text-[11px] font-mono text-slate-400 px-1">
                <span>00:00 (Night)</span>
                <span>06:00 (Dawn)</span>
                <span className="text-amber-400 font-bold">12:00 (Diurnal Peak)</span>
                <span>18:00 (Dusk)</span>
                <span>23:00 (Midnight)</span>
              </div>
            </div>
          </div>

          {/* Micro-Zone Telemetry Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {activeZones.map((z) => (
              <div
                key={z.zone_id}
                className="bg-slate-800 rounded-xl border border-slate-700 p-5 space-y-4 shadow-lg hover:border-slate-600 transition-all"
              >
                {/* Zone Name & Risk Score Meter */}
                <div className="border-b border-slate-700 pb-3">
                  <div className="flex justify-between items-start">
                    <h3 className="font-bold text-white text-md">{z.name}</h3>
                    <span
                      className="px-2.5 py-0.5 rounded-full text-xs font-mono font-bold"
                      style={{ backgroundColor: `${z.color}20`, color: z.color, border: `1px solid ${z.color}50` }}
                    >
                      Risk: {z.risk_score} / 100
                    </span>
                  </div>
                  <div className="text-xs text-slate-400 mt-1">
                    {z.fuel_type} • Slope: <strong className="text-slate-200">{z.slope_deg}° ({z.aspect})</strong>
                  </div>
                </div>

                {/* Multi-Modal Real Metrics Grid */}
                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div className="bg-slate-900/70 p-3 rounded-lg border border-slate-700/60">
                    <span className="text-slate-400 uppercase font-semibold text-[10px]">Peak Wind Gust</span>
                    <div className="text-lg font-black text-amber-400 mt-0.5 font-mono">{z.wind_gust_kmh} km/h</div>
                    <span className="text-[10px] text-slate-400">Steady: {z.wind_speed_kmh} km/h</span>
                  </div>

                  <div className="bg-slate-900/70 p-3 rounded-lg border border-slate-700/60">
                    <span className="text-slate-400 uppercase font-semibold text-[10px]">Relative Humidity</span>
                    <div className="text-lg font-black text-teal-300 mt-0.5 font-mono">{z.rh}%</div>
                    <span className="text-[10px] text-slate-400">Temp: {z.temp_c}°C</span>
                  </div>

                  <div className="bg-slate-900/70 p-3 rounded-lg border border-slate-700/60">
                    <span className="text-slate-400 uppercase font-semibold text-[10px]">Dead Fuel Moisture</span>
                    <div className="text-lg font-black text-yellow-300 mt-0.5 font-mono">{z.fm100}%</div>
                    <span className="text-[10px] text-slate-400">100-Hr Fuel Bed</span>
                  </div>

                  <div className="bg-slate-900/70 p-3 rounded-lg border border-slate-700/60">
                    <span className="text-slate-400 uppercase font-semibold text-[10px]">Energy Release (ERC)</span>
                    <div className="text-lg font-black text-orange-400 mt-0.5 font-mono">{z.erc}</div>
                    <span className="text-[10px] text-slate-400">Elev: {z.elevation_m}m</span>
                  </div>
                </div>

                {/* Fire Behavior Status */}
                <div className="pt-2 border-t border-slate-700 flex justify-between items-center text-xs">
                  <span className="text-slate-400">Fire Behavior Status:</span>
                  <span className="font-bold" style={{ color: z.color }}>
                    {z.spread_behavior}
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