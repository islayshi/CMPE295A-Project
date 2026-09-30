import { Link, useLocation } from 'react-router-dom';
import { Flame, MessageSquare } from 'lucide-react';

const Navbar = ({ onChatToggle }) => {
  const location = useLocation();
  
  const isActive = (path) => {
    return location.pathname === path ? "text-slate-800 font-semibold" : "text-slate-800 hover:text-slate-900";
  };

  return (
    <nav className="fixed top-0 left-0 w-full h-16 bg-white backdrop-blur-md border-b border-slate-200 z-50 flex items-center justify-between px-6 shadow-sm">
      <div className="flex items-center gap-2 text-slate-800 font-bold text-xl tracking-tight">
        <Flame className="text-orange-600" size={24} />
        <span>FightFire<span className="text-orange-600">WithAI</span></span>
      </div>
      
      <div className="flex gap-8 text-sm font-medium items-center">
        <Link to="/" className={`transition-colors ${isActive('/')}`}>Home</Link>
        {onChatToggle ? (
          <button 
            onClick={onChatToggle}
            className="flex items-center gap-1.5 text-slate-800 hover:text-slate-900 transition-colors cursor-pointer"
          >
            <MessageSquare size={16} />
            <span>Chatbot</span>
          </button>
        ) : (
          <Link to="/" className={`transition-colors text-slate-800 hover:text-slate-900`}>Chatbot</Link>
        )}
      </div>
      
      <div>
        <Link to="/login" className="text-sm font-semibold text-orange-600 hover:text-white transition-colors border border-orange-600 hover:border-orange-600 px-4 py-2 rounded-lg bg-transparent hover:bg-orange-600">
          Login
        </Link>
      </div>
    </nav>
  );
};

export default Navbar;
