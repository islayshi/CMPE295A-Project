import { AlertTriangle, Wind, Activity } from 'lucide-react';
import { getMapData } from '../../mockData/geojsonStates';

export default function TelemetryCard({ scenarioState }) {
  const { envState } = getMapData(scenarioState, 0);
  const { aqi, aqiStatus, windText, redFlagActive, vulnerability } = envState;
  
  const aqiColor = aqi < 50 ? 'bg-green-500' : (aqi > 100 ? 'bg-red-500' : 'bg-orange-500');
  // rotate-180 points West (Left), rotate-[135deg] points South-West (Down-Left)
  const windRotation = redFlagActive ? 'rotate-[135deg]' : 'rotate-180';

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
          <span className="font-semibold">Hayward, CA</span>
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
          <span className={`font-bold ${vulnerability === 'High' ? 'text-red-500' : 'text-green-500'}`}>{vulnerability}</span>
        </div>
      </div>
    </div>
  );
}