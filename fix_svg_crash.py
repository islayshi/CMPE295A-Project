import sys

path = "frontend/src/components/HUD/TelemetryCard.jsx"
with open(path, "r") as f:
    content = f.read()

# Replace the broken SVG className
old_line = '<svg className={`w-3 h-3 ${windRotation} transition-transform duration-500`} fill="none" stroke="currentColor" viewBox="0 0 24 24">'
new_line = '<svg className="w-3 h-3 transition-transform duration-500" style={{ transform: `rotate(${windAngle}deg)` }} fill="none" stroke="currentColor" viewBox="0 0 24 24">'

content = content.replace(old_line, new_line)

with open(path, "w") as f:
    f.write(content)
print("SUCCESS")
