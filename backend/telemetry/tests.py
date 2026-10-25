import json
from unittest.mock import patch
import pytest
from rest_framework.test import APIClient

FIRMS_HOTSPOTS_CACHE_KEY = "ffwai:telemetry:firms_hotspots"


@pytest.fixture
def api_client():
    return APIClient()


def test_hotspots_telemetry_empty_cache(api_client):
    """GET /api/telemetry/hotspots/ returns empty FeatureCollection when cache is empty."""
    with patch("telemetry.views.cache.get", return_value=None):
        response = api_client.get("/api/telemetry/hotspots/")
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "FeatureCollection"
        assert data["features"] == []


def test_hotspots_telemetry_with_cached_data(api_client):
    """GET /api/telemetry/hotspots/ returns GeoJSON FeatureCollection of Point features when cached."""
    mock_fc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [-121.70, 37.20],
                },
                "properties": {
                    "latitude": 37.20,
                    "longitude": -121.70,
                    "frp": 14.5,
                    "confidence": "high",
                    "satellite": "Suomi-NPP",
                    "is_industrial_flare": False,
                    "flare_site_name": None,
                },
            },
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [-121.9323, 37.4557],
                },
                "properties": {
                    "latitude": 37.4557,
                    "longitude": -121.9323,
                    "frp": 22.0,
                    "confidence": "high",
                    "satellite": "NOAA-21",
                    "is_industrial_flare": True,
                    "flare_site_name": "Alviso Landfill",
                },
            },
        ],
    }
    with patch("telemetry.views.cache.get", return_value=json.dumps(mock_fc)):
        response = api_client.get("/api/telemetry/hotspots/")
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "FeatureCollection"
        assert len(data["features"]) == 2
        assert data["features"][0]["geometry"]["coordinates"] == [-121.70, 37.20]
        assert data["features"][0]["properties"]["satellite"] == "Suomi-NPP"
        assert data["features"][0]["properties"]["is_industrial_flare"] is False
        assert data["features"][1]["properties"]["is_industrial_flare"] is True
        assert data["features"][1]["properties"]["flare_site_name"] == "Alviso Landfill"


def test_hotspots_telemetry_corrupt_cache(api_client):
    """GET /api/telemetry/hotspots/ gracefully handles corrupted cache payloads without 500."""
    with patch("telemetry.views.cache.get", return_value="corrupted json {["):
        response = api_client.get("/api/telemetry/hotspots/")
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "FeatureCollection"
        assert data["features"] == []


