export default function TimeScrubber({ timeScrub, setTimeScrub }) {
  return (
    <div className="w-full relative group">
      {/* Tooltip / Label that appears above the scrubber on hover */}
      <div className="absolute bottom-full left-0 w-full flex justify-between px-4 pb-2 text-xs font-semibold text-slate-300 opacity-0 group-hover:opacity-100 transition-opacity bg-gradient-to-t from-black/80 to-transparent pt-6 pointer-events-none">
        <span>Now</span>
        <span className="text-red-500 font-bold tracking-wide">
          Prediction Window: +{timeScrub} Hour{timeScrub !== 1 ? 's' : ''}
        </span>
        <span>+24 Hrs</span>
      </div>
      
      {/* Sleek Scrubber Input */}
      <input 
        type="range" 
        min="0" 
        max="24" 
        step="12" 
        value={timeScrub}
        onChange={(e) => setTimeScrub(parseInt(e.target.value))}
        className="w-full h-1.5 bg-slate-800/80 appearance-none cursor-pointer accent-red-600 outline-none block hover:h-2.5 transition-all"
        style={{ margin: 0, padding: 0 }}
      />
    </div>
  );
}