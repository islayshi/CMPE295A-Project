const MODELS = [
  {
    id: 'pinn',
    label: 'PIML',
    hint: 'Physics-Informed Machine Learning (v0.3.1 Spread)',
    activeClass: 'bg-orange-600 text-white shadow-sm ring-1 ring-orange-500/20 font-semibold',
  },
  {
    id: 'unet',
    label: 'U-Net',
    hint: 'Spatial Segmentation (GOES-18 ABI)',
    activeClass: 'bg-indigo-600 text-white shadow-sm ring-1 ring-indigo-500/20 font-semibold',
  },
  {
    id: 'ensemble',
    label: 'Ensemble',
    hint: 'Multi-Model Consensus (Pending AI/ML Team Specification)',
    disabled: true,
    activeClass: 'bg-purple-600 text-white shadow-sm ring-1 ring-purple-500/20 font-semibold',
  },
];

export default function ModelSelector({ selectedModel, onSelectModel, className = '' }) {
  return (
    <div
      className={`inline-flex items-center bg-white border border-slate-200 shadow-sm rounded-full p-0.5 pointer-events-auto transition-all ${className}`}
      role="radiogroup"
      aria-label="Predictive Model"
    >
      {MODELS.map((model) => {
        const isActive = selectedModel === model.id;
        const isDisabled = Boolean(model.disabled);
        return (
          <button
            key={model.id}
            type="button"
            role="radio"
            disabled={isDisabled}
            aria-checked={isActive}
            title={model.hint}
            onClick={() => !isDisabled && onSelectModel(model.id)}
            className={`px-3 py-1 text-xs rounded-full transition-all duration-200 tracking-wide ${
              isDisabled
                ? 'opacity-40 cursor-not-allowed text-slate-400 font-medium'
                : isActive
                ? model.activeClass
                : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100 font-medium'
            }`}
          >
            {model.label}
          </button>
        );
      })}
    </div>
  );
}
