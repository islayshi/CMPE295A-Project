import sys
import re

path = "frontend/src/components/HUD/TelemetryCard.jsx"
with open(path, "r") as f:
    content = f.read()

# Replace the component signature
old_sig = r"export default function TelemetryCard\(\{ predictions, windData, alerts, routeData \}\) \{"
new_sig = """
// Helper to bilinearly interpolate vector field at specific lat/lon
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

// Convert U/V components to compass direction (e.g. N, NE, S)
function getCompassDirection(u, v) {
  if (u === 0 && v === 0) return "CALM";
  // Wind direction is WHERE it blows FROM (meteorological standard), but let's just use angle
  const angle = (Math.atan2(v, u) * 180 / Math.PI + 360) % 360;
  const directions = ['W', 'WSW', 'SW', 'SSW', 'S', 'SSE', 'SE', 'ESE', 'E', 'ENE', 'NE', 'NNE', 'N', 'NNW', 'NW', 'WNW'];
  const index = Math.round(angle / 22.5) % 16;
  return directions[index];
}

export default function TelemetryCard({ predictions, windData, alerts, routeData, userLocation, cityName }) {"""

content = re.sub(old_sig, new_sig, content)

# Replace the wind computation logic
old_wind_logic = r"let windText = \"Loading\.\.\.\";\n.*?let maxProbability = 0;"
new_wind_logic = """let windText = "Loading...";
  let windRotation = "rotate-0";
  
  if (windData && windData.length >= 2 && userLocation) {
    const h = windData[0].header;
    const [u, v] = getVector(userLocation.lon, userLocation.lat, h, windData[0].data, windData[1].data);
    
    // Wind is returned directly in MPH by our backend IDW interpolator
    const speed = Math.sqrt(u * u + v * v);
    const dir = getCompassDirection(u, v);
    
    if (speed === 0) {
      windText = "Calm";
    } else {
      windText = `${Math.round(speed)} mph ${dir}`;
      // Calculate rotation for the icon (0 deg is pointing UP)
      // Math.atan2(y, x) where x=u, y=v. 
      const angleDeg = Math.atan2(v, u) * 180 / Math.PI;
      // Invert Y because screen coordinates, adjust by 90 to match SVG arrow pointing up
      const rotation = Math.round(90 - angleDeg); 
      windRotation = `rotate-[${rotation}deg]`;
    }
  }

  let maxProbability = 0;"""

content = re.sub(old_wind_logic, new_wind_logic, content, flags=re.DOTALL)

# Replace the hardcoded location
old_loc = r"<span className=\"font-semibold\">Bay Area, CA</span>"
new_loc = r"<span className=\"font-semibold\">{cityName || 'Bay Area, CA'}</span>"
content = content.replace(old_loc, new_loc)

# Update SVG rotation for arbitrary degrees via style prop
svg_old = r"<svg className={`w-3 h-3 \$\{windRotation\} transition-transform duration-500`} fill=\"none\" stroke=\"currentColor\" viewBox=\"0 0 24 24\">"
# Since Tailwind doesn't compile dynamic string classes like `rotate-[45deg]` dynamically unless safelisted, we should use inline style for dynamic rotation!
svg_new = r"""<svg className="w-3 h-3 transition-transform duration-500" style={{ transform: windRotation.startsWith('rotate-[') ? `rotate(${windRotation.match(/-?\d+/)[0]}deg)` : 'rotate(0deg)' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">"""
content = content.replace(svg_old, svg_new)

with open(path, "w") as f:
    f.write(content)
print("SUCCESS")
