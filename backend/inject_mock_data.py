"""
inject_mock_data.py
-------------------
Re-populates the Redis cache with a 25-cell 1x1 km mock fire progression
centred on the East Bay Hills / Diablo Range (visible at the default map view:
lng=-122.08, lat=37.67, zoom=11).

Run from the backend/ directory:
    python inject_mock_data.py

Requires Redis on localhost:6379 (or REDIS_URL env var).
"""
import json
import os
import sys
import datetime

REDIS_URL = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0")
CACHE_KEY  = "ffwai:current_risk_map"
CACHE_TTL  = 86_400  # 24 h

CELL_DX    = 0.009   # ~1 km longitude
CELL_DY    = 0.009   # ~1 km latitude
ORIGIN_LNG = -122.22
ORIGIN_LAT =  37.620

# 25-cell 5x5 grid (col, row) -> fire_probability, 0=SW corner
FIRE_PROBS = {
    (4, 4): 0.93, (3, 4): 0.85, (4, 3): 0.82, (3, 3): 0.74,
    (2, 4): 0.67, (4, 2): 0.63, (2, 3): 0.58, (3, 2): 0.52,
    (1, 4): 0.44, (4, 1): 0.41, (1, 3): 0.37, (2, 2): 0.34,
    (3, 1): 0.29, (0, 4): 0.24, (1, 2): 0.21, (2, 1): 0.18,
    (4, 0): 0.15, (0, 3): 0.13, (3, 0): 0.11, (1, 1): 0.09,
    (2, 0): 0.08, (0, 2): 0.06, (1, 0): 0.04, (0, 1): 0.02,
    (0, 0): 0.01,
}

NOW = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def _risk_label(prob):
    if prob >= 0.80: return "CRITICAL"
    if prob >= 0.60: return "HIGH_RISK"
    if prob >= 0.35: return "ELEVATED"
    if prob >= 0.10: return "MODERATE"
    return "LOW"


def build_geojson():
    features = []
    cell_id = 3000
    for (col, row), prob in FIRE_PROBS.items():
        lng0, lat0 = ORIGIN_LNG + col * CELL_DX, ORIGIN_LAT + row * CELL_DY
        lng1, lat1 = lng0 + CELL_DX, lat0 + CELL_DY
        features.append({
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [
                [[lng0, lat0], [lng1, lat0], [lng1, lat1], [lng0, lat1], [lng0, lat0]]
            ]},
            "properties": {
                "grid_id": cell_id, "fire_probability": prob,
                "risk_label": _risk_label(prob), "source_model": "mock",
                "timestamp": NOW,
            },
        })
        cell_id += 1
    return {
        "type": "FeatureCollection",
        "metadata": {
            "timestamp": NOW, "source_model": "mock", "mock": True,
            "description": "25-cell 1x1 km mock fire progression -- East Bay Hills.",
            "grid_resolution_km": 1.0, "region": "San Francisco Bay Area, CA",
            "total_cells": len(features),
        },
        "features": features,
    }


def inject(geojson):
    payload = json.dumps(geojson)
    # Try raw redis-py
    try:
        import redis as redis_lib
        r = redis_lib.from_url(REDIS_URL, decode_responses=True)
        r.ping()
        r.set(CACHE_KEY, payload, ex=CACHE_TTL)
        print(f"[inject_mock_data] OK  {len(geojson['features'])} cells -> Redis {REDIS_URL!r} key={CACHE_KEY!r}")
        return True
    except Exception as exc:
        print(f"[inject_mock_data] redis-py failed ({exc}); trying Django cache...")
    # Fall back to Django cache layer
    try:
        import django
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
        bd = os.path.dirname(os.path.abspath(__file__))
        if bd not in sys.path: sys.path.insert(0, bd)
        django.setup()
        from django.core.cache import cache
        cache.set(CACHE_KEY, geojson, CACHE_TTL)
        print(f"[inject_mock_data] OK  {len(geojson['features'])} cells -> Django cache key={CACHE_KEY!r}")
        return True
    except Exception as exc2:
        print(f"[inject_mock_data] FAIL  {exc2}")
        return False


if __name__ == "__main__":
    ok = inject(build_geojson())
    sys.exit(0 if ok else 1)
