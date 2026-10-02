import json
import math

def generate_polygon(center_lon, center_lat, radius_deg, num_points=12):
    coords = []
    for i in range(num_points):
        angle = (2 * math.pi * i) / num_points
        lon = center_lon + radius_deg * math.cos(angle)
        lat = center_lat + radius_deg * math.sin(angle)
        coords.append([lon, lat])
    coords.append(coords[0]) # close polygon
    return coords

# Santa Cruz / Bonny Doon roughly
cx, cy = -122.15, 37.05

features = []

# Center Core
features.append({
    "type": "Feature",
    "geometry": {
        "type": "Polygon",
        "coordinates": [generate_polygon(cx, cy, 0.02, 16)]
    },
    "properties": {
        "grid_id": 2001,
        "fire_probability": 0.95,
        "risk_label": "HIGH_RISK",
        "source_model": "mock",
        "spread_hour": 0
    }
})

# Inner Perimeter
features.append({
    "type": "Feature",
    "geometry": {
        "type": "Polygon",
        "coordinates": [generate_polygon(cx, cy, 0.05, 16)]
    },
    "properties": {
        "grid_id": 2002,
        "fire_probability": 0.65,
        "risk_label": "MEDIUM_RISK",
        "source_model": "mock",
        "spread_hour": 12
    }
})

# Outer Perimeter
features.append({
    "type": "Feature",
    "geometry": {
        "type": "Polygon",
        "coordinates": [generate_polygon(cx, cy, 0.08, 16)]
    },
    "properties": {
        "grid_id": 2003,
        "fire_probability": 0.35,
        "risk_label": "LOW_RISK",
        "source_model": "mock",
        "spread_hour": 24
    }
})

geojson = {
  "type": "FeatureCollection",
  "metadata": {
    "timestamp": "2026-09-23T06:00:00Z",
    "source_model": "mock",
    "mock": True,
    "description": "CZU Lightning Complex fire area — Santa Cruz Mountains (August 2020). Layered.",
    "grid_resolution_km": 0.5,
    "region": "San Francisco Bay Area, CA",
    "total_cells": 3
  },
  "features": features
}

with open("/Users/earlpadron/Desktop/Spring 2026 Courses/CMPE 295A/CMPE295A-Project/ml_adapter/fixtures/bay_area_fixture.json", "w") as f:
    json.dump(geojson, f, indent=2)
