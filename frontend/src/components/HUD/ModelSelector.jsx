import { Sparkles, Cpu, Flame } from 'lucide-react';

const MODELS = [
  { id: 'ensemble', label: 'Ensemble', icon: Sparkles, hint: 'Blended 0.6 U-Net + 0.4 PINN' },
  { id: 'unet', label: 'U-Net', icon: Cpu, hint: 'Spatial Segmentation' },
  { id: 'pinn', label: 'PINN', icon: Flame, hint: 'Physics-Informed Spread' },
];

export default function ModelSelector({ selectedModel, onSelectModel, className = '' }) {
  return (
    <div
      className={`inline-flex items-center bg-white/90 backdrop-blur-md border border-slate-200 shadow-lg rounded-full p-1 pointer-events-auto transition-all ${className}`}
      role="radiogroup"
      aria-label="Predictive Model"
    >
      {MODELS.map((model) => {
        const Icon = model.icon;
        const isActive = selectedModel === model.id;
        return (
          <button
            key={model.id}
            type="button"
            role="radio"
            aria-checked={isActive}
            title={model.hint}
            onClick={() => onSelectModel(model.id)}
            className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-full transition-all duration-200 ${
              isActive
                ? 'bg-orange-600 text-white shadow-sm'
                : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
            }`}
          >
            <Icon size={14} className={isActive ? 'text-white' : 'text-slate-500'} />
            <span>{model.label}</span>
          </button>
        );
      })}
    </div>
  );
}
