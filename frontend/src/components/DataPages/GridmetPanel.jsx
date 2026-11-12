import React, { useState, useEffect } from 'react';

export default function GridmetPanel() {
  const todayStr = new Date().toISOString().split('T')[0];
  const [selectedDate, setSelectedDate] = useState(todayStr);
  const [gridmetData, setGridmetData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchGridmet();
  }, [selectedDate]);

  const fetchGridmet = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/telemetry/gridmet/?date=${selectedDate}`);
      if (!res.ok) throw new Error(`HTTP Error ${res.status}`);

      const json = await res.json();
      if (json.status === 'success') {
        // Target the inner 'data' block directly
        setGridmetData(json.data);
      } else {
        setError(json.message || 'Failed to load GRIDMET telemetry.');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const zones = gridmetData?.zones || [];

  return (
    <div className="space-y-6">
      {/* Top Header Controls */}
      <div className="bg-slate-800 p-4 rounded-xl border border-slate-700 flex flex-wrap justify-between items-center gap-4">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <span className="h-3 w-3 rounded-full bg-amber-500 inline-block animate-pulse"></span>
            GridMET Fuel Moisture & Drought Telemetry
          </h2>
          <p className="text-sm text-slate-400 mt-1">
            ~4km daily surface fuel dryness (FM100, ERC, and VPD indicators).
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

      {loading && (
        <div className="p-12 text-center text-slate-400">Loading GridMET telemetry...</div>
      )}

      {error && (
        <div className="p-4 bg-red-950/50 border border-red-800 rounded-xl text-red-200">
          {error}
        </div>
      )}

      {!loading && !error && gridmetData && (
        <>
          {/* Summary KPI Cards */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="bg-slate-800/80 p-4 rounded-xl border border-slate-700/80">
              <span className="text-xs font-semibold text-slate-400 uppercase">Mean 100-Hr Fuel Moisture</span>
              <div className="text-2xl font-black text-amber-400 mt-1">
                {gridmetData?.summary?.avgFm100 ?? 'N/A'}%
              </div>
              <span className="text-xs text-slate-400">Dead Fuel Moisture (FM100)</span>
            </div>

            <div className="bg-slate-800/80 p-4 rounded-xl border border-slate-700/80">
              <span className="text-xs font-semibold text-slate-400 uppercase">Mean ERC Index</span>
              <div className="text-2xl font-black text-red-400 mt-1">
                {gridmetData?.summary?.avgErc ?? 'N/A'}
              </div>
              <span className="text-xs text-slate-400">Energy Release Component</span>
            </div>

            <div className="bg-slate-800/80 p-4 rounded-xl border border-slate-700/80">
              <span className="text-xs font-semibold text-slate-400 uppercase">Observation Date</span>
              <div className="text-lg font-bold text-white mt-1">
                {gridmetData?.observation_date ?? selectedDate}
              </div>
              <span className="text-xs text-slate-400">Resolution: ~4km Daily Grid</span>
            </div>

            <div className="bg-slate-800/80 p-4 rounded-xl border border-slate-700/80">
              <span className="text-xs font-semibold text-slate-400 uppercase">Data Provider</span>
              <div className="text-sm font-bold text-blue-400 mt-2">
                {gridmetData?.provider ?? 'GridMET 4km Engine'}
              </div>
            </div>
          </div>

          {/* Sub-region Grid Table matching your API output */}
          <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-700 font-semibold text-white flex justify-between items-center">
              <span>Northern California Target Zones</span>
              <span className="text-xs font-mono bg-slate-900 text-amber-400 px-3 py-1 rounded border border-slate-700">
                GridMET Stream
              </span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm text-slate-300">
                <thead className="bg-slate-900/60 text-slate-400 uppercase text-xs">
                  <tr>
                    <th className="px-6 py-3">Zone / Station</th>
                    <th className="px-6 py-3">Coordinates</th>
                    <th className="px-6 py-3">100-Hr Fuel Moisture</th>
                    <th className="px-6 py-3">ERC Index</th>
                    <th className="px-6 py-3">VPD (kPa)</th>
                    <th className="px-6 py-3">Fire Risk Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-700/50">
                  {zones.map((z) => (
                    <tr key={z.id} className="hover:bg-slate-700/30 transition-colors">
                      <td className="px-6 py-4 font-medium text-white">{z.name}</td>
                      <td className="px-6 py-4 text-xs font-mono text-slate-400">
                        {z.lat}, {z.lng}
                      </td>
                      <td className="px-6 py-4 text-amber-300 font-bold">
                        {z.fm100}%
                      </td>
                      <td className="px-6 py-4 text-red-400 font-bold">
                        {z.erc}
                      </td>
                      <td className="px-6 py-4 text-teal-300 font-mono">
                        {z.vpd}
                      </td>
                      <td className="px-6 py-4 font-semibold" style={{ color: z.color }}>
                        {z.status}
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