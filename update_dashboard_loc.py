import sys
import re

path = "frontend/src/pages/Dashboard.jsx"
with open(path, "r") as f:
    content = f.read()

# Add useEffect and Mapbox geocoding logic
import_effect = r"import \{ useState, useEffect \} from 'react';"
if "import { useState, useEffect } from 'react';" not in content:
    content = content.replace("import { useState } from 'react';", "import { useState, useEffect } from 'react';")

# Find the userLocation state
state_pattern = r"const \[userLocation\] = useState\(\{ lat: 37\.6688, lon: -122\.0828 \}\); // hardcoded user origin for now"
new_state = """  const [userLocation, setUserLocation] = useState({ lat: 37.6688, lon: -122.0828 });
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
  }, []);"""

content = re.sub(state_pattern, new_state, content)

# Update the TelemetryCard props
telemetry_old = r"<TelemetryCard predictions=\{predictions\} windData=\{windData\} alerts=\{alerts\} routeData=\{routeData\} />"
telemetry_new = r"<TelemetryCard predictions={predictions} windData={windData} alerts={alerts} routeData={routeData} userLocation={userLocation} cityName={cityName} />"
content = re.sub(telemetry_old, telemetry_new, content)

with open(path, "w") as f:
    f.write(content)
print("SUCCESS")
