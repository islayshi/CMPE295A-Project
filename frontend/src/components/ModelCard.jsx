import React from 'react';

const ACCENTS = {
  amber: 'bg-amber-500',
  purple: 'bg-purple-600',
  teal: 'bg-teal-600',
  indigo: 'bg-indigo-600',
  slate: 'bg-slate-400',
};

const pct = (v) => `${(v * 100).toFixed(1)}%`;

const ModelCard = ({ name, description, status = 'live', accent = 'slate', test, validationF1, best = false }) => {
  const live = status === 'live';
  return (
    <div
      className={`bg-white border rounded-xl p-6 shadow-sm hover:shadow-md transition-shadow font-sans flex flex-col ${
        best ? 'border-amber-300 ring-1 ring-amber-200' : 'border-gray-200'
      }`}
    >
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex items-center gap-2">
          <span className={`h-3 w-3 rounded-full ${ACCENTS[accent] || ACCENTS.slate}`} aria-hidden="true"></span>
          <h3 className="text-lg font-bold text-gray-900">{name}</h3>
        </div>
        <span
          className={`shrink-0 text-xs font-semibold px-2 py-0.5 rounded-full ${
            live ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-gray-100 text-gray-500 border border-gray-200'
          }`}
        >
          {live ? 'On dashboard' : 'Research only'}
        </span>
      </div>

      <p className="text-sm text-gray-500 mb-5 leading-relaxed">{description}</p>

      <hr className="border-gray-100 mb-4" />

      <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Test fires (11), +6 h</div>
      <div className="grid grid-cols-3 gap-2">
        <MetricBadge label="F1" value={test.f1.toFixed(3)} highlight />
        <MetricBadge label="Precision" value={pct(test.precision)} />
        <MetricBadge label="Hit rate" value={pct(test.hitRate)} />
        <MetricBadge label="IoU (growth)" value={test.iou.toFixed(3)} />
        <MetricBadge label="False alarm" value={`${test.falseAlarmKm2.toFixed(1)} km²`} />
        <MetricBadge label="Avg precision" value={test.ap.toFixed(3)} />
      </div>
      <div className="mt-3 text-xs text-gray-500">
        Validation fires (20): F1 <span className="font-semibold text-gray-700">{validationF1.toFixed(3)}</span>
        {best && <span className="ml-2 text-amber-700 font-semibold">Best on both splits</span>}
      </div>
    </div>
  );
};

const MetricBadge = ({ label, value, highlight = false }) => (
  <div className={`p-2 rounded-lg text-center ${highlight ? 'bg-amber-50 border border-amber-200/60' : 'bg-gray-50'}`}>
    <div className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-0.5">{label}</div>
    <div className={`text-base font-extrabold ${highlight ? 'text-amber-700' : 'text-gray-800'}`}>{value}</div>
  </div>
);

export default ModelCard;
