export default function TimeScrubber({ timeScrub, setTimeScrub, availableHorizons = [0, 1, 3, 6] }) {
  // Enforce the requirement: "The time scrubber should be updated to only show +0h, +1h, +3, and +6h; +24h is not possible so it must be remove."
  const allowed = [0, 1, 3, 6];
  const filteredHorizons = availableHorizons.filter(h => allowed.includes(h));
  const horizonsToUse = filteredHorizons.length > 0 ? filteredHorizons : allowed;

  const maxIndex = horizonsToUse.length - 1;
  const currentIndex = horizonsToUse.indexOf(timeScrub) !== -1 ? horizonsToUse.indexOf(timeScrub) : 0;

  // Calculate target time to give users a concrete ETA
  const targetDate = new Date(Date.now() + timeScrub * 60 * 60 * 1000);
  const targetTimeStr = targetDate.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });

  return (
    <div className="w-full bg-slate-50 border-t border-slate-200 shadow-[0_-4px_6px_-1px_rgba(0,0,0,0.1)]">
      <div className="px-6 py-3 flex flex-col gap-3">
        
        {/* Centered Badge for Active Forecast Time */}
        <div className="flex justify-center items-center text-sm font-bold tracking-wide">
          <div className="px-4 py-1.5 bg-orange-100 text-orange-700 rounded-full border border-orange-300 shadow-sm flex items-center gap-2 transition-all">
            <span className="relative flex h-2 w-2">
              {timeScrub === 0 && <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-orange-400 opacity-75"></span>}
              <span className="relative inline-flex rounded-full h-2 w-2 bg-orange-500"></span>
            </span>
            Forecast: +{timeScrub} Hour{timeScrub !== 1 ? 's' : ''} 
            <span className="opacity-75 font-medium ml-1">
              ({timeScrub === 0 ? 'Current' : targetTimeStr})
            </span>
          </div>
        </div>
        
        <input 
          type="range" 
          min="0" 
          max={maxIndex}
          step="1" 
          value={currentIndex}
          onChange={(e) => setTimeScrub(horizonsToUse[parseInt(e.target.value)])}
          className="w-full h-2 bg-slate-200 rounded-full appearance-none cursor-pointer accent-orange-600 outline-none block transition-all"
          style={{ margin: 0, padding: 0 }}
        />
        
        {/* Tick marks for discrete steps */}
        <div className="flex justify-between px-2 -mt-1 text-[11px] font-medium transition-colors">
          {horizonsToUse.map((h, i) => {
            const isActive = h === timeScrub;
            return (
              <span 
                key={i} 
                className={`flex flex-col items-center transition-all duration-200 ${isActive ? 'text-orange-700 font-bold scale-110' : 'text-slate-500'}`}
              >
                <span className={`w-0.5 h-2 mb-1 rounded-full ${isActive ? 'bg-orange-500' : 'bg-slate-300'}`}></span>
                +{h}h
              </span>
            );
          })}
        </div>
      </div>
    </div>
  );
}