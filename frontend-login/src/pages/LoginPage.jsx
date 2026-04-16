import { Link } from 'react-router-dom';

const LoginPage = () => {
  return (
    <div style={{ maxWidth: '300px', margin: 'auto', textAlign: 'center' }}>
      <h2>Login</h2>
      <form style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
        <input type="email" placeholder="Email" required />
        <input type="password" placeholder="Password" required />
        <button type="submit">Login</button>
      </form>
      <p>
        New User? <Link to="/register">Sign up</Link>
      </p>
    </div>
  );
};

export default LoginPage;