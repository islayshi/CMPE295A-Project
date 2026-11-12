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


def test_hotspots_telemetry_with_cached_list(api_client):
    """GET /api/telemetry/hotspots/ returns GeoJSON FeatureCollection when cached as raw point list."""
    mock_list = [
        {
            "latitude": 37.19,
            "longitude": -121.68,
            "frp": 18.0,
            "confidence": "high",
            "satellite": "VIIRS_NOAA20_NRT",
            "is_industrial_flare": False,
        }
    ]
    with patch("telemetry.views.cache.get", return_value=json.dumps(mock_list)):
        response = api_client.get("/api/telemetry/hotspots/")
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "FeatureCollection"
        assert len(data["features"]) == 1
        assert data["features"][0]["geometry"]["coordinates"] == [-121.68, 37.19]
        assert data["features"][0]["properties"]["frp"] == 18.0


@patch("harvester.tasks.trigger_daily_inference.delay")
def test_trigger_harvest_endpoint(mock_delay, api_client):
    """POST /api/telemetry/harvest/trigger/ queues daily inference task."""
    class DummyTask:
        id = "dummy-harvest-task-123"

    mock_delay.return_value = DummyTask()
    response = api_client.post("/api/telemetry/harvest/trigger/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "queued"
    assert data["task_id"] == "dummy-harvest-task-123"
    assert data["pipeline"] == "daily_harvest"
    mock_delay.assert_called_once()


@patch("harvester.tasks.trigger_active_inference.delay")
def test_trigger_scout_endpoint(mock_delay, api_client):
    """POST /api/telemetry/scout/trigger/ queues active fire scout task."""
    class DummyTask:
        id = "dummy-scout-task-456"

    mock_delay.return_value = DummyTask()
    response = api_client.post("/api/telemetry/scout/trigger/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "queued"
    assert data["task_id"] == "dummy-scout-task-456"
    assert data["pipeline"] == "firms_scout"
    mock_delay.assert_called_once()


def test_trigger_endpoints_method_not_allowed(api_client):
    """GET /api/telemetry/harvest/trigger/ returns 405 Method Not Allowed."""
    response = api_client.get("/api/telemetry/harvest/trigger/")
    assert response.status_code == 405
    response = api_client.get("/api/telemetry/scout/trigger/")
    assert response.status_code == 405
    response = api_client.get("/api/telemetry/aqi/trigger/")
    assert response.status_code == 405


@patch("harvester.tasks.fetch_aqi_data.delay")
def test_trigger_aqi_endpoint(mock_delay, api_client):
    """POST /api/telemetry/aqi/trigger/ queues AQI fetch task."""
    class DummyTask:
        id = "dummy-aqi-task-789"

    mock_delay.return_value = DummyTask()
    response = api_client.post("/api/telemetry/aqi/trigger/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "queued"
    assert data["task_id"] == "dummy-aqi-task-789"
    assert data["pipeline"] == "aqi_fetch"
    mock_delay.assert_called_once()


@patch("harvester.tasks.fetch_aqi_data.apply")
def test_aqi_data_cache_miss_self_heals(mock_apply, api_client):
    """GET /api/telemetry/aqi/ self-heals on cache miss by invoking fetch_aqi_data."""
    from django.core.cache import cache
    from telemetry.views import AQI_CACHE_KEY

    cache.delete(AQI_CACHE_KEY)

    def side_effect():
        cache.set(AQI_CACHE_KEY, json.dumps({
            "aqi": 35,
            "status": "Good",
            "pm25": 8.4,
            "sensors": [{"lat": 37.6688, "lon": -122.0808, "pm25": 8.4}]
        }), timeout=60 * 35)

    mock_apply.side_effect = side_effect

    response = api_client.get("/api/telemetry/aqi/")
    assert response.status_code == 200
    data = response.json()
    assert data["aqi"] == 35
    assert data["status"] == "Good"
    assert data["pm25"] == 8.4
    mock_apply.assert_called_once()




