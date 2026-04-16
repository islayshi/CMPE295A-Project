import { Link } from 'react-router-dom';

const Navbar = () => {
  return (
    <nav className="navbar">
      <div className="nav-logo">FightFireWithAI</div>
      <div className="nav-links">
        <Link to="/dashboard">Home</Link>
        <Link to="/routing">Evacuation Routing</Link>
        <Link to="/chatbot">Chatbot</Link>
      </div>
      <div className="nav-logout">
        <Link to="/">Logout</Link>
      </div>
    </nav>
  );
};

export default Navbar;