import './App.css'
import WeatherForecast from "./components/WeatherForecast";

export default function App() {
  return (
    <div style={{ minHeight: "100vh", background: "#f5f5f5", padding: "2rem 1rem" }}>
      <WeatherForecast />
    </div>
  );
}