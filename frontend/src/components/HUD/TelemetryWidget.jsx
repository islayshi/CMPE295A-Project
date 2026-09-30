import { useState } from 'react';
import { Wind, Activity, ChevronRight } from 'lucide-react';
import WeatherForecast from '../WeatherForecast';
// eslint-disable-next-line no-unused-vars
import { motion, AnimatePresence } from 'framer-motion';
import { getLocalizedAQI } from '../../utils/aqiMath';

// Helper to bilinearly interpolate vector field at specific lat/lon
function getVector(x, y, header, uData, vData) {
  const { nx, ny, lo1, la1, dx, dy } = header;
  const i = (x - lo1) / dx;
  const j = (y - la1) / dy;
  if (i < 0 || i >= nx - 1 || j < 0 || j >= ny - 1) return [0, 0];
  const i0 = Math.floor(i), i1 = i0 + 1, j0 = Math.floor(j), j1 = j0 + 1;
  const u = i - i0, v = j - j0;
  const idx00 = j0 * nx + i0, idx10 = j0 * nx + i1, idx01 = j1 * nx + i0, idx11 = j1 * nx + i1;
  const u_interp = uData[idx00] * (1 - u) * (1 - v) + uData[idx10] * u * (1 - v) + uData[idx01] * (1 - u) * v + uData[idx11] * u * v;
  const v_interp = vData[idx00] * (1 - u) * (1 - v) + vData[idx10] * u * (1 - v) + vData[idx01] * (1 - u) * v + vData[idx11] * u * v;
  return [u_interp, v_interp];
}

// Convert U/V components to compass direction
function getCompassDirection(u, v) {
  if (u === 0 && v === 0) return "CALM";
  const angle = (Math.atan2(v, u) * 180 / Math.PI + 360) % 360;
  const directions = ['E', 'ENE', 'NE', 'NNE', 'N', 'NNW', 'NW', 'WNW', 'W', 'WSW', 'SW', 'SSW', 'S', 'SSE', 'SE', 'ESE'];
  const index = Math.round(angle / 22.5) % 16;
  return directions[index];
}

/** Derive a Tailwind bg-color class from an AQI integer. */
function aqiColorClass(aqi) {
  if (aqi === null || aqi === undefined) return 'bg-slate-400';
  if (aqi <= 50)  return 'bg-green-500';
  if (aqi <= 100) return 'bg-yellow-500';
  if (aqi <= 150) return 'bg-orange-500';
  if (aqi <= 200) return 'bg-red-500';
  if (aqi <= 300) return 'bg-purple-500';
  return 'bg-purple-700';
}

export default function TelemetryWidget({ windData, userLocation, cityName, aqiData }) {
  const [isOpen, setIsOpen] = useState(false);
  
  let windText = "Loading...";
  let windAngle = 0;
  
  if (windData && windData.length >= 2 && userLocation) {
    const h = windData[0].header;
    const [u, v] = getVector(userLocation.lon, userLocation.lat, h, windData[0].data, windData[1].data);
    
    const speed = Math.sqrt(u * u + v * v);
    const dir = getCompassDirection(u, v);
    
    if (speed === 0) {
      windText = "Calm";
    } else {
      windText = `${Math.round(speed)} mph ${dir}`;
      const angleDeg = Math.atan2(v, u) * 180 / Math.PI;
      windAngle = Math.round(-angleDeg);
    }
  }

  // Calculate localized AQI using Inverse Distance Weighting if we have sensors
  let localAqi = null;
  if (userLocation && aqiData?.sensors) {
    localAqi = getLocalizedAQI(userLocation.lat, userLocation.lon, aqiData.sensors);
  }

  // Fallback to global average if local calculation fails
  const aqi = localAqi !== null ? localAqi : (aqiData?.aqi ?? null);
  
  // Determine status based on dynamic AQI, or fallback to global status
  let aqiStatus = aqiData?.status ?? null;
  if (localAqi !== null) {
    if (aqi <= 50) aqiStatus = 'Good';
    else if (aqi <= 100) aqiStatus = 'Moderate';
    else if (aqi <= 150) aqiStatus = 'Sensitive Groups';
    else if (aqi <= 200) aqiStatus = 'Unhealthy';
    else if (aqi <= 300) aqiStatus = 'Very Unhealthy';
    else aqiStatus = 'Hazardous';
  }
  const aqiColor = aqiColorClass(aqi);
  const aqiDisplay = aqi !== null ? String(aqi) : "Loading...";
  const aqiStatusDisplay = aqiStatus && aqiStatus !== "Unavailable" ? aqiStatus : (aqiStatus === "Unavailable" ? "Unavailable" : "Loading...");

  return (
    <>
      <div className="absolute top-20 right-6 z-40">
        <button
          onClick={() => setIsOpen(true)}
          className={`flex items-center gap-3 bg-orange-600 backdrop-blur-md border border-orange-500 text-white px-4 py-2 rounded-full shadow-lg hover:bg-orange-700 transition-all duration-300 ${isOpen ? 'opacity-0 pointer-events-none' : 'opacity-100 pointer-events-auto'}`}
        >
          <span className="font-semibold text-sm">{cityName || "Bay Area"}</span>
          <div className="w-1 h-1 rounded-full bg-orange-300"></div>
          <span className="text-sm flex items-center gap-1">
            AQI <span className={`w-2 h-2 rounded-full ${aqiColor}`}></span> {aqiDisplay}
          </span>
          <div className="w-1 h-1 rounded-full bg-orange-300"></div>
          <span className="text-sm flex items-center gap-1">
            <Wind size={14} /> {windText}
          </span>
        </button>
      </div>

      <AnimatePresence>
        {isOpen && (
          <motion.div 
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', damping: 25, stiffness: 200 }}
            className="absolute top-16 right-0 w-full max-w-[400px] h-[calc(100vh-64px)] bg-slate-50 backdrop-blur-xl border-l border-slate-200 shadow-2xl flex flex-col z-50 pointer-events-auto overflow-y-auto"
          >
            <div className="p-5 border-b border-slate-200 flex justify-between items-center sticky top-0 bg-slate-50/95 backdrop-blur-xl z-10">
              <h2 className="font-bold text-lg flex items-center gap-2 text-slate-800"><Activity size={20}/> Telemetry &amp; Forecast</h2>
              <button onClick={() => setIsOpen(false)} className="text-slate-800 hover:text-orange-600 transition-colors p-1 bg-slate-200 hover:bg-orange-100 rounded-md">
                <ChevronRight size={20} />
              </button>
            </div>

            <div className="p-5 space-y-6 text-slate-800">
              <div className="bg-white p-4 rounded-xl border border-slate-200 space-y-3">
                <h3 className="text-sm font-bold text-slate-800 uppercase tracking-wider">Live Conditions</h3>
                <div className="flex justify-between items-center text-sm">
                  <span className="text-slate-800">Location:</span>
                  <span className="font-semibold">{cityName || "Bay Area, CA"}</span>
                </div>
                <div className="flex justify-between items-center text-sm">
                  <span className="text-slate-800">AQI (PM2.5):</span>
                  <span className={`font-semibold px-2 py-0.5 rounded text-xs ${aqiColor} text-white`}>
                    {aqi !== null ? `${aqi} (${aqiStatusDisplay})` : aqiStatusDisplay}
                  </span>
                </div>
                <div className="flex justify-between items-center text-sm">
                  <span className="text-slate-800 flex items-center gap-1"><Wind size={14}/> Wind:</span>
                  <div className="font-semibold flex items-center gap-1 text-orange-600">
                    <span>{windText}</span>
                    <svg className="w-3 h-3" style={{ transform: `rotate(${windAngle}deg)` }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M14 5l7 7m0 0l-7 7m7-7H3" />
                    </svg>
                  </div>
                </div>

              </div>

              <div className="bg-white p-4 rounded-xl border border-slate-200">
                 <h3 className="text-sm font-bold text-slate-800 uppercase tracking-wider mb-4">Detailed Forecast</h3>
                 <div>
                   <WeatherForecast userLocation={userLocation} />
                 </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
