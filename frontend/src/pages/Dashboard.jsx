import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import Navbar from '../components/Navbar';
import MapCanvas from '../components/Map/MapCanvas';
import TelemetryCard from '../components/HUD/TelemetryCard';
import Legend from '../components/HUD/Legend';
import TimeScrubber from '../components/HUD/TimeScrubber';
import ChatDrawer from '../components/HUD/ChatDrawer';
import WeatherForecast from '../components/WeatherForecast';

import { fetchCurrentPredictions } from '../api/predictions';
import { fetchShelters, fetchWindData, fetchAlerts } from '../api/telemetry';

export default function Dashboard() {
  const [timeScrub, setTimeScrub] = useState(0);
  const [isWeatherOpen, setIsWeatherOpen] = useState(false);
    const [userLocation, setUserLocation] = useState({ lat: 37.6688, lon: -122.0828 });
  const [cityName, setCityName] = useState("Hayward, CA");

  useEffect(() => {
    // 1. Get exact GPS location
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        async (position) => {
          const lat = position.coords.latitude;
          const lon = position.coords.longitude;
          setUserLocation({ lat, lon });
          
          // 2. Reverse Geocode via Mapbox
          try {
            const token = import.meta.env.VITE_MAPBOX_ACCESS_TOKEN || 'pk.eyJ1IjoiZGV2IiwiYSI6ImNrbXZ6bHcyZDBhMTEydm8wc3Nqd3o1ZWUifQ.mock';
            const res = await fetch(`https://api.mapbox.com/geocoding/v5/mapbox.places/${lon},${lat}.json?access_token=${token}&types=place`);
            const data = await res.json();
            if (data.features && data.features.length > 0) {
              setCityName(data.features[0].place_name.split(',').slice(0, 2).join(',')); // e.g. "San Jose, California"
            }
          } catch (e) {
            console.error("Geocoding failed", e);
          }
        },
        (error) => {
          console.warn("Geolocation denied or failed. Using fallback.", error);
        },
        { enableHighAccuracy: true }
      );
    }
  }, []);
  
  // React Query - Poll predictions every 5 minutes (300,000 ms)
  const { data: predictions } = useQuery({
    queryKey: ['predictions', 'current'],
    queryFn: fetchCurrentPredictions,
    refetchInterval: 300000, 
  });

  const { data: shelters } = useQuery({
    queryKey: ['telemetry', 'shelters'],
    queryFn: fetchShelters,
  });

  const { data: windData } = useQuery({
    queryKey: ['telemetry', 'wind'],
    queryFn: fetchWindData,
  });

  const { data: alerts } = useQuery({
    queryKey: ['telemetry', 'alerts'],
    queryFn: fetchAlerts,
  });

  return (
    <div className="relative w-screen h-screen overflow-hidden bg-black text-white font-sans">
      <Navbar />
      
      <MapCanvas 
        predictions={predictions}
        shelters={shelters}
        windData={windData}
        alerts={alerts}
        userLocation={userLocation}
        timeScrub={timeScrub}
      />
      
      {/* HUD Overlays */}
      <div className="absolute inset-0 z-40 pointer-events-none p-6 pt-24 flex flex-col justify-between">
        <div className="flex justify-between items-start">
          <Legend />
          <div className="flex flex-col items-end gap-4 pointer-events-auto">
            <TelemetryCard predictions={predictions} windData={windData} alerts={alerts} userLocation={userLocation} cityName={cityName} />
            <button 
              onClick={() => setIsWeatherOpen(true)}
              className="bg-slate-900/60 backdrop-blur-md border border-slate-700 text-white px-4 py-2 rounded-xl shadow-lg hover:bg-slate-800/80 transition-colors flex items-center gap-2 text-sm font-bold"
            >
              <svg className="w-4 h-4 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 15a4 4 0 004 4h9a5 5 0 10-.1-9.999 5.002 5.002 0 10-9.78 2.096A4.001 4.001 0 003 15z" /></svg>
              Detailed Forecast
            </button>
          </div>
        </div>
        
        <div className="flex justify-center items-end pb-8 pointer-events-auto">
          <TimeScrubber timeScrub={timeScrub} setTimeScrub={setTimeScrub} />
        </div>
      </div>

      <ChatDrawer />

      {/* Weather Modal Overlay */}
      {isWeatherOpen && (
        <div className="absolute inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-6">
          <div className="relative bg-white rounded-2xl shadow-2xl max-w-4xl w-full max-h-[90vh] overflow-y-auto text-black">
            <button 
              onClick={() => setIsWeatherOpen(false)}
              className="absolute top-4 right-4 p-2 text-gray-400 hover:text-gray-800 bg-gray-100 hover:bg-gray-200 rounded-full transition-colors z-10"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
            <WeatherForecast />
          </div>
        </div>
      )}
    </div>
  );
}
