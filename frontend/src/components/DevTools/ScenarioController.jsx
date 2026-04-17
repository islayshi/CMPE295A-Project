export default function ScenarioController({ scenarioState, setScenarioState }) {
  const states = ['NORMAL', 'AI_UPDATE', 'REROUTE'];
  
  return (
    <div className="absolute top-24 left-1/2 -translate-x-1/2 bg-black/80 backdrop-blur-md border border-slate-700 p-2 rounded-full flex gap-2 shadow-2xl z-50 pointer-events-auto">
      {states.map(state => (
        <button
          key={state}
          onClick={() => setScenarioState(state)}
          className={`px-4 py-1.5 rounded-full text-xs font-bold transition-colors ${
            scenarioState === state 
              ? 'bg-[#7F77DD] text-white' 
              : 'bg-transparent text-slate-400 hover:text-white hover:bg-slate-800'
          }`}
        >
          {state.replace('_', ' ')}
        </button>
      ))}
    </div>
  );
}