import { useState } from 'react';
import { Layers, ShieldPlus, Activity, Map as MapIcon, X } from 'lucide-react';
// eslint-disable-next-line no-unused-vars
import { motion, AnimatePresence } from 'framer-motion';

export default function LayersLegend({ isAqiVisible, setIsAqiVisible }) {
  const [isOpen, setIsOpen] = useState(false);

  const aqiLegend = [
    { label: 'Good (0–50)', color: '#22c55e' },
    { label: 'Moderate (51–100)', color: '#eab308' },
    { label: 'Unhealthy (Sensitive) (101–150)', color: '#f97316' },
    { label: 'Unhealthy (151–200)', color: '#ef4444' },
    { label: 'Very Unhealthy (201–300)', color: '#a855f7' },
  ];

  return (
    <>
      <div className="absolute top-20 left-6 z-40">
        <button
          onClick={() => setIsOpen(true)}
          className={`flex items-center justify-center p-3 bg-white/90 backdrop-blur-md border border-slate-200 text-slate-800 rounded-full shadow-lg hover:bg-slate-50 transition-all duration-300 ${isOpen ? 'opacity-0 pointer-events-none' : 'opacity-100 pointer-events-auto'}`}
          title="Layers & Legend"
        >
          <Layers size={20} />
        </button>
      </div>

      <AnimatePresence>
        {isOpen && (
          <motion.div 
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.2 }}
            className="absolute top-20 left-6 w-72 bg-slate-50 backdrop-blur-xl border border-slate-200 shadow-2xl rounded-2xl flex flex-col z-50 pointer-events-auto overflow-hidden text-slate-800"
          >
            <div className="p-4 border-b border-slate-200 flex justify-between items-center bg-white/60">
              <h2 className="font-bold text-sm flex items-center gap-2"><MapIcon size={16}/> Layers & Legend</h2>
              <button onClick={() => setIsOpen(false)} className="text-slate-500 hover:text-slate-800 transition-colors">
                <X size={18} />
              </button>
            </div>

            <div className="p-4 space-y-6">
              {/* Layer Toggles */}
              <div>
                <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider mb-3">Map Layers</h3>
                <button
                  onClick={() => setIsAqiVisible(!isAqiVisible)}
                  className="w-full flex justify-between items-center bg-white hover:bg-slate-100 transition-colors p-3 rounded-lg border border-slate-200"
                >
                  <div className="flex items-center gap-2">
                    <Activity size={16} className={isAqiVisible ? 'text-orange-600' : 'text-slate-400'} />
                    <span className="text-sm font-medium text-slate-800">AQI Grid Layer</span>
                  </div>
                  <div className={`w-8 h-4 rounded-full p-0.5 transition-colors ${isAqiVisible ? 'bg-orange-600' : 'bg-slate-300'}`}>
                    <div className={`bg-white w-3 h-3 rounded-full shadow-sm transition-transform ${isAqiVisible ? 'translate-x-4' : 'translate-x-0'}`}></div>
                  </div>
                </button>
              </div>

              {/* Map Legend */}
              <div>
                <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider mb-3">Map Legend</h3>
                <ul className="space-y-2.5 text-sm">
                  <li className="flex items-center gap-3">
                    <div className="w-4 h-3 bg-red-500/10 border border-dashed border-red-500 rounded-sm"></div>
                    <span className="text-slate-800">Red Flag Warning Zone</span>
                  </li>
                  <li className="flex items-center gap-3">
                    <div className="w-5 h-5 bg-green-600 text-white flex items-center justify-center rounded-full border border-white/20 shadow-sm shrink-0">
                      <ShieldPlus size={10} />
                    </div>
                    <span className="text-slate-800">Official Evac Shelter</span>
                  </li>
                  <li className="flex items-center gap-3">
                    <div className="w-3 h-3 bg-red-600/80 border border-red-600 rounded-sm"></div>
                    <span className="text-slate-800">Active Fire</span>
                  </li>
                  <li className="flex items-center gap-3">
                    <div className="w-3 h-3 bg-orange-500/60 border border-orange-500 rounded-sm"></div>
                    <span className="text-slate-800">High Risk</span>
                  </li>
                  <li className="flex items-center gap-3">
                    <div className="w-3 h-3 bg-yellow-400/60 border border-yellow-500 rounded-sm"></div>
                    <span className="text-slate-800">Moderate Risk</span>
                  </li>
                  <li className="flex items-center gap-3">
                    <div className="w-3 h-3 bg-green-500/60 border border-green-500 rounded-sm"></div>
                    <span className="text-slate-800">Low Risk</span>
                  </li>
                </ul>
              </div>

              {/* AQI Legend */}
              <AnimatePresence>
                {isAqiVisible && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    className="overflow-hidden"
                  >
                    <div className="pt-4 border-t border-slate-200">
                      <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider mb-3">AQI Scale</h3>
                      <div className="space-y-2">
                        {aqiLegend.map((item, idx) => (
                          <div key={idx} className="flex items-center gap-3">
                            <span
                              className="w-3 h-3 rounded-full shrink-0 shadow-sm"
                              style={{ backgroundColor: item.color }}
                            />
                            <span className="text-xs text-slate-800 font-medium">{item.label}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
