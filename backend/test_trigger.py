import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from harvester.tasks import trigger_daily_inference
try:
    trigger_daily_inference()
except Exception as e:
    print(f"FAILED WITH EXCEPTION: {type(e).__name__}: {e}")
