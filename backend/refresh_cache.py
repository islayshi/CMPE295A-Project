import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from harvester.tasks import fetch_wind_data, fetch_nws_alerts, trigger_daily_inference

print("Re-populating Wind Data...")
try:
    fetch_wind_data()
except Exception as e:
    print(f"Failed to fetch wind data: {e}")

print("Re-populating NWS Alerts...")
try:
    fetch_nws_alerts()
except Exception as e:
    print(f"Failed to fetch NWS alerts: {e}")

print("Re-populating Predictions...")
# This will use the mock inference locally to regenerate the heatmaps
trigger_daily_inference()

print("Cache refresh complete.")
