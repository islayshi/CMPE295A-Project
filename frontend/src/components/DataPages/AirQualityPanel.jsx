// src/components/DataPages/AirQualityPanel.jsx
import React, { useState, useEffect } from 'react';
import AirQualityTable from '../AirQualityTable';
import { BAY_AREA_STATIONS } from '../../config/datasets';

export default function AirQualityPanel({ selectedDate, setSelectedDate, formatDateString }) {
  const [telemetryData, setTelemetryData] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchBayAreaAQI = async () => {
      setIsLoading(true);
      setError(null);

      try {
        const dateStr = formatDateString(selectedDate);
        const requests = BAY_AREA_STATIONS.map(async (station) => {
          const url = `https://air-quality-api.open-meteo.com/v1/air-quality?latitude=${station.lat}&longitude=${station.lon}&hourly=pm10,pm2_5,us_aqi&start_date=${dateStr}&end_date=${dateStr}`;
          
          const res = await fetch(url);
          if (!res.ok) throw new Error(`HTTP ${res.status} on station ${station.id}`);
          const json = await res.json();

          const hourly = json.hourly || {};
          const timestamps = hourly.time || [];
          const pm25List = hourly.pm2_5 || [];
          const pm10List = hourly.pm10 || [];
          const aqiList = hourly.us_aqi || [];

          return timestamps.map((time, idx) => ({
            id: `${station.id}-${idx}`,
            timestamp: time.replace('T', ' '),
            stationId: station.id,
            stationName: station.name,
            subRegion: station.subRegion,
            pm25: pm25List[idx] ?? 0,
            pm10: pm10List[idx] ?? 0,
            aqi: aqiList[idx] ?? 0,
            lat: station.lat,
            lon: station.lon,
          }));
        });

        const results = await Promise.all(requests);
        setTelemetryData(results.flat());
      } catch (err) {
        console.error('Failed to fetch Open-Meteo data:', err);
        setError('Failed to fetch live station data. Check your network connection.');
      } finally {
        setIsLoading(false);
      }
    };

    fetchBayAreaAQI();
  }, [selectedDate, formatDateString]);

  return (
    <div>
      {isLoading && (
        <div className="p-8 text-center text-sm font-semibold text-blue-600 bg-white rounded-xl border border-gray-200 shadow-sm animate-pulse mb-6">
          Fetching live sensor telemetry from Open-Meteo API...
        </div>
      )}

      {error && (
        <div className="p-4 text-sm text-red-700 bg-red-50 rounded-xl border border-red-200 mb-6">
          {error}
        </div>
      )}

      {!isLoading && (
        <AirQualityTable
          telemetryData={telemetryData}
          bayAreaStations={BAY_AREA_STATIONS}
          selectedDate={formatDateString(selectedDate)}
          onDateChange={(dateStr) => setSelectedDate(new Date(dateStr + 'T00:00:00'))}
        />
      )}
    </div>
  );
}