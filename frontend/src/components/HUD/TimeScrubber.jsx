export default function TimeScrubber({ timeScrub, setTimeScrub }) {
  return (
    <div className="pointer-events-auto bg-slate-900/60 backdrop-blur-md border border-slate-700 text-white rounded-xl shadow-lg p-4 w-96 flex flex-col items-center">
      <div className="flex justify-between w-full text-xs font-semibold text-slate-300 mb-2 px-1">
        <span>Now</span>
        <span>+3 Hrs</span>
        <span>+6 Hrs</span>
      </div>
      <input 
        type="range" 
        min="0" 
        max="6" 
        step="1" 
        value={timeScrub}
        onChange={(e) => setTimeScrub(parseInt(e.target.value))}
        className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-blue-500 outline-none"
      />
      <div className="mt-2 text-sm font-bold text-blue-400">
        Prediction Window: +{timeScrub} Hour{timeScrub !== 1 ? 's' : ''}
      </div>
    </div>
  );
}