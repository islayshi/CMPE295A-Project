import sys
import re

path = "frontend/src/components/Map/WindOverlay.jsx"
with open(path, "r") as f:
    content = f.read()

old_color_logic = r"getColor: d => \{.*?\},\s*opacity: 0.8,"

new_color_logic = """getColor: d => {
          if (d.path.length < 2) return [100, 200, 255];
          const dx = d.path[1][0] - d.path[0][0];
          const dy = d.path[1][1] - d.path[0][1];
          const speed = Math.sqrt(dx*dx + dy*dy);
          
          // Step size is 0.003. True MPH = speed / 0.003.
          const trueMph = speed / 0.003;
          
          if (trueMph >= 32) return [220, 20, 20];      // 32+ mph (High wind): Deep Red
          if (trueMph >= 25) return [255, 120, 20];     // 25-31 mph (Strong breeze): Orange
          if (trueMph >= 19) return [255, 220, 50];     // 19-24 mph (Fresh breeze): Yellow
          if (trueMph >= 13) return [50, 220, 100];     // 13-18 mph (Moderate breeze): Green
          return [100, 200, 255];                       // 1-12 mph (Calm/Gentle): Light Blue
        },
        opacity: 0.8,"""

content = re.sub(old_color_logic, new_color_logic, content, flags=re.DOTALL)

with open(path, "w") as f:
    f.write(content)
print("SUCCESS")
