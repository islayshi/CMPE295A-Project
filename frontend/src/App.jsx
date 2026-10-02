import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import Dashboard from './pages/Dashboard';
import InformationForm from './pages/InformationForm';
import ProfilePage from './pages/ProfilePage';
import ModelPage from './pages/ModelPage';
import DataPage from './pages/DataPage'; 

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/information" element={<InformationForm />} /> 
        <Route path="/profile" element={<ProfilePage />} />
        <Route path="/data" element={<DataPage />} /> 
        <Route path="/model" element={<ModelPage />} /> 
      </Routes>
    </Router>
  );
}

export default App;