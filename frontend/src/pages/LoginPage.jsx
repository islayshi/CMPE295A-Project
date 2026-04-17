import { Link } from 'react-router-dom';

const LoginPage = () => {
  return (
    <div className="flex items-center justify-center min-h-screen bg-[#111] text-white font-sans">
      <div className="w-full max-w-md p-8 space-y-6 bg-[#1a1a1a] rounded-xl shadow-2xl border border-gray-800">
        <div className="text-center">
          <h2 className="text-3xl font-bold text-white tracking-tight">Welcome Back</h2>
          <p className="text-gray-400 mt-2 text-sm">Sign in to FightFireWithAI</p>
        </div>
        
        <form className="flex flex-col gap-4 mt-8">
          <div>
            <input 
              type="email" 
              placeholder="Email address" 
              required 
              className="w-full px-4 py-3 bg-[#222] border border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#7F77DD] focus:border-transparent text-white placeholder-gray-500 transition-all"
            />
          </div>
          <div>
            <input 
              type="password" 
              placeholder="Password" 
              required 
              className="w-full px-4 py-3 bg-[#222] border border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#7F77DD] focus:border-transparent text-white placeholder-gray-500 transition-all"
            />
          </div>
          <button 
            type="submit"
            className="w-full py-3 mt-4 font-semibold text-white bg-[#7F77DD] rounded-lg hover:bg-[#6b62c7] focus:outline-none focus:ring-2 focus:ring-[#7F77DD] focus:ring-offset-2 focus:ring-offset-[#1a1a1a] transition-all"
          >
            Login
          </button>
        </form>
        
        <p className="text-center text-gray-400 mt-6 text-sm">
          New User? <Link to="/register" className="text-[#7F77DD] hover:text-[#958df0] font-medium hover:underline transition-colors">Sign up</Link>
        </p>
      </div>
    </div>
  );
};

export default LoginPage;