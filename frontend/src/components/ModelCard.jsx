import React, { useState } from 'react';

const ModelCard = ({
  name = "U-Net Baseline Model",
  description = "Convolutional network trained on satellite imagery for spatial perimeter delineation.",
  metrics = {
    accuracy: 91.4,
    precision: 88.7,
    recall: 86.2,
    f1Score: 87.4,
  },
  initialEnabled = true,
  onToggle,
}) => {
  const [isEnabled, setIsEnabled] = useState(initialEnabled);

  const handleToggle = () => {
    const newState = !isEnabled;
    setIsEnabled(newState);
    if (onToggle) onToggle(newState);
  };

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-sm hover:shadow-md transition-shadow max-w-md font-sans">
      {/* Header: Name, Version & Toggle */}
      <div className="flex items-center justify-between mb-3">
        <div>
          <h3 className="text-lg font-bold text-gray-900">{name}</h3>
        </div>

        {/* On/Off Switch */}
        <label className="relative inline-flex items-center cursor-pointer">
          <input
            type="checkbox"
            checked={isEnabled}
            onChange={handleToggle}
            className="sr-only peer"
          />
          <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-emerald-600"></div>
        </label>
      </div>

      {/* Description */}
      <p className="text-sm text-gray-500 mb-5 leading-relaxed">
        {description}
      </p>

      {/* Status Indicator */}
      <div className="flex items-center gap-2 mb-4 text-xs font-medium">
        <span
          className={`h-2.5 w-2.5 rounded-full ${
            isEnabled ? 'bg-emerald-500 animate-pulse' : 'bg-gray-300'
          }`}
        ></span>
        <span className={isEnabled ? 'text-emerald-700' : 'text-gray-400'}>
          {isEnabled ? 'Ready for Inference' : 'Inactive'}
        </span>
      </div>

      <hr className="border-gray-100 mb-4" />

      {/* Metrics Grid */}
      <div className="grid grid-cols-2 gap-3">
        <MetricBadge label="Accuracy" value={`${metrics.accuracy}%`} />
        <MetricBadge label="Precision" value={`${metrics.precision}%`} />
        <MetricBadge label="Recall" value={`${metrics.recall}%`} />
        <MetricBadge label="F1 Score" value={`${metrics.f1Score}%`} highlight />
      </div>
    </div>
  );
};

// Internal reusable helper badge for stats
const MetricBadge = ({ label, value, highlight = false }) => (
  <div
    className={`p-3 rounded-lg text-center ${
      highlight ? 'bg-amber-50 border border-amber-200/60' : 'bg-gray-50'
    }`}
  >
    <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">
      {label}
    </div>
    <div
      className={`text-lg font-extrabold ${
        highlight ? 'text-amber-700' : 'text-gray-800'
      }`}
    >
      {value}
    </div>
  </div>
);

export default ModelCard;