import React, { useState } from 'react';

// Color badge logic for AQI levels
const getAqiBadge = (aqi) => {
  if (aqi <= 50) return <span className="px-2 py-0.5 text-xs font-semibold rounded bg-emerald-100 text-emerald-800">Good ({aqi})</span>;
  if (aqi <= 100) return <span className="px-2 py-0.5 text-xs font-semibold rounded bg-yellow-100 text-yellow-800">Moderate ({aqi})</span>;
  if (aqi <= 150) return <span className="px-2 py-0.5 text-xs font-semibold rounded bg-amber-100 text-amber-800">Unhealthy for Sensitive ({aqi})</span>;
  return <span className="px-2 py-0.5 text-xs font-semibold rounded bg-rose-100 text-rose-800">Unhealthy ({aqi})</span>;
};

const AirQualityTable = ({ telemetryData, selectedDate, onDateChange, bayAreaStations }) => {
  const [subTab, setSubTab] = useState('raw'); // 'raw' | 'stations'
  const [selectedStation, setSelectedStation] = useState('ALL');
  const [searchTerm, setSearchTerm] = useState('');

  // Filter rows by Date, Selected Bay Area Station, and Search Query
  const filteredRows = telemetryData.filter((row) => {
    const matchesDate = !selectedDate || row.timestamp.startsWith(selectedDate);
    const matchesStation = selectedStation === 'ALL' || row.stationId === selectedStation;
    const matchesSearch =
      row.stationName.toLowerCase().includes(searchTerm.toLowerCase()) ||
      row.stationId.toLowerCase().includes(searchTerm.toLowerCase()) ||
      row.subRegion.toLowerCase().includes(searchTerm.toLowerCase());

    return matchesDate && matchesStation && matchesSearch;
  });

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm font-sans">
      
      {/* Header & Main Controls */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 mb-6 border-b border-gray-100 pb-4">
        
        {/* Sub-Tabs */}
        <div className="flex gap-2">
          <button
            onClick={() => setSubTab('raw')}
            className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors ${
              subTab === 'raw'
                ? 'bg-gray-900 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            Raw Telemetry Stream (.CSV)
          </button>
          <button
            onClick={() => setSubTab('stations')}
            className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors ${
              subTab === 'stations'
                ? 'bg-gray-900 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            Bay Area Stations Overview
          </button>
        </div>

        {/* Filters: Station Dropdown + Search + Date */}
        <div className="flex flex-wrap items-center gap-3">
          
          {/* SF Bay Area Station Selector */}
          <div className="flex items-center gap-2 bg-gray-50 px-3 py-1.5 border border-gray-200 rounded-lg">
            <label htmlFor="station-select" className="text-xs font-semibold text-gray-500 uppercase">
              Station:
            </label>
            <select
              id="station-select"
              value={selectedStation}
              onChange={(e) => setSelectedStation(e.target.value)}
              className="text-xs font-medium text-gray-800 bg-transparent outline-none cursor-pointer max-w-[200px]"
            >
              <option value="ALL">All SF Bay Area Stations</option>
              {bayAreaStations.map((st) => (
                <option key={st.id} value={st.id}>
                  {st.name} ({st.subRegion})
                </option>
              ))}
            </select>
          </div>

          {/* Date Picker Filter */}
          <div className="flex items-center gap-2 bg-gray-50 px-3 py-1.5 border border-gray-200 rounded-lg">
            <label htmlFor="aqi-date" className="text-xs font-semibold text-gray-500 uppercase">
              Date:
            </label>
            <input
              id="aqi-date"
              type="date"
              value={selectedDate}
              onChange={(e) => onDateChange(e.target.value)}
              className="text-xs font-mono text-gray-800 bg-transparent outline-none cursor-pointer"
            />
          </div>

          {/* Quick Search */}
          <input
            type="text"
            placeholder="Search city/county..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="px-3 py-1.5 text-xs border border-gray-200 rounded-lg outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
      </div>

      {/* CSV Data Table View */}
      {subTab === 'raw' ? (
        <div className="overflow-x-auto">
          <table className="w-full text-left font-mono text-xs">
            <thead className="bg-gray-100 text-gray-700 uppercase tracking-wider">
              <tr>
                <th className="p-3 border-b">Timestamp</th>
                <th className="p-3 border-b">Station ID</th>
                <th className="p-3 border-b">Station Name</th>
                <th className="p-3 border-b">Region</th>
                <th className="p-3 border-b">PM2.5 (µg/m³)</th>
                <th className="p-3 border-b">PM10 (µg/m³)</th>
                <th className="p-3 border-b">AQI Level</th>
                <th className="p-3 border-b">Coordinates</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 bg-white">
              {filteredRows.length > 0 ? (
                filteredRows.map((row) => (
                  <tr key={row.id} className="hover:bg-gray-50 transition-colors">
                    <td className="p-3 text-gray-600">{row.timestamp}</td>
                    <td className="p-3 font-bold text-gray-900">{row.stationId}</td>
                    <td className="p-3 text-gray-800 font-sans">{row.stationName}</td>
                    <td className="p-3 font-sans">
                      <span className="bg-gray-100 text-gray-600 text-[10px] px-2 py-0.5 rounded font-semibold">
                        {row.subRegion}
                      </span>
                    </td>
                    <td className="p-3 text-gray-900 font-bold">{row.pm25}</td>
                    <td className="p-3 text-gray-600">{row.pm10}</td>
                    <td className="p-3 font-sans">{getAqiBadge(row.aqi)}</td>
                    <td className="p-3 text-gray-400">{row.lat}, {row.lon}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan="8" className="p-6 text-center text-gray-400 font-sans">
                    No telemetry records found for <span className="font-mono">{selectedDate || 'selected criteria'}</span>.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      ) : (
        /* Bay Area Stations Summary Cards */
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {bayAreaStations
            .filter((st) => selectedStation === 'ALL' || st.id === selectedStation)
            .map((station) => {
              const stationLogs = filteredRows.filter((r) => r.stationId === station.id);
              const latest = stationLogs[stationLogs.length - 1];

              return (
                <div key={station.id} className="p-4 bg-gray-50 rounded-xl border border-gray-200 flex flex-col justify-between">
                  <div>
                    <div className="flex justify-between items-start mb-1">
                      <h4 className="font-bold text-gray-900 text-sm">{station.name}</h4>
                      <span className="text-[10px] bg-blue-50 text-blue-700 font-semibold px-2 py-0.5 rounded">
                        {station.subRegion}
                      </span>
                    </div>
                    <p className="text-xs text-gray-500 font-mono mb-3">
                      ID: {station.id} • {station.lat}, {station.lon}
                    </p>
                  </div>

                  <div className="flex justify-between items-center border-t border-gray-200/60 pt-3 mt-2">
                    <span className="text-xs text-gray-500">
                      {latest ? `Latest: ${latest.timestamp.split(' ')[1]}` : 'No data on date'}
                    </span>
                    <div>{latest ? getAqiBadge(latest.aqi) : <span className="text-xs text-gray-400">Offline</span>}</div>
                  </div>
                </div>
              );
            })}
        </div>
      )}
    </div>
  );
};

export default AirQualityTable;