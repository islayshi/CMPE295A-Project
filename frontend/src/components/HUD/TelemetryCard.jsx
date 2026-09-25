import { AlertTriangle, Wind, Activity, Route } from 'lucide-react';

export default function TelemetryCard({ predictions, windData, alerts, routeData }) {
  // Determine if there is a red flag warning
  const redFlagActive = alerts && alerts.features && alerts.features.length > 0;
  
  // Compute wind speed and direction from the first vector (assuming uniform grid for now)
  let windText = "Loading...";
  let windRotation = "rotate-0";
  if (windData && windData.length > 0) {
    const { u, v } = windData[0];
    const speed = Math.sqrt(u * u + v * v);
    
    // Simple compass direction logic (rudimentary)
    let dir = "";
    if (u < -10 && v < -10) dir = "SW";
    else if (u < 0 && v === 0) dir = "W";
    else if (u > 0 && v === 0) dir = "E";
    else dir = "VAR"; // variable
    
    windText = `${Math.round(speed)} mph ${dir}`;
    
    // Calculate rotation angle for the arrow icon based on u,v
    // Using simple mapping for now
    if (dir === "SW") windRotation = "rotate-[135deg]";
    else if (dir === "W") windRotation = "rotate-180";
  }

  // Calculate vulnerability based on max fire probability in predictions
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
          <span className="font-semibold">Bay Area, CA</span>
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
            <svg className={`w-3 h-3 ${windRotation} transition-transform duration-500`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M14 5l7 7m0 0l-7 7m7-7H3" />
            </svg>
          </div>
        </div>
        
        <div className="flex justify-between mt-2 pt-2 border-t border-slate-700/50">
          <span className="text-slate-300">Vulnerability Score:</span>
          <span className={`font-bold ${vulnerability === 'High' ? 'text-red-500' : (vulnerability === 'Medium' ? 'text-orange-500' : 'text-green-500')}`}>{vulnerability}</span>
        </div>

        {routeData && routeData.properties && (
          <div className="mt-2 pt-2 border-t border-slate-700/50">
            <h4 className="text-xs text-blue-400 font-bold mb-1 flex items-center gap-1"><Route size={12}/> EVACUATION PLAN</h4>
            <div className="flex justify-between items-center text-xs">
              <span className="text-slate-400">Destination:</span>
              <span className="text-right truncate ml-2 max-w-[140px]" title={routeData.properties.destination_shelter}>{routeData.properties.destination_shelter}</span>
            </div>
            <div className="flex justify-between items-center text-xs mt-1">
              <span className="text-slate-400">ETA / Distance:</span>
              <span>{routeData.properties.estimated_duration_minutes} min / {routeData.properties.distance_km} km</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
