import React, { useState, useEffect } from 'react';

export default function GridmetPanel() {
  const todayStr = new Date().toISOString().split('T')[0];
  const [selectedDate, setSelectedDate] = useState(todayStr);
  const [gridmetData, setGridmetData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Determine if the selected date is in the future
  const isFutureDate = selectedDate > todayStr;

  useEffect(() => {
    fetchGridmet();
  }, [selectedDate]);

  const fetchGridmet = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/telemetry/gridmet/?date=${selectedDate}`);
      const data = await res.json();
      if (data.status === 'success') {
        setGridmetData(data);
      } else {
        setError(data.message || 'Failed to load GRIDMET telemetry.');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Header Controls */}
      <div className="bg-slate-800 p-4 rounded-xl border border-slate-700 flex flex-wrap justify-between items-center gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-xl font-bold text-white flex items-center gap-2">
              <span className="h-3 w-3 rounded-full bg-amber-500 inline-block"></span>
              GRIDMET Fire Weather Surface Meteorology
            </h2>

            {/* Dynamic Status Badge */}
            {isFutureDate ? (
              <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/20 text-amber-300 border border-amber-500/40 animate-pulse flex items-center gap-1">
                <span className="h-1.5 w-1.5 rounded-full bg-amber-400"></span>
                PREDICTED MODEL FORECAST
              </span>
            ) : (
              <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 flex items-center gap-1">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400"></span>
                RECORDED OBSERVATION
              </span>
            )}
          </div>

          <p className="text-sm text-slate-400 mt-1">
            {isFutureDate 
              ? "Displaying projected fire-weather variables from ensemble meteorological forecast models."
              : "Daily 4km high-resolution surface observations (Temperatures, Wind, Humidity, Precipitation, and ERC)."
            }
          </p>
        </div>

        <div className="flex items-center gap-3">
          <label className="text-sm font-medium text-slate-300">Target Date:</label>
          <input
            type="date"
            value={selectedDate}
            onChange={(e) => setSelectedDate(e.target.value)}
            className="bg-slate-900 border border-slate-700 text-white text-sm rounded-lg p-2 focus:ring-amber-500 focus:border-amber-500"
          />
        </div>
      </div>

      {/* Warning Notice Banner for Future Dates */}
      {isFutureDate && (
        <div className="p-3 bg-amber-950/40 border border-amber-800/60 rounded-xl text-amber-200 text-sm flex items-center gap-3">
          <span className="text-lg">⚠️</span>
          <div>
            <span className="font-semibold">Forecast Mode Active:</span> You are viewing projected surface weather for {selectedDate}. These values represent model predictions and may differ from final post-processed GRIDMET observations.
          </div>
        </div>
      )}

      {loading && (
        <div className="p-12 text-center text-slate-400">Loading GRIDMET surface telemetry...</div>
      )}

      {error && (
        <div className="p-4 bg-red-950/50 border border-red-800 rounded-xl text-red-200">
          {error}
        </div>
      )}

      {!loading && !error && gridmetData && (
        <>
          {/* Summary KPI Cards */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <div className="bg-slate-800/80 p-4 rounded-xl border border-slate-700/80 relative overflow-hidden">
              <span className="text-xs font-semibold text-slate-400 uppercase">Avg Max Temp</span>
              <div className="text-2xl font-black text-amber-400 mt-1">
                {gridmetData.summary.avgMaxTemp}°C
              </div>
              {isFutureDate && <span className="text-[10px] text-amber-500 font-medium">Model Est.</span>}
            </div>

            <div className="bg-slate-800/80 p-4 rounded-xl border border-slate-700/80">
              <span className="text-xs font-semibold text-slate-400 uppercase">Peak Wind Speed</span>
              <div className="text-2xl font-black text-blue-400 mt-1">
                {gridmetData.summary.peakWindSpeed} <span className="text-xs text-slate-400">km/h</span>
              </div>
              {isFutureDate && <span className="text-[10px] text-amber-500 font-medium">Model Est.</span>}
            </div>

            <div className="bg-slate-800/80 p-4 rounded-xl border border-slate-700/80">
              <span className="text-xs font-semibold text-slate-400 uppercase">Lowest RH</span>
              <div className="text-2xl font-black text-teal-400 mt-1">
                {gridmetData.summary.lowestRh}%
              </div>
              {isFutureDate && <span className="text-[10px] text-amber-500 font-medium">Model Est.</span>}
            </div>

            <div className="bg-slate-800/80 p-4 rounded-xl border border-slate-700/80">
              <span className="text-xs font-semibold text-slate-400 uppercase">Avg Precip</span>
              <div className="text-2xl font-black text-cyan-400 mt-1">
                {gridmetData.summary.avgPrecip} <span className="text-xs text-slate-400">mm</span>
              </div>
              {isFutureDate && <span className="text-[10px] text-amber-500 font-medium">Model Est.</span>}
            </div>

            <div className="bg-slate-800/80 p-4 rounded-xl border border-slate-700/80 col-span-2 md:col-span-1">
              <span className="text-xs font-semibold text-slate-400 uppercase">ET / ERC Proxy</span>
              <div className="text-2xl font-black text-orange-400 mt-1">
                {gridmetData.summary.avgErcProxy} <span className="text-xs text-slate-400">mm</span>
              </div>
              {isFutureDate && <span className="text-[10px] text-amber-500 font-medium">Model Est.</span>}
            </div>
          </div>

          {/* Sub-region Grid Table */}
          <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-700 font-semibold text-white flex justify-between items-center">
              <span>SF Bay Area GRIDMET 4km Grid Centroid Breakdown</span>
              {isFutureDate && (
                <span className="text-xs font-normal text-amber-400 bg-amber-950/60 px-2 py-1 rounded border border-amber-800/60">
                  Predicted Values
                </span>
              )}
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm text-slate-300">
                <thead className="bg-slate-900/60 text-slate-400 uppercase text-xs">
                  <tr>
                    <th className="px-6 py-3">Sub-Region / Station</th>
                    <th className="px-6 py-3">Coordinates</th>
                    <th className="px-6 py-3">Max Temp (tmmx)</th>
                    <th className="px-6 py-3">Wind Speed (vs)</th>
                    <th className="px-6 py-3">Min RH (rmin)</th>
                    <th className="px-6 py-3">Precip (pr)</th>
                    <th className="px-6 py-3">ERC Proxy (ET)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-700/50">
                  {gridmetData.gridPoints.map((pt, idx) => (
                    <tr key={idx} className="hover:bg-slate-700/30 transition-colors">
                      <td className="px-6 py-4 font-medium text-white">{pt.location}</td>
                      <td className="px-6 py-4 text-xs font-mono text-slate-400">
                        {pt.lat}, {pt.lon}
                      </td>
                      <td className="px-6 py-4 text-amber-300 font-bold">
                        {pt.metrics.tmmx.value ?? 'N/A'}°C
                      </td>
                      <td className="px-6 py-4 text-blue-300">
                        {pt.metrics.vs.value ?? 'N/A'} km/h
                      </td>
                      <td className="px-6 py-4 text-teal-300">
                        {pt.metrics.rmin.value ?? 'N/A'}%
                      </td>
                      <td className="px-6 py-4 text-cyan-300">
                        {pt.metrics.pr.value ?? 'N/A'} mm
                      </td>
                      <td className="px-6 py-4 text-orange-300 font-semibold">
                        {pt.metrics.erc.value ?? 'N/A'} mm
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}