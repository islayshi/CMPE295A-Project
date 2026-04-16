import { ShieldPlus } from 'lucide-react';

export default function Legend() {
  return (
    <div className="pointer-events-auto bg-slate-900/60 backdrop-blur-md border border-slate-700 text-white rounded-xl shadow-lg p-4 w-64">
      <h4 className="text-sm font-bold mb-3 text-slate-200 uppercase tracking-wider">Map Legend</h4>
      <ul className="space-y-3 text-sm">
        <li className="flex items-center gap-3">
          <div className="w-4 h-3 bg-red-500/10 border border-dashed border-red-500"></div>
          <span>Red Flag Warning Zone</span>
        </li>
        <li className="flex items-center gap-3">
          <div className="w-5 h-5 bg-green-600 text-white flex items-center justify-center rounded-full border border-white shadow-sm shrink-0">
            <ShieldPlus size={12} />
          </div>
          <span>Official Evac Shelter</span>
        </li>
        <li className="flex items-center gap-3">
          <div className="w-3 h-3 rounded-full bg-red-600 shadow-[0_0_5px_rgba(220,38,38,0.8)]"></div>
          <span>Current Fire Detection</span>
        </li>
        <li className="flex items-center gap-3">
          <div className="w-3 h-3 bg-orange-500/40 border border-orange-500"></div>
          <span>+1 Hour Spread Risk</span>
        </li>
        <li className="flex items-center gap-3">
          <div className="w-3 h-3 bg-yellow-500/30 border border-yellow-500"></div>
          <span>+3 Hour Spread Risk</span>
        </li>
        <li className="flex items-center gap-3">
          <div className="w-4 h-1 bg-blue-500 shadow-[0_0_4px_rgba(59,130,246,0.8)]"></div>
          <span>Safe Evacuation Route</span>
        </li>
        <li className="flex items-center gap-3">
          <div className="w-4 h-1 border-t-2 border-dashed border-red-500"></div>
          <span>Compromised Road</span>
        </li>
      </ul>
    </div>
  );
}