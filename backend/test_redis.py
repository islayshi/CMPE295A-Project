import os
import django
import json

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from django.core.cache import cache
data = cache.get("ffwai:current_risk_map")
if data:
    parsed = json.loads(data)
    print("Found data! Features count:", len(parsed.get('features', [])))
else:
    print("NO DATA IN REDIS!")
