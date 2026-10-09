import { Link, useLocation } from 'react-router-dom';
import { Flame, Map, Cpu, Database } from 'lucide-react';

const Navbar = () => {
  const location = useLocation();
  
  const navItems = [
    { name: 'Live Map', path: '/', icon: Map },
    { name: 'Model', path: '/model', icon: Cpu },
    { name: 'Data', path: '/data', icon: Database },
  ];

  return (
    <nav className="fixed top-0 left-0 w-full h-16 bg-white/90 backdrop-blur-md border-b border-slate-200 z-50 flex items-center justify-between px-6 shadow-[0_4px_20px_-10px_rgba(0,0,0,0.1)]">
      {/* Brand */}
      <div className="flex items-center gap-2 text-slate-800 font-extrabold text-xl tracking-tight w-64">
        <Flame className="text-orange-600" size={26} strokeWidth={2.5} />
        <span>FightFire<span className="text-orange-600">WithAI</span></span>
      </div>
      
      {/* Nav Links (Segmented Control Style) */}
      <div className="flex gap-1 text-sm font-semibold items-center bg-slate-100 p-1.5 rounded-full border border-slate-200/60 shadow-inner">
        {navItems.map((item) => {
          const isActive = location.pathname === item.path;
          const Icon = item.icon;
          return (
            <Link 
              key={item.path}
              to={item.path} 
              className={`flex items-center gap-2 px-5 py-2 rounded-full transition-all duration-300 ease-out ${
                isActive 
                  ? "bg-white text-orange-600 shadow-sm border border-slate-200/50 scale-105" 
                  : "text-slate-500 hover:text-slate-800 hover:bg-slate-200/60"
              }`}
            >
              <Icon size={16} strokeWidth={isActive ? 2.5 : 2} className={isActive ? "text-orange-500" : "text-slate-400"} />
              <span>{item.name}</span>
            </Link>
          );
        })}
      </div>
      
      {/* Right Spacer for visual balance (matches the width of the brand logo) */}
      <div className="w-64 flex justify-end">
      </div>
    </nav>
  );
};

export default Navbar;
