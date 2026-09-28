import sys

path = "backend/harvester/tasks.py"
with open(path, "r") as f:
    content = f.read()

# Replace the requests.get loop to add a small delay and increase timeout
old_loop = """            for lon in lons:
                url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=wind_speed_10m,wind_direction_10m&wind_speed_unit=mph"
                res = requests.get(url, timeout=10)"""

new_loop = """            import time
            for lon in lons:
                url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=wind_speed_10m,wind_direction_10m&wind_speed_unit=mph"
                try:
                    res = requests.get(url, timeout=20)
                except Exception:
                    time.sleep(1)
                    res = requests.get(url, timeout=20)
                time.sleep(0.2) # Avoid Open-Meteo throttling"""

if old_loop in content:
    content = content.replace(old_loop, new_loop)
    with open(path, "w") as f:
        f.write(content)
    print("SUCCESS")
else:
    print("FAILED TO FIND LOOP")
