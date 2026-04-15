"""
pyrecast_test.py
Pulls real Pyrecast outputs directly from data.pyrecast.org
No API key, no login required.
"""

import requests
import csv
import json
from datetime import datetime, timezone

BASE = "https://data.pyrecast.org"

# ── 1. ACTIVE FIRE DETECTIONS ──────────────────────────────────────────────
# The simplest endpoint — a plain CSV updated every ~8 minutes
print("=" * 55)
print("PYRECAST — Live Active Fire Detections")
print("=" * 55)

resp = requests.get(f"{BASE}/fire_detections/active-fires/active-fires.csv", timeout=15)
resp.raise_for_status()

lines = resp.text.strip().splitlines()
reader = csv.DictReader(lines)
fires = list(reader)

print(f"\nTotal active fires detected: {len(fires)}")
print(f"Fields available: {list(fires[0].keys()) if fires else 'none'}\n")

for f in fires[:5]:  # show first 5
    print(f"  {f}")

# Save it
with open("pyrecast_active_fires.csv", "w", newline="") as out:
    out.write(resp.text)
print("\nSaved to pyrecast_active_fires.csv")


# ── 2. DISCOVER LATEST RISK FORECAST ──────────────────────────────────────
# Walk the directory listing to find the most recent forecast run
print("\n" + "=" * 55)
print("PYRECAST — Latest Risk Forecast Files")
print("=" * 55)

index_resp = requests.get(f"{BASE}/fire_risk_forecast/all/", timeout=15)
# Parse the directory listing — folder names are like 20260407_12
folders = []
for line in index_resp.text.splitlines():
    # Look for date-formatted folder names
    import re
    match = re.search(r'(\d{8}_\d{2})/', line)
    if match:
        folders.append(match.group(1))

if folders:
    latest = sorted(folders)[-1]
    date_str = latest[:8]
    hour_str = latest[9:]
    forecast_dt = datetime.strptime(f"{date_str} {hour_str}:00", "%Y%m%d %H:%M")
    print(f"\nLatest forecast run: {forecast_dt.strftime('%Y-%m-%d %H:%M UTC')}")

    # List available GeoTIFF files for this run
    tif_url = f"{BASE}/fire_risk_forecast/all/{latest}/elmfire/landfire/"
    tif_resp = requests.get(tif_url, timeout=15)
    tif_files = re.findall(r'([\w\-]+\.tif)', tif_resp.text)
    unique_tifs = sorted(set(tif_files))

    print(f"Available output types (GeoTIFF rasters, one per hour):")
    # Show unique file type prefixes
    prefixes = sorted(set(f.split("_")[0] for f in unique_tifs))
    for p in prefixes:
        count = sum(1 for f in unique_tifs if f.startswith(p))
        print(f"  {p}  ({count} hourly files)")

    # Show the first file URL so you know exactly what's there
    if unique_tifs:
        example = unique_tifs[0]
        print(f"\nExample file URL:")
        print(f"  {tif_url}{example}")
        print(f"  (download with: requests.get(that_url) -> open rasterio or GDAL)")


# ── 3. SUMMARY ─────────────────────────────────────────────────────────────
summary = {
    "fetched_at": datetime.now(timezone.utc).isoformat(),
    "active_fires_count": len(fires),
    "active_fires_sample": fires[:3],
    "latest_forecast_run": latest if folders else None,
    "forecast_output_types": prefixes if folders else [],
    "note": (
        "GeoTIFF rasters require rasterio to read pixel values. "
        "active-fires.csv is immediately usable as-is."
    )
}

with open("pyrecast_results.json", "w") as f:
    json.dump(summary, f, indent=2)

print("\n" + "=" * 55)
print("Saved summary to pyrecast_results.json")
print("=" * 55)