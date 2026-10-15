import React, { useState, useEffect } from 'react';

const WeatherTelemetryPanel = ({ selectedDate, formatDateString }) => {
  const [weatherData, setWeatherData] = useState(null);
  const [selectedStationId, setSelectedStationId] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchWeather = async () => {
      setIsLoading(true);
      setError(null);

      try {
        const dateStr = formatDateString(selectedDate);
        const res = await fetch(`http://127.0.0.1:8000/api/telemetry/weather/?date=${dateStr}`);
        const data = await res.json();

        if (res.ok && data.status === 'success') {
          setWeatherData(data);
          if (data.stations && data.stations.length > 0) {
            setSelectedStationId(data.stations[0].stationId);
          }
        } else {
          throw new Error(data.message || 'Failed to fetch weather telemetry.');
        }
      } catch (err) {
        console.error('Weather fetch error:', err);
        setError(err.message);
      } finally {
        setIsLoading(false);
      }
    };

    fetchWeather();
  }, [selectedDate, formatDateString]);

  if (isLoading) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-8 text-center">
        <div className="text-amber-600 font-semibold text-sm animate-pulse">
          Fetching Bay Area weather telemetry & Red Flag risk conditions...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 rounded-xl border border-red-200 p-6 text-red-700 text-sm">
        {error}
      </div>
    );
  }

  const summary = weatherData?.summary || {};
  const activeStation = weatherData?.stations?.find((s) => s.stationId === selectedStationId) || weatherData?.stations?.[0];

  return (
    <div className="space-y-6">
      
      {/* 1. Header & Red Flag Threat Banner */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
        <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
          <div>
            <h2 className="text-xl font-semibold text-gray-800">
              Surface Meteorology & Fire Weather
            </h2>
            <p className="text-sm text-gray-600">
              Hourly surface wind vectors, relative humidity, and Red Flag threat indicators for {formatDateString(selectedDate)}.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <span
              className={`px-3 py-1.5 rounded-full text-xs font-bold uppercase tracking-wider ${
                summary.isRedFlagCondition
                  ? 'bg-red-100 text-red-700 border border-red-300 animate-pulse'
                  : 'bg-emerald-100 text-emerald-800 border border-emerald-300'
              }`}
            >
              {summary.isRedFlagCondition ? '⚠️ Red Flag Warning Active' : '🟢 Moderate / Low Fire Weather Risk'}
            </span>
          </div>
        </div>

        {/* Key Summary Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-6">
          <div className="bg-gray-50 rounded-lg p-4 border border-gray-100">
            <p className="text-xs font-semibold text-gray-500 uppercase">Min Relative Humidity</p>
            <p className={`text-2xl font-bold mt-1 ${summary.minRelativeHumidity <= 15 ? 'text-red-600' : 'text-gray-800'}`}>
              {summary.minRelativeHumidity}%
            </p>
            <p className="text-[11px] text-gray-500 mt-0.5">Critical threshold: ≤ 15%</p>
          </div>

          <div className="bg-gray-50 rounded-lg p-4 border border-gray-100">
            <p className="text-xs font-semibold text-gray-500 uppercase">Peak Wind Gust</p>
            <p className={`text-2xl font-bold mt-1 ${summary.maxWindGustMph >= 25 ? 'text-red-600' : 'text-gray-800'}`}>
              {summary.maxWindGustMph} <span className="text-sm font-normal">mph</span>
            </p>
            <p className="text-[11px] text-gray-500 mt-0.5">Critical threshold: ≥ 25 mph</p>
          </div>

          <div className="bg-gray-50 rounded-lg p-4 border border-gray-100">
            <p className="text-xs font-semibold text-gray-500 uppercase">Max Temperature</p>
            <p className="text-2xl font-bold text-gray-800 mt-1">
              {summary.maxTemperatureF}°F
            </p>
            <p className="text-[11px] text-gray-500 mt-0.5">Peak daily heat</p>
          </div>

          <div className="bg-gray-50 rounded-lg p-4 border border-gray-100">
            <p className="text-xs font-semibold text-gray-500 uppercase">Avg Wind Vector</p>
            <p className="text-2xl font-bold text-gray-800 mt-1">
              {summary.avgWindDirectionDeg}°
            </p>
            <p className="text-[11px] text-gray-500 mt-0.5">Primary wind heading</p>
          </div>
        </div>
      </div>

      {/* 2. Station Selector & Hourly Telemetry Table */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
        <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
          <h3 className="text-lg font-semibold text-gray-800">
            Station Telemetry — {activeStation?.stationName}
          </h3>

          <div className="flex items-center gap-2">
            <label className="text-xs font-semibold text-gray-600 uppercase">Station:</label>
            <select
              value={selectedStationId || ''}
              onChange={(e) => setSelectedStationId(e.target.value)}
              className="px-3 py-1.5 border border-gray-300 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-amber-500"
            >
              {weatherData?.stations?.map((st) => (
                <option key={st.stationId} value={st.stationId}>
                  {st.stationName} ({st.subRegion})
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Hourly Readings Grid */}
        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-gray-200 bg-gray-50 text-gray-600 uppercase tracking-wider">
                <th className="py-2.5 px-3">Time (UTC)</th>
                <th className="py-2.5 px-3">Temp (°F)</th>
                <th className="py-2.5 px-3">Humidity (%)</th>
                <th className="py-2.5 px-3">Wind Speed (mph)</th>
                <th className="py-2.5 px-3">Wind Gust (mph)</th>
                <th className="py-2.5 px-3">Wind Dir (°)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 text-gray-700">
              {activeStation?.hourly?.map((row, idx) => (
                <tr key={idx} className="hover:bg-gray-50 transition-colors">
                  <td className="py-2 px-3 font-medium text-gray-900">{row.time.split(' ')[1]}</td>
                  <td className="py-2 px-3">{row.temperature}°F</td>
                  <td className={`py-2 px-3 font-semibold ${row.relativeHumidity <= 15 ? 'text-red-600' : 'text-gray-800'}`}>
                    {row.relativeHumidity}%
                  </td>
                  <td className="py-2 px-3">{row.windSpeed} mph</td>
                  <td className={`py-2 px-3 font-semibold ${row.windGust >= 25 ? 'text-red-600' : 'text-gray-800'}`}>
                    {row.windGust} mph
                  </td>
                  <td className="py-2 px-3">{row.windDirection}°</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

    </div>
  );
};

export default WeatherTelemetryPanel;