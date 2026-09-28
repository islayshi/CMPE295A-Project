import sys

path = "frontend/src/components/HUD/TelemetryCard.jsx"
with open(path, "r") as f:
    content = f.read()

# 1. Fix the Bay Area, CA fallback
content = content.replace('<span className="font-semibold">Bay Area, CA</span>', '<span className="font-semibold">{cityName || "Bay Area, CA"}</span>')

# 2. Fix the getCompassDirection array
old_dir = "const directions = ['W', 'WSW', 'SW', 'SSW', 'S', 'SSE', 'SE', 'ESE', 'E', 'ENE', 'NE', 'NNE', 'N', 'NNW', 'NW', 'WNW'];"
new_dir = "const directions = ['E', 'ENE', 'NE', 'NNE', 'N', 'NNW', 'NW', 'WNW', 'W', 'WSW', 'SW', 'SSW', 'S', 'SSE', 'SE', 'ESE'];"
content = content.replace(old_dir, new_dir)

# 3. Update the text to "blowing E" etc.
old_text = "windText = `${Math.round(speed)} mph ${dir}`;"
new_text = "windText = `${Math.round(speed)} mph ${dir}`;"
# Just 'dir' is fine, but maybe let's add a tooltip or just keep it simple. E.g. "12 mph E"
content = content.replace(old_text, new_text)

with open(path, "w") as f:
    f.write(content)
print("SUCCESS")
