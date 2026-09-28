import sys

path = "frontend/src/components/HUD/TelemetryCard.jsx"
with open(path, "r") as f:
    content = f.read()

# Change windRotation to windAngle (number)
content = content.replace('let windRotation = "rotate-0";', 'let windAngle = 0;')

# Update the math logic
old_math = """      const angleDeg = Math.atan2(v, u) * 180 / Math.PI;
      // Invert Y because screen coordinates, adjust by 90 to match SVG arrow pointing up
      const rotation = Math.round(90 - angleDeg); 
      windRotation = `rotate-[${rotation}deg]`;"""
new_math = """      const angleDeg = Math.atan2(v, u) * 180 / Math.PI;
      windAngle = Math.round(90 - angleDeg);"""
content = content.replace(old_math, new_math)

# Update SVG element
old_svg = """<svg className="w-3 h-3 transition-transform duration-500" style={{ transform: windRotation.startsWith('rotate-[') ? `rotate(${windRotation.match(/-?\\d+/)[0]}deg)` : 'rotate(0deg)' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">"""
new_svg = """<svg className="w-3 h-3 transition-transform duration-500" style={{ transform: `rotate(${windAngle}deg)` }} fill="none" stroke="currentColor" viewBox="0 0 24 24">"""
content = content.replace(old_svg, new_svg)

with open(path, "w") as f:
    f.write(content)
print("SUCCESS")
