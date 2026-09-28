import { AlertTriangle, Wind, Activity } from 'lucide-react';


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

// Convert U/V components to compass direction (e.g. N, NE, S)
function getCompassDirection(u, v) {
  if (u === 0 && v === 0) return "CALM";
  // Wind direction is WHERE it blows FROM (meteorological standard), but let's just use angle
  const angle = (Math.atan2(v, u) * 180 / Math.PI + 360) % 360;
  const directions = ['E', 'ENE', 'NE', 'NNE', 'N', 'NNW', 'NW', 'WNW', 'W', 'WSW', 'SW', 'SSW', 'S', 'SSE', 'SE', 'ESE'];
  const index = Math.round(angle / 22.5) % 16;
  return directions[index];
}

export default function TelemetryCard({ predictions, windData, alerts, userLocation, cityName }) {
  // Determine if there is a red flag warning
  const redFlagActive = alerts && alerts.features && alerts.features.length > 0;
  
  // Compute wind speed and direction from the first vector (assuming uniform grid for now)
  let windText = "Loading...";
  let windAngle = 0;
  
  if (windData && windData.length >= 2 && userLocation) {
    const h = windData[0].header;
    const [u, v] = getVector(userLocation.lon, userLocation.lat, h, windData[0].data, windData[1].data);
    
    // Wind is returned directly in MPH by our backend IDW interpolator
    const speed = Math.sqrt(u * u + v * v);
    const dir = getCompassDirection(u, v);
    
    if (speed === 0) {
      windText = "Calm";
    } else {
      windText = `${Math.round(speed)} mph ${dir}`;
      // Calculate rotation for the icon (0 deg is pointing UP)
      // Math.atan2(y, x) where x=u, y=v. 
      const angleDeg = Math.atan2(v, u) * 180 / Math.PI;
      windAngle = Math.round(90 - angleDeg);
    }
  }

  let maxProbability = 0;
  if (predictions && predictions.features) {
    predictions.features.forEach(f => {
      if (f.properties.fire_probability > maxProbability) {
        maxProbability = f.properties.fire_probability;
      }
    });
  }
  const vulnerability = maxProbability > 0.7 ? "High" : (maxProbability > 0.4 ? "Medium" : "Low");
  
  // AQI mock logic based on fire risk
  const aqi = maxProbability > 0.7 ? 150 : (maxProbability > 0.4 ? 90 : 45);
  const aqiStatus = maxProbability > 0.7 ? 'Unhealthy' : (maxProbability > 0.4 ? 'Moderate' : 'Good');
  const aqiColor = aqi < 50 ? 'bg-green-500' : (aqi > 100 ? 'bg-red-500' : 'bg-orange-500');

  return (
    <div className={`pointer-events-auto w-72 bg-slate-900/60 backdrop-blur-md border ${redFlagActive ? 'border-red-500 animate-pulse' : 'border-slate-700'} text-white rounded-xl shadow-lg p-4 transition-all duration-300`}>
      {redFlagActive && (
        <div className="mb-3 bg-red-600/90 text-white text-xs font-bold px-2 py-1.5 rounded flex items-center gap-2 animate-pulse">
          <AlertTriangle size={16} className="shrink-0" />
          <span>⚠️ NWS RED FLAG WARNING IN EFFECT</span>
        </div>
      )}
      
      <h3 className="text-lg font-bold mb-3 flex items-center gap-2">
        <Activity size={18}/> Live Telemetry
      </h3>
      
      <div className="space-y-2 text-sm">
        <div className="flex justify-between items-center">
          <span className="text-slate-300">Location:</span>
          <span className="font-semibold">{cityName || "Bay Area, CA"}</span>
        </div>
        
        <div className="flex justify-between items-center">
          <span className="text-slate-300">AQI (PM2.5):</span>
          <span className={`font-semibold px-2 py-0.5 rounded text-xs ${aqiColor} text-white`}>
            {aqi} ({aqiStatus})
          </span>
        </div>
        
        <div className="flex justify-between items-center gap-2">
          <span className="text-slate-300 flex items-center gap-1"><Wind size={14}/> Wind:</span>
          <div className={`font-semibold flex items-center gap-1 ${redFlagActive ? 'text-red-400' : 'text-blue-400'}`}>
            <span>{windText}</span>
            <svg className="w-3 h-3 transition-transform duration-500" style={{ transform: `rotate(${windAngle}deg)` }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M14 5l7 7m0 0l-7 7m7-7H3" />
            </svg>
          </div>
        </div>
        
        <div className="flex justify-between mt-2 pt-2 border-t border-slate-700/50">
          <span className="text-slate-300">Vulnerability Score:</span>
          <span className={`font-bold ${vulnerability === 'High' ? 'text-red-500' : (vulnerability === 'Medium' ? 'text-orange-500' : 'text-green-500')}`}>{vulnerability}</span>
        </div>
      </div>
    </div>
  );
}
