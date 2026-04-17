import { Link, useLocation } from 'react-router-dom';
import { Flame } from 'lucide-react';

const Navbar = () => {
  const location = useLocation();
  
  const isActive = (path) => {
    return location.pathname === path ? "text-white font-semibold" : "text-gray-400 hover:text-white";
  };

  return (
    <nav className="fixed top-0 left-0 w-full h-16 bg-[#111]/90 backdrop-blur-md border-b border-gray-800 z-50 flex items-center justify-between px-6 shadow-md">
      <div className="flex items-center gap-2 text-white font-bold text-xl tracking-tight">
        <Flame className="text-[#7F77DD]" size={24} />
        <span><span className="text-[#7F77DD]">FightFire</span>WithAI</span>
      </div>
      
      <div className="flex gap-8 text-sm font-medium">
        <Link to="/" className={`transition-colors ${isActive('/')}`}>Home</Link>
        <Link to="/routing" className={`transition-colors ${isActive('/routing')}`}>Evacuation Routing</Link>
        <Link to="/chatbot" className={`transition-colors ${isActive('/chatbot')}`}>Chatbot</Link>
      </div>
      
      <div>
        <Link to="/login" className="text-sm font-semibold text-[#7F77DD] hover:text-[#958df0] transition-colors border border-[#7F77DD]/30 hover:border-[#7F77DD] px-4 py-2 rounded-lg bg-[#7F77DD]/10 hover:bg-[#7F77DD]/20">
          Login
        </Link>
      </div>
    </nav>
  );
};

export default Navbar;