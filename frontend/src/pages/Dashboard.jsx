import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import Navbar from '../components/Navbar';
import MapCanvas from '../components/Map/MapCanvas';
import TelemetryWidget from '../components/HUD/TelemetryWidget';
import LayersLegend from '../components/HUD/LayersLegend';
import TimeScrubber from '../components/HUD/TimeScrubber';
import ChatDrawer from '../components/HUD/ChatDrawer';

import { fetchCurrentPredictions } from '../api/predictions';
import { fetchShelters, fetchWindData, fetchAqiData } from '../api/telemetry';

export default function Dashboard() {
  const [timeScrub, setTimeScrub] = useState(0);
  const [isAqiVisible, setIsAqiVisible] = useState(false);
  const [isChatOpen, setIsChatOpen] = useState(false);
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

  const { data: aqiData } = useQuery({
    queryKey: ['telemetry', 'aqi'],
    queryFn: fetchAqiData,
    refetchInterval: 300000,  // Poll every 5 minutes
  });

  return (
    <div className="relative w-screen h-screen overflow-hidden bg-black text-white font-sans">
      <Navbar onChatToggle={() => setIsChatOpen(!isChatOpen)} />
      
      <MapCanvas 
        predictions={predictions}
        shelters={shelters}
        windData={windData}
        userLocation={userLocation}
        isAqiVisible={isAqiVisible}
        aqiData={aqiData}
        timeScrub={timeScrub}
      />
      
      <LayersLegend 
        isAqiVisible={isAqiVisible} 
        setIsAqiVisible={setIsAqiVisible} 
      />
      
      <TelemetryWidget 
        windData={windData} 
        userLocation={userLocation} 
        cityName={cityName}
        aqiData={aqiData}
      />
        
      <div className="absolute bottom-0 left-0 w-full z-40 pointer-events-auto">
        <TimeScrubber timeScrub={timeScrub} setTimeScrub={setTimeScrub} />
      </div>

      <ChatDrawer isOpen={isChatOpen} onClose={() => setIsChatOpen(false)} />
    </div>
  );
}
