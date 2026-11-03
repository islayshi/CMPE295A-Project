import React, { useState, useEffect } from 'react';

export default function UsgsPanel() {
  const [usgsData, setUsgsData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedZoneId, setSelectedZoneId] = useState(null);

  useEffect(() => {
    fetchUsgs();
  }, []);

  const fetchUsgs = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/telemetry/usgs/');
      if (!res.ok) throw new Error(`HTTP Error ${res.status}`);

      const json = await res.json();
      if (json.status === 'success') {
        setUsgsData(json.data);
        if (json.data?.zones?.length > 0) {
          setSelectedZoneId(json.data.zones[0].id);
        }
      } else {
        setError(json.message || 'Failed to load USGS telemetry.');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const zones = usgsData?.zones || [];
  const selectedZone = zones.find((z) => z.id === selectedZoneId) || zones[0];
  const maxElevation = Math.max(...zones.map((z) => z.elevation_m), 1);

  return (
    <div className="space-y-6">
      {/* Top Controls & Baseline Metadata */}
      <div className="bg-slate-800 p-4 rounded-xl border border-slate-700 flex flex-wrap justify-between items-center gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-xl font-bold text-white flex items-center gap-2">
              <span className="h-3 w-3 rounded-full bg-emerald-500 inline-block animate-pulse"></span>
              USGS 30m Physical Terrain & Topography
            </h2>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
              STATIC DEM BASELINE
            </span>
          </div>
          <p className="text-sm text-slate-400 mt-1">
            Baseline topographic geometry modeling slope acceleration vectors and solar aspect orientation.
          </p>
        </div>

        <div className="flex items-center gap-2 bg-slate-900 px-3 py-1.5 rounded-lg border border-slate-700 text-xs text-slate-300 font-mono">
          <span>Resolution: 1 Arc-Second (~30m)</span>
        </div>
      </div>

      {loading && (
        <div className="p-12 text-center text-slate-400">Loading USGS DEM Digital Elevation Model...</div>
      )}

      {error && (
        <div className="p-4 bg-red-950/50 border border-red-800 rounded-xl text-red-200">{error}</div>
      )}

      {!loading && !error && usgsData && (
        <>
          {/* Top KPI Cards */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="bg-slate-800/80 p-4 rounded-xl border border-slate-700/80">
              <span className="text-xs font-semibold text-slate-400 uppercase">Dataset</span>
              <div className="text-lg font-bold text-emerald-400 mt-1">{usgsData.dataset}</div>
              <span className="text-xs text-slate-400">Shuttle Radar Topography Mission</span>
            </div>

            <div className="bg-slate-800/80 p-4 rounded-xl border border-slate-700/80">
              <span className="text-xs font-semibold text-slate-400 uppercase">Mean Region Elevation</span>
              <div className="text-2xl font-black text-amber-400 mt-1">{usgsData.avg_elevation_m} m</div>
              <span className="text-xs text-slate-400">~{Math.round(usgsData.avg_elevation_m * 3.28084)} ft above sea level</span>
            </div>

            <div className="bg-slate-800/80 p-4 rounded-xl border border-slate-700/80">
              <span className="text-xs font-semibold text-slate-400 uppercase">Steepest Slope Zone</span>
              <div className="text-lg font-bold text-red-400 mt-1">Santa Cruz Mountains</div>
              <span className="text-xs text-slate-400">31° Slope Gradient</span>
            </div>

            <div className="bg-slate-800/80 p-4 rounded-xl border border-slate-700/80">
              <span className="text-xs font-semibold text-slate-400 uppercase">Data Provider</span>
              <div className="text-sm font-bold text-blue-400 mt-2">{usgsData.provider}</div>
            </div>
          </div>

          {/* Interactive Profile & Visual Elevation Bars */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            
            {/* Left Column: Visual Zone Selector & Elevation Bars */}
            <div className="lg:col-span-2 bg-slate-800 p-6 rounded-xl border border-slate-700 space-y-4">
              <h3 className="text-md font-bold text-white flex justify-between items-center">
                <span>Northern California Regional Elevation Profile</span>
                <span className="text-xs font-normal text-slate-400">Click zone to inspect terrain dynamics</span>
              </h3>

              <div className="space-y-3 pt-2">
                {zones.map((z) => {
                  const percentage = Math.round((z.elevation_m / maxElevation) * 100);
                  const isSelected = z.id === selectedZone?.id;

                  return (
                    <div
                      key={z.id}
                      onClick={() => setSelectedZoneId(z.id)}
                      className={`p-3 rounded-lg border cursor-pointer transition-all ${
                        isSelected
                          ? 'bg-slate-700/90 border-emerald-500 shadow-md'
                          : 'bg-slate-900/50 border-slate-700/60 hover:bg-slate-700/40'
                      }`}
                    >
                      <div className="flex justify-between items-center mb-1.5 text-sm">
                        <span className="font-semibold text-white flex items-center gap-2">
                          <span className="h-2 w-2 rounded-full" style={{ backgroundColor: z.color }}></span>
                          {z.name}
                        </span>
                        <span className="font-mono text-emerald-400 font-bold">
                          {z.elevation_m} m <span className="text-xs text-slate-400 font-normal">({z.elevation_ft} ft)</span>
                        </span>
                      </div>

                      {/* Visual Elevation Progress Bar */}
                      <div className="w-full bg-slate-800 rounded-full h-2 overflow-hidden border border-slate-700/50">
                        <div
                          className="bg-gradient-to-r from-emerald-500 via-amber-500 to-red-500 h-2 rounded-full transition-all duration-500"
                          style={{ width: `${percentage}%` }}
                        ></div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Right Column: Selected Zone Terrain Detail Inspector */}
            {selectedZone && (
              <div className="bg-slate-800 p-6 rounded-xl border border-slate-700 flex flex-col justify-between space-y-6">
                <div>
                  <div className="border-b border-slate-700 pb-3 mb-4">
                    <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Topographic Inspector</span>
                    <h3 className="text-xl font-bold text-white mt-1">{selectedZone.name}</h3>
                    <div className="text-xs font-mono text-slate-400 mt-0.5">
                      Coordinates: {selectedZone.lat}, {selectedZone.lng}
                    </div>
                  </div>

                  <div className="space-y-4">
                    <div className="bg-slate-900/80 p-3.5 rounded-lg border border-slate-700/70 flex justify-between items-center">
                      <span className="text-sm text-slate-400">Elevation</span>
                      <span className="text-lg font-bold text-emerald-400 font-mono">
                        {selectedZone.elevation_m} m ({selectedZone.elevation_ft} ft)
                      </span>
                    </div>

                    <div className="bg-slate-900/80 p-3.5 rounded-lg border border-slate-700/70 flex justify-between items-center">
                      <span className="text-sm text-slate-400">Slope Gradient</span>
                      <span className="text-lg font-bold text-amber-300 font-mono">
                        {selectedZone.slope_deg}° Slope
                      </span>
                    </div>

                    <div className="bg-slate-900/80 p-3.5 rounded-lg border border-slate-700/70 flex justify-between items-center">
                      <span className="text-sm text-slate-400">Solar Aspect</span>
                      <span className="text-lg font-bold text-teal-300 font-mono">
                        {selectedZone.aspect}
                      </span>
                    </div>

                    <div className="bg-slate-900/80 p-3.5 rounded-lg border border-slate-700/70">
                      <span className="text-xs text-slate-400 uppercase font-semibold">Slope Risk Status</span>
                      <div className="text-sm font-bold mt-1" style={{ color: selectedZone.color }}>
                        {selectedZone.terrain_risk}
                      </div>
                    </div>
                  </div>
                </div>

                <div className="bg-amber-950/30 border border-amber-800/50 p-3 rounded-lg text-xs text-amber-200">
                  💡 <span className="font-semibold">Fire Behavior Note:</span> Slopes exceeding 20° leaning toward South/West orientations experience accelerated convective pre-heating during uphill fire runs.
                </div>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}