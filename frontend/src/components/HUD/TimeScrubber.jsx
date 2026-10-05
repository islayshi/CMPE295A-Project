export default function TimeScrubber({ timeScrub, setTimeScrub, availableHorizons = [0, 1, 3, 6] }) {
  const maxIndex = availableHorizons.length - 1;
  const currentIndex = availableHorizons.indexOf(timeScrub) !== -1 ? availableHorizons.indexOf(timeScrub) : 0;
  const maxHorizon = availableHorizons[maxIndex];

  return (
    <div className="w-full bg-slate-50 border-t border-slate-200 shadow-[0_-4px_6px_-1px_rgba(0,0,0,0.1)]">
      <div className="px-6 py-3 flex flex-col gap-2">
        <div className="flex justify-between items-center text-xs font-bold text-slate-800 tracking-wider">
          <span>Now</span>
          <span className="text-orange-600">
            Prediction Window: +{timeScrub} Hour{timeScrub !== 1 ? 's' : ''}
          </span>
          <span>+{maxHorizon} Hrs</span>
        </div>
        
        <input 
          type="range" 
          min="0" 
          max={maxIndex}
          step="1" 
          value={currentIndex}
          onChange={(e) => setTimeScrub(availableHorizons[parseInt(e.target.value)])}
          className="w-full h-2 bg-slate-200 rounded-full appearance-none cursor-pointer accent-orange-600 outline-none block"
          style={{ margin: 0, padding: 0 }}
        />
        
        {/* Tick marks for discrete steps */}
        <div className="flex justify-between px-2 -mt-1 text-[10px] font-medium text-slate-800">
          {availableHorizons.map((h, i) => (
            <span key={i} className="flex flex-col items-center">
              <span className="w-0.5 h-1.5 bg-slate-300 mb-0.5"></span>
              +{h}h
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}