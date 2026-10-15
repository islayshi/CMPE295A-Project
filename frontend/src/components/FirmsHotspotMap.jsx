import React, { useState, useEffect, useCallback } from 'react';
import { MapContainer, TileLayer, CircleMarker, Popup, LayersControl } from 'react-leaflet';
import DatePicker from 'react-datepicker';
import 'react-datepicker/dist/react-datepicker.css';

const FirmsHotspotMap = ({ selectedDate, setSelectedDate, formatDateString }) => {
  const [firmsData, setFirmsData] = useState([]);
  const [availablePasses, setAvailablePasses] = useState({});
  const [selectedPassTime, setSelectedPassTime] = useState('');
  const [activeFireDates, setActiveFireDates] = useState([]);
  const [isFirmsLoading, setIsFirmsLoading] = useState(false);
  const [firmsError, setFirmsError] = useState(null);

  // Function to fetch active dates for a specific year and month
  const fetchActiveDatesForMonth = useCallback(async (dateObj) => {
    try {
      const year = dateObj.getFullYear();
      const month = dateObj.getMonth() + 1; // 1-indexed month
      const res = await fetch(`http://127.0.0.1:8000/api/telemetry/firms/active-dates/?year=${year}&month=${month}`);
      const data = await res.json();
      if (res.ok && data.status === 'success') {
        const dateObjs = data.dates.map((dStr) => new Date(dStr + 'T00:00:00'));
        setActiveFireDates(dateObjs);
      }
    } catch (err) {
      console.error('Failed to fetch FIRMS active dates:', err);
    }
  }, []);

  // Initial load for selected date's month
  useEffect(() => {
    fetchActiveDatesForMonth(selectedDate);
  }, [selectedDate, fetchActiveDatesForMonth]);

  // Fetch FIRMS hotspots for selected date & pass
  useEffect(() => {
    const fetchFirmsHotspots = async () => {
      setIsFirmsLoading(true);
      setFirmsError(null);

      try {
        const dateStr = formatDateString(selectedDate);
        let url = `http://127.0.0.1:8000/api/telemetry/firms/?date=${dateStr}`;
        if (selectedPassTime) {
          url += `&time=${selectedPassTime}`;
        }

        const res = await fetch(url);
        const data = await res.json();

        if (res.ok && data.status === 'success') {
          setFirmsData(data.hotspots || []);
          setAvailablePasses(data.passes || {});
        } else {
          throw new Error(data.message || 'Failed to fetch FIRMS thermal hotspots.');
        }
      } catch (err) {
        console.error('FIRMS fetch error:', err);
        setFirmsError(err.message);
      } finally {
        setIsFirmsLoading(false);
      }
    };

    fetchFirmsHotspots();
  }, [selectedDate, selectedPassTime, formatDateString]);

  const currentPasses = availablePasses[formatDateString(selectedDate)] || [];

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
      <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
        <div>
          <h2 className="text-xl font-semibold text-gray-800">
            NASA FIRMS — Thermal Hotspots (VIIRS)
          </h2>
          <p className="text-sm text-gray-600">
            Near Real-Time & Historical thermal anomalies over the SF Bay Area.
          </p>
        </div>

        <div className="flex items-center gap-2 relative z-[1001]">
          <label className="text-sm font-medium text-gray-700">Target Date:</label>
          <DatePicker
            selected={selectedDate}
            onChange={(date) => {
              setSelectedDate(date);
              setSelectedPassTime('');
            }}
            onMonthChange={(newMonthDate) => {
              // Re-fetch highlighted active dates when user clicks previous/next month arrows
              fetchActiveDatesForMonth(newMonthDate);
            }}
            maxDate={new Date()}
            dateFormat="yyyy-MM-dd"
            highlightDates={[
              {
                'react-datepicker__day--highlighted-firms': activeFireDates,
              },
            ]}
            className="px-3 py-1.5 border border-gray-300 rounded-lg text-sm bg-white shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 cursor-pointer"
          />
        </div>
      </div>

      {/* Satellite Pass Time Filter Pills */}
      <div className="mb-4 flex items-center gap-2 flex-wrap">
        <span className="text-xs font-semibold uppercase tracking-wider text-gray-500 mr-2">
          Satellite Passes (UTC):
        </span>
        <button
          onClick={() => setSelectedPassTime('')}
          className={`px-3 py-1 text-xs font-medium rounded-full transition-colors ${
            selectedPassTime === ''
              ? 'bg-amber-600 text-white'
              : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
          }`}
        >
          All Passes ({firmsData.length})
        </button>

        {currentPasses.map((passTime) => (
          <button
            key={passTime}
            onClick={() => setSelectedPassTime(passTime)}
            className={`px-3 py-1 text-xs font-medium rounded-full transition-colors ${
              selectedPassTime === passTime
                ? 'bg-amber-600 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            {`${passTime.slice(0, 2)}:${passTime.slice(2)} UTC`}
          </button>
        ))}
      </div>

      {isFirmsLoading && (
        <div className="p-6 text-center text-sm font-semibold text-amber-600 bg-amber-50 rounded-xl border border-amber-100 animate-pulse mb-4">
          Querying NASA FIRMS thermal detections...
        </div>
      )}

      {firmsError && (
        <div className="p-4 text-sm text-red-700 bg-red-50 rounded-xl border border-red-200 mb-4">
          {firmsError}
        </div>
      )}

      {/* Map Canvas */}
      <div className="h-[550px] w-full rounded-lg overflow-hidden border border-gray-200 relative">
        {!isFirmsLoading && !firmsError && firmsData.length === 0 && (
          <div className="absolute top-4 left-1/2 transform -translate-x-1/2 z-[1000] bg-white/95 backdrop-blur-sm border border-gray-200 px-4 py-2 rounded-lg shadow-md text-center">
            <p className="text-xs font-semibold text-gray-700">No Thermal Hotspots Detected</p>
            <p className="text-[11px] text-gray-500">
              VIIRS satellite passed over SF Bay Area on {formatDateString(selectedDate)} with 0 active thermal anomalies.
            </p>
          </div>
        )}

        <MapContainer center={[37.6, -122.1]} zoom={9} style={{ height: '100%', width: '100%' }}>
          <LayersControl position="topright">
            <LayersControl.BaseLayer checked name="OpenStreetMap Standard">
              <TileLayer
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
              />
            </LayersControl.BaseLayer>
            <LayersControl.BaseLayer name="Esri World Imagery">
              <TileLayer
                url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
                attribution="Tiles &copy; Esri"
              />
            </LayersControl.BaseLayer>
          </LayersControl>

          {firmsData.map((spot, idx) => (
            <CircleMarker
              key={`${spot.lat}-${spot.lon}-${idx}`}
              center={[spot.lat, spot.lon]}
              radius={Math.max(5, Math.min(spot.frp * 0.4, 16))}
              pathOptions={{
                color: '#dc2626',
                fillColor: '#ef4444',
                fillOpacity: 0.8,
                weight: 2,
              }}
            >
              <Popup>
                <div className="text-xs space-y-1">
                  <p className="font-bold text-red-600">VIIRS Thermal Hotspot</p>
                  <p><strong>FRP:</strong> {spot.frp} MW</p>
                  <p><strong>Brightness:</strong> {spot.bright_ti4} K</p>
                  <p><strong>Time:</strong> {spot.acq_date} {spot.acq_time} UTC</p>
                  <p><strong>Confidence:</strong> {spot.confidence}</p>
                </div>
              </Popup>
            </CircleMarker>
          ))}
        </MapContainer>
      </div>
    </div>
  );
};

export default FirmsHotspotMap;