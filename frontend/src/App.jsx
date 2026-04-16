import { useState } from 'react';
import MapCanvas from './components/Map/MapCanvas';
import TelemetryCard from './components/HUD/TelemetryCard';
import Legend from './components/HUD/Legend';
import TimeScrubber from './components/HUD/TimeScrubber';
import ChatDrawer from './components/HUD/ChatDrawer';
import ScenarioController from './components/DevTools/ScenarioController';

export default function App() {
  const [scenarioState, setScenarioState] = useState('NORMAL');
  const [timeScrub, setTimeScrub] = useState(0);

  return (
    <div className="relative w-screen h-screen overflow-hidden bg-black text-white font-sans">
      <MapCanvas scenarioState={scenarioState} timeScrub={timeScrub} />
      
      {/* HUD Overlays */}
      <div className="absolute inset-0 pointer-events-none p-6 flex flex-col justify-between">
        <div className="flex justify-between items-start">
          <Legend />
          <TelemetryCard scenarioState={scenarioState} />
        </div>
        
        <div className="flex justify-center items-end pb-8">
          <TimeScrubber timeScrub={timeScrub} setTimeScrub={setTimeScrub} />
        </div>
      </div>

      <ChatDrawer scenarioState={scenarioState} />
      <ScenarioController scenarioState={scenarioState} setScenarioState={setScenarioState} />
    </div>
  );
}