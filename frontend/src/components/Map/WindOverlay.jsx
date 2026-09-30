import { useMemo, useEffect, useState } from 'react';
import { TripsLayer } from '@deck.gl/geo-layers';
import { MapboxOverlay } from '@deck.gl/mapbox';
import { useControl } from 'react-map-gl/mapbox';

// Helper to bilinearly interpolate vector field
function getVector(x, y, header, uData, vData) {
  const { nx, ny, lo1, la1, dx, dy } = header;
  const i = (x - lo1) / dx;
  const j = (y - la1) / dy;
  if (i < 0 || i >= nx - 1 || j < 0 || j >= ny - 1) return [0, 0];
  const i0 = Math.floor(i), i1 = i0 + 1, j0 = Math.floor(j), j1 = j0 + 1;
  const u = i - i0, v = j - j0;
  const idx00 = j0 * nx + i0, idx10 = j0 * nx + i1, idx01 = j1 * nx + i0, idx11 = j1 * nx + i1;
  
  const u_interp = uData[idx00] * (1 - u) * (1 - v) + uData[idx10] * u * (1 - v) + uData[idx01] * (1 - u) * v + uData[idx11] * u * v;
  const v_interp = vData[idx00] * (1 - u) * (1 - v) + vData[idx10] * u * (1 - v) + vData[idx01] * (1 - u) * v + vData[idx11] * u * v;
  return [u_interp, v_interp];
}

const getPath = d => d.path;
const getTimestamps = d => d.timestamps;
const getColor = () => [255, 255, 255];

const generateTrips = (data) => {

    if (!data || data.length < 2 || !data[0].header) return [];
    const h = data[0].header;
    const generatedTrips = [];
    
    for (let p = 0; p < 1200; p++) {
      let lon = h.lo1 + Math.random() * (h.nx * h.dx);
      let lat = h.la1 + Math.random() * (h.ny * h.dy);
      const path = [];
      const timestamps = [];
      let currentTime = Math.random() * 100;
      
      for (let s = 0; s < 20; s++) {
        path.push([lon, lat]);
        timestamps.push(currentTime);
        const [u, v] = getVector(lon, lat, h, data[0].data, data[1].data);
        if (u === 0 && v === 0) break;
        lon += u * 0.003;
        lat += v * 0.003;
        currentTime += 1;
      }
      if (path.length > 1) generatedTrips.push({ path, timestamps });
    }
    return generatedTrips;
  };

export default function WindOverlay({ data }) {
  const [time, setTime] = useState(0);


  const trips = useMemo(() => generateTrips(data), [data]);

  useEffect(() => {
    let frame;
    const animate = () => {
      setTime(t => (t + 0.05) % 150);
      frame = window.requestAnimationFrame(animate);
    };
    animate();
    return () => window.cancelAnimationFrame(frame);
  }, []);



  const overlay = useControl(() => new MapboxOverlay({ interleaved: true, layers: [] }));
  
  useEffect(() => {
    if (trips.length > 0) {
      const layer = new TripsLayer({
        id: 'wind-trips',
        data: trips,
        getPath,
        getTimestamps,
        getColor,
        widthMinPixels: 3,
        trailLength: 4,
        opacity: 0.85,
        currentTime: time
      });
      overlay.setProps({ layers: [layer] });
    }
  }, [time, trips, overlay]);

  return null;
}
