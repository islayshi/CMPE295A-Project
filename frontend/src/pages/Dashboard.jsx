import { useState } from 'react';
import Navbar from '../components/Navbar';
import MapCanvas from '../components/Map/MapCanvas';
import TelemetryCard from '../components/HUD/TelemetryCard';
import Legend from '../components/HUD/Legend';
import TimeScrubber from '../components/HUD/TimeScrubber';
import ChatDrawer from '../components/HUD/ChatDrawer';
import ScenarioController from '../components/DevTools/ScenarioController';
import WeatherForecast from '../components/WeatherForecast';

export default function Dashboard() {
  const [scenarioState, setScenarioState] = useState('NORMAL');
  const [timeScrub, setTimeScrub] = useState(0);
  const [isWeatherOpen, setIsWeatherOpen] = useState(false);

  return (
    <div className="relative w-screen h-screen overflow-hidden bg-black text-white font-sans">
      <Navbar />
      
      <MapCanvas scenarioState={scenarioState} timeScrub={timeScrub} />
      
      {/* HUD Overlays - Added pt-24 so HUD sits below the Navbar */}
      <div className="absolute inset-0 pointer-events-none p-6 pt-24 flex flex-col justify-between">
        <div className="flex justify-between items-start">
          <Legend />
          <div className="flex flex-col items-end gap-4 pointer-events-auto">
            <TelemetryCard scenarioState={scenarioState} />
            <button 
              onClick={() => setIsWeatherOpen(true)}
              className="bg-slate-900/60 backdrop-blur-md border border-slate-700 text-white px-4 py-2 rounded-xl shadow-lg hover:bg-slate-800/80 transition-colors flex items-center gap-2 text-sm font-bold"
            >
              <svg className="w-4 h-4 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 15a4 4 0 004 4h9a5 5 0 10-.1-9.999 5.002 5.002 0 10-9.78 2.096A4.001 4.001 0 003 15z" /></svg>
              Detailed Forecast
            </button>
          </div>
        </div>
        
        <div className="flex justify-center items-end pb-8 pointer-events-auto">
          <TimeScrubber timeScrub={timeScrub} setTimeScrub={setTimeScrub} />
        </div>
      </div>

      <ChatDrawer scenarioState={scenarioState} />
      <ScenarioController scenarioState={scenarioState} setScenarioState={setScenarioState} />

      {/* Weather Modal Overlay */}
      {isWeatherOpen && (
        <div className="absolute inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-6">
          <div className="relative bg-white rounded-2xl shadow-2xl max-w-4xl w-full max-h-[90vh] overflow-y-auto text-black">
            <button 
              onClick={() => setIsWeatherOpen(false)}
              className="absolute top-4 right-4 p-2 text-gray-400 hover:text-gray-800 bg-gray-100 hover:bg-gray-200 rounded-full transition-colors z-10"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
            <WeatherForecast />
          </div>
        </div>
      )}
    </div>
  );
}
