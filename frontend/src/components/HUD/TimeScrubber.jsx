import { useState, useMemo } from 'react';
import ModelSelector from './ModelSelector';

const MODEL_THEMES = {
  pinn: {
    badge: 'bg-teal-50 text-teal-800 border-teal-200',
    ping: 'bg-teal-400',
    dot: 'bg-teal-600',
    slider: 'accent-teal-600',
    tickText: 'text-teal-700 font-bold scale-110',
    tickBar: 'bg-teal-600',
  },
  unet: {
    badge: 'bg-indigo-50 text-indigo-800 border-indigo-200',
    ping: 'bg-indigo-400',
    dot: 'bg-indigo-600',
    slider: 'accent-indigo-600',
    tickText: 'text-indigo-700 font-bold scale-110',
    tickBar: 'bg-indigo-600',
  },
  ensemble: {
    badge: 'bg-purple-50 text-purple-800 border-purple-200',
    ping: 'bg-purple-400',
    dot: 'bg-purple-600',
    slider: 'accent-purple-600',
    tickText: 'text-purple-700 font-bold scale-110',
    tickBar: 'bg-purple-600',
  },
};

export default function TimeScrubber({
  timeScrub,
  setTimeScrub,
  availableHorizons = [0, 1, 3, 6],
  selectedModel = 'pinn',
  onSelectModel = () => {},
}) {
  const allowed = [0, 1, 3, 6];
  const filteredHorizons = availableHorizons.filter(h => allowed.includes(h));
  const horizonsToUse = filteredHorizons.length > 0 ? filteredHorizons : allowed;

  const maxIndex = horizonsToUse.length - 1;
  const currentIndex = horizonsToUse.indexOf(timeScrub) !== -1 ? horizonsToUse.indexOf(timeScrub) : 0;

  // Store base time in state initializer to ensure render purity for ESLint
  const [baseTime] = useState(() => Date.now());
  const targetDate = useMemo(() => new Date(baseTime + timeScrub * 60 * 60 * 1000), [baseTime, timeScrub]);
  const targetTimeStr = useMemo(
    () => targetDate.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' }),
    [targetDate]
  );

  const getBadgeLabel = () => {
    if (timeScrub === 0) {
      return (
        <>
          Forecast: Current State
          <span className="opacity-75 font-medium ml-1">(Active Observed Fire)</span>
        </>
      );
    }
    return (
      <>
        Forecast: +{timeScrub} Hour{timeScrub !== 1 ? 's' : ''}
        <span className="opacity-75 font-medium ml-1">({targetTimeStr})</span>
      </>
    );
  };

  const currentTheme = MODEL_THEMES[selectedModel] || MODEL_THEMES.pinn;

  return (
    <div className="w-full bg-slate-50 border-t border-slate-200 shadow-[0_-4px_6px_-1px_rgba(0,0,0,0.1)]">
      <div className="px-6 py-3 flex flex-col gap-2.5">
        {/* Header: Model Selector (Left) + Forecast Badge (Right) */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-2.5">
          {/* Predictive Model Segmented Switch */}
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">Model:</span>
            <ModelSelector selectedModel={selectedModel} onSelectModel={onSelectModel} />
          </div>

          {/* Active Forecast Time Badge */}
          <div className="flex items-center text-xs font-bold tracking-wide">
            <div
              className={`px-3.5 py-1.5 rounded-full border shadow-sm flex items-center gap-2 transition-all ${currentTheme.badge}`}
            >
              <span className="relative flex h-2 w-2">
                {timeScrub === 0 && (
                  <span
                    className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${currentTheme.ping}`}
                  ></span>
                )}
                <span
                  className={`relative inline-flex rounded-full h-2 w-2 ${currentTheme.dot}`}
                ></span>
              </span>
              {getBadgeLabel()}
            </div>
          </div>
        </div>

        <input
          type="range"
          min="0"
          max={maxIndex}
          step="1"
          value={currentIndex}
          onChange={(e) => setTimeScrub(horizonsToUse[parseInt(e.target.value, 10)])}
          className={`w-full h-2 bg-slate-200 rounded-full appearance-none cursor-pointer outline-none block transition-all ${currentTheme.slider}`}
          style={{ margin: 0, padding: 0 }}
        />

        {/* Tick marks for discrete steps */}
        <div className="flex justify-between px-2 -mt-1 text-[11px] font-medium transition-colors">
          {horizonsToUse.map((h, i) => {
            const isActive = h === timeScrub;
            const label = h === 0 ? '0h' : `+${h}h`;
            return (
              <span
                key={i}
                onClick={() => setTimeScrub(h)}
                className={`flex flex-col items-center cursor-pointer transition-all duration-200 ${
                  isActive
                    ? currentTheme.tickText
                    : 'text-slate-500 hover:text-slate-800'
                }`}
              >
                <span
                  className={`w-0.5 h-2 mb-1 rounded-full ${
                    isActive ? currentTheme.tickBar : 'bg-slate-300'
                  }`}
                ></span>
                {label}
              </span>
            );
          })}
        </div>
      </div>
    </div>
  );
}
