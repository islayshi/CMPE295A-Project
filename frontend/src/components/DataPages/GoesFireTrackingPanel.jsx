import React, { useState, useEffect } from 'react';
import DatePicker from 'react-datepicker';
import 'react-datepicker/dist/react-datepicker.css';

const GoesFireTrackingPanel = ({ selectedDate, formatDateString }) => {
  const [activeDate, setActiveDate] = useState(selectedDate || new Date());
  const [availableDates, setAvailableDates] = useState([]);
  const [channel, setChannel] = useState('07'); // '07' = Shortwave IR, 'GEOCOLOR' = Smoke
  const [frames, setFrames] = useState([]);
  const [currentIdx, setCurrentIdx] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchFrames = async () => {
      setIsLoading(true);
      setError(null);

      try {
        const dateStr = formatDateString(activeDate);
        const res = await fetch(`http://127.0.0.1:8000/api/telemetry/goes/?date=${dateStr}&channel=${channel}`);
        const data = await res.json();

        if (res.ok && data.status === 'success') {
          setFrames(data.frames || []);
          if (data.availableDates) {
            const dateObjs = data.availableDates.map(d => new Date(d + 'T00:00:00'));
            setAvailableDates(dateObjs);
          }
          setCurrentIdx(0);
        } else {
          throw new Error(data.message || 'Failed to load GOES-18 frames.');
        }
      } catch (err) {
        console.error('GOES fetch error:', err);
        setError(err.message);
      } finally {
        setIsLoading(false);
      }
    };

    fetchFrames();
  }, [activeDate, channel, formatDateString]);

  const handlePrev = () => {
    if (frames.length === 0) return;
    setCurrentIdx((prev) => (prev === 0 ? frames.length - 1 : prev - 1));
  };

  const handleNext = () => {
    if (frames.length === 0) return;
    setCurrentIdx((prev) => (prev === frames.length - 1 ? 0 : prev + 1));
  };

  const activeFrame = frames[currentIdx] || null;

  return (
    <div className="space-y-6">
      {/* Header & Controls Bar */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold text-gray-800">
              GOES-18 Satellite Image Gallery
            </h2>
            <p className="text-sm text-gray-600">
              Pacific Southwest (California & SF Bay Area) real-time geostationary imagery.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            {/* Target Date Picker */}
            <div className="flex items-center gap-2 relative z-10">
              <label className="text-xs font-semibold text-gray-600 uppercase">Target Date:</label>
              <DatePicker
                selected={activeDate}
                onChange={(date) => setActiveDate(date)}
                includeDates={availableDates.length > 0 ? availableDates : undefined}
                dateFormat="yyyy-MM-dd"
                className="px-3 py-1.5 border border-gray-300 rounded-lg text-xs font-medium bg-white shadow-sm focus:outline-none focus:ring-2 focus:ring-orange-500 cursor-pointer"
              />
            </div>

            {/* Band Toggle */}
            <div className="flex bg-gray-100 p-1 rounded-lg border border-gray-200">
              <button
                onClick={() => setChannel('07')}
                className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-all ${
                  channel === '07'
                    ? 'bg-orange-600 text-white shadow-sm'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                🔥 Shortwave IR
              </button>
              <button
                onClick={() => setChannel('GEOCOLOR')}
                className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-all ${
                  channel === 'GEOCOLOR'
                    ? 'bg-blue-600 text-white shadow-sm'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                💨 GeoColor
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Main Stage */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
        {isLoading ? (
          <div className="h-[480px] flex items-center justify-center bg-gray-50 rounded-xl border border-gray-100">
            <span className="text-sm font-semibold text-orange-600 animate-pulse">
              Fetching GOES-18 satellite frames...
            </span>
          </div>
        ) : error ? (
          <div className="p-6 bg-red-50 text-red-700 rounded-xl border border-red-200 text-sm">
            {error}
          </div>
        ) : frames.length === 0 ? (
          /* Blank / Empty State when no archive frames exist for date */
          <div className="h-[480px] flex flex-col items-center justify-center bg-gray-50 rounded-xl border border-dashed border-gray-300 p-8 text-center">
            <div className="text-3xl mb-2">📡</div>
            <h3 className="text-base font-semibold text-gray-800">No Image Frames Available</h3>
            <p className="text-xs text-gray-500 max-w-md mt-1">
              NOAA NESDIS STAR only maintains real-time sector frames for recent 24–48 hour windows. Try selecting today's date or switching bands.
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {/* Gallery Viewer Canvas */}
            <div className="relative h-[520px] w-full bg-black rounded-lg overflow-hidden border border-gray-800 flex items-center justify-center">
              {activeFrame ? (
                <img
                  src={activeFrame.url}
                  alt={`GOES-18 scan at ${activeFrame.time}`}
                  className="max-h-full max-w-full object-contain"
                />
              ) : (
                <span className="text-gray-500 text-sm">No frame loaded</span>
              )}

              {/* Timestamp Overlay */}
              <div className="absolute top-4 left-4 bg-black/80 backdrop-blur-md px-3 py-1.5 rounded-md border border-white/20 text-white text-xs font-mono">
                Scan Time: <span className="text-orange-400 font-bold">{activeFrame?.time}</span> | {channel === '07' ? 'Shortwave IR' : 'GeoColor'}
              </div>

              {/* Frame Counter Overlay */}
              <div className="absolute top-4 right-4 bg-black/80 backdrop-blur-md px-3 py-1.5 rounded-md border border-white/20 text-white text-xs font-mono">
                Image {currentIdx + 1} of {frames.length}
              </div>

              {/* Prev/Next Arrow Overlays */}
              <button
                onClick={handlePrev}
                disabled={frames.length <= 1}
                className="absolute left-4 top-1/2 -translate-y-1/2 bg-black/60 hover:bg-orange-600 text-white p-3 rounded-full border border-white/20 transition-all shadow-lg active:scale-95 disabled:opacity-30"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M15 19l-7-7 7-7" />
                </svg>
              </button>

              <button
                onClick={handleNext}
                disabled={frames.length <= 1}
                className="absolute right-4 top-1/2 -translate-y-1/2 bg-black/60 hover:bg-orange-600 text-white p-3 rounded-full border border-white/20 transition-all shadow-lg active:scale-95 disabled:opacity-30"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M9 5l7 7-7 7" />
                </svg>
              </button>
            </div>

            {/* Quick-Jump Slots */}
            <div className="grid grid-cols-4 sm:grid-cols-6 md:grid-cols-12 gap-1.5 pt-2">
              {frames.map((frame, idx) => (
                <button
                  key={idx}
                  onClick={() => setCurrentIdx(idx)}
                  className={`py-2 px-1 rounded border text-center transition-all ${
                    currentIdx === idx
                      ? 'bg-orange-600 text-white border-orange-700 font-bold shadow-sm'
                      : 'bg-white text-gray-700 border-gray-200 hover:bg-orange-50 hover:border-orange-200'
                  }`}
                >
                  <div className="text-[10px] font-mono leading-none">{frame.time.replace(' UTC', '')}</div>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default GoesFireTrackingPanel;