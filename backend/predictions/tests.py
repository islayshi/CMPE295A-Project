import pytest
from rest_framework.test import APIClient
from django.contrib.gis.geos import Polygon, Point
from grid.models import BayAreaGrid
from predictions.models import PredictionPolygon
from django.utils import timezone
import datetime

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def prediction_data():
    # Create two grid cells, one at (10, 10), another at (20, 20)
    poly1 = Polygon(((9, 9), (9, 11), (11, 11), (11, 9), (9, 9)), srid=4326)
    grid1 = BayAreaGrid.objects.create(id=1, geometry=poly1, centroid=Point(10, 10, srid=4326), row=0, col=0)
    
    poly2 = Polygon(((19, 19), (19, 21), (21, 21), (21, 19), (19, 19)), srid=4326)
    grid2 = BayAreaGrid.objects.create(id=2, geometry=poly2, centroid=Point(20, 20, srid=4326), row=0, col=1)

    ts = timezone.now()
    PredictionPolygon.objects.create(
        grid=grid1,
        timestamp=ts,
        source_model="mock",
        fire_probability=0.8
    )
    PredictionPolygon.objects.create(
        grid=grid2,
        timestamp=ts,
        source_model="mock",
        fire_probability=0.2
    )
    return ts

import json
from django.core.cache import cache

@pytest.fixture
def cached_prediction_data():
    feature_collection = {
        "type": "FeatureCollection",
        "metadata": {"timestamp": "2026-10-04T00:00:00Z", "total_cells": 2},
        "features": [
            {
                "type": "Feature",
                "properties": {"grid_id": 1, "fire_probability": 0.8},
                "geometry": {"type": "Polygon", "coordinates": [[[0,0],[0,1],[1,1],[1,0],[0,0]]]}
            },
            {
                "type": "Feature",
                "properties": {"grid_id": 2, "fire_probability": 0.2},
                "geometry": {"type": "Polygon", "coordinates": [[[1,1],[1,2],[2,2],[2,1],[1,1]]]}
            }
        ]
    }
    return feature_collection

from unittest.mock import patch

def test_current_predictions_from_cache(api_client, cached_prediction_data):
    """
    Verifies that the current_predictions endpoint fetches data from Redis cache
    in O(1) time instead of querying the database.
    """
    with patch("predictions.views.cache.get") as mock_cache_get:
        mock_cache_get.return_value = json.dumps(cached_prediction_data)
        response = api_client.get("/api/predictions/current/")
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "FeatureCollection"
        assert len(data["features"]) == 2
        assert data["features"][0]["properties"]["grid_id"] == 1
        assert data["features"][1]["properties"]["grid_id"] == 2
        mock_cache_get.assert_called_once_with("ffwai:predictions:current")

@pytest.mark.django_db
def test_current_predictions_empty_cache(api_client, prediction_data):
    """
    Verifies that when the cache is empty, the endpoint gracefully falls back
    to querying the database for the latest predictions.
    """
    with patch("predictions.views.cache.get") as mock_cache_get:
        mock_cache_get.return_value = None
        response = api_client.get("/api/predictions/current/")
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "FeatureCollection"
        assert len(data["features"]) == 2
        mock_cache_get.assert_called_once_with("ffwai:predictions:current")


def test_current_predictions_model_scoped_cache_keys(api_client, cached_prediction_data):
    """
    Verifies that model query parameter selects model-scoped Redis cache keys.
    """
    with patch("predictions.views.cache.get") as mock_cache_get:
        mock_cache_get.return_value = json.dumps(cached_prediction_data)

        # Default / ensemble (no model param)
        api_client.get("/api/predictions/current/")
        mock_cache_get.assert_called_with("ffwai:predictions:current")

        # Explicit ensemble
        api_client.get("/api/predictions/current/?model=ensemble")
        mock_cache_get.assert_called_with("ffwai:predictions:current:ensemble")

        # U-Net
        api_client.get("/api/predictions/current/?model=unet")
        mock_cache_get.assert_called_with("ffwai:predictions:current:unet")

        # PINN
        api_client.get("/api/predictions/current/?model=pinn")
        mock_cache_get.assert_called_with("ffwai:predictions:current:pinn")


@pytest.mark.django_db
def test_store_geojson_result_populates_ensemble_cache(cached_prediction_data):
    """
    Verifies that store_geojson_result populates both ffwai:predictions:current
    and ffwai:predictions:current:ensemble when source_model='ensemble'.
    """
    from harvester.tasks import store_geojson_result
    data = dict(cached_prediction_data)
    data["metadata"]["source_model"] = "ensemble"
    for f in data["features"]:
        f["properties"]["source_model"] = "ensemble"
        f["properties"]["horizon_hours"] = 1

    with patch("harvester.tasks.cache.set") as mock_cache_set:
        store_geojson_result(data)
        keys_set = [call[0][0] for call in mock_cache_set.call_args_list]
        assert "ffwai:predictions:current" in keys_set
        assert "ffwai:predictions:current:ensemble" in keys_set


def test_current_predictions_horizon_filtering(api_client):
    """
    Verifies that passing ?horizon=X filters features by horizon_hours.
    """
    multi_horizon_fc = {
        "type": "FeatureCollection",
        "metadata": {"timestamp": "2026-10-04T00:00:00Z"},
        "features": [
            {
                "type": "Feature",
                "properties": {"grid_id": 1, "fire_probability": 0.8, "horizon_hours": 1},
                "geometry": {"type": "Polygon", "coordinates": [[[0,0],[0,1],[1,1],[1,0],[0,0]]]}
            },
            {
                "type": "Feature",
                "properties": {"grid_id": 2, "fire_probability": 0.5, "horizon_hours": 6},
                "geometry": {"type": "Polygon", "coordinates": [[[1,1],[1,2],[2,2],[2,1],[1,1]]]}
            }
        ]
    }
    with patch("predictions.views.cache.get", return_value=json.dumps(multi_horizon_fc)):
        response = api_client.get("/api/predictions/current/?horizon=6")
        assert response.status_code == 200
        data = response.json()
        assert len(data["features"]) == 1
        assert data["features"][0]["properties"]["horizon_hours"] == 6


@pytest.mark.django_db
def test_current_predictions_db_fallback_by_model(api_client):
    """
    Verifies that DB fallback filters by source_model when specified.
    """
    from predictions.models import FireIncident

    poly1 = Polygon(((9, 9), (9, 11), (11, 11), (11, 9), (9, 9)), srid=4326)
    grid1 = BayAreaGrid.objects.create(id=201, geometry=poly1, centroid=Point(10, 10, srid=4326), row=0, col=0)
    poly2 = Polygon(((19, 19), (19, 21), (21, 21), (21, 19), (19, 19)), srid=4326)
    grid2 = BayAreaGrid.objects.create(id=202, geometry=poly2, centroid=Point(20, 20, srid=4326), row=0, col=1)

    now = timezone.now()
    inc = FireIncident.objects.create(name="Model Filter Test Fire", start_time=now, is_active=True)

    PredictionPolygon.objects.create(grid=grid1, fire_incident=inc, timestamp=now, source_model="unet", fire_probability=0.8, lead_time_hours=1)
    PredictionPolygon.objects.create(grid=grid2, fire_incident=inc, timestamp=now, source_model="pinn", fire_probability=0.6, lead_time_hours=1)

    with patch("predictions.views.cache.get", return_value=None):
        resp_unet = api_client.get("/api/predictions/current/?model=unet")
        assert resp_unet.status_code == 200
        data_unet = resp_unet.json()
        assert len(data_unet["features"]) == 1
        assert data_unet["features"][0]["properties"]["source_model"] == "unet"

        resp_pinn = api_client.get("/api/predictions/current/?model=pinn")
        assert resp_pinn.status_code == 200
        data_pinn = resp_pinn.json()
        assert len(data_pinn["features"]) == 1
        assert data_pinn["features"][0]["properties"]["source_model"] == "pinn"


@pytest.mark.django_db
def test_current_predictions_falls_back_when_cache_has_empty_features(api_client, prediction_data):
    """
    Verifies that when Redis cache contains a FeatureCollection with empty features ([]),
    the current_predictions endpoint falls back to active PostGIS PredictionPolygon records.
    """
    empty_fc = {
        "type": "FeatureCollection",
        "metadata": {"total_cells": 0, "timestamp": "2026-10-26T00:00:00Z"},
        "features": [],
    }
    with patch("predictions.views.cache.get", return_value=json.dumps(empty_fc)):
        response = api_client.get("/api/predictions/current/")
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "FeatureCollection"
        assert len(data["features"]) == 2


@pytest.mark.django_db
def test_current_predictions_falls_back_when_cache_returns_dict_with_empty_features(api_client, prediction_data):
    """
    Verifies that when Redis cache returns a Python dict with empty features (e.g. LocMemCache),
    the endpoint falls back to active PostGIS PredictionPolygon records without TypeError.
    """
    empty_fc = {
        "type": "FeatureCollection",
        "metadata": {"total_cells": 0, "timestamp": "2026-10-26T00:00:00Z"},
        "features": [],
    }
    with patch("predictions.views.cache.get", return_value=empty_fc):
        response = api_client.get("/api/predictions/current/")
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "FeatureCollection"
        assert len(data["features"]) == 2


@pytest.mark.django_db
def test_current_predictions_horizon_filter_robustness(api_client, prediction_data):
    """
    Verifies that the horizon filter handles integer, float, and string representations
    correctly when filtering GeoJSON features.
    """
    cached_fc = {
        "type": "FeatureCollection",
        "metadata": {"total_cells": 3},
        "features": [
            {"type": "Feature", "properties": {"grid_id": 1, "horizon_hours": 1}},
            {"type": "Feature", "properties": {"grid_id": 2, "lead_time_hours": "1"}},
            {"type": "Feature", "properties": {"grid_id": 3, "horizon_hours": 3}},
        ],
    }
    with patch("predictions.views.cache.get", return_value=json.dumps(cached_fc)):
        response = api_client.get("/api/predictions/current/?horizon=1")
        assert response.status_code == 200
        data = response.json()
        assert len(data["features"]) == 2
        assert {f["properties"]["grid_id"] for f in data["features"]} == {1, 2}


@pytest.mark.django_db
def test_current_predictions_bidirectional_cache_sync_on_fallback(api_client, prediction_data):
    """
    Verifies that when current_predictions falls back to PostGIS, it populates both
    ffwai:predictions:current and ffwai:predictions:current:ensemble.
    """
    cached_writes = {}

    def fake_cache_set(key, val, timeout=None):
        cached_writes[key] = val

    with patch("predictions.views.cache.get", return_value=None), \
         patch("predictions.views.cache.set", side_effect=fake_cache_set):
        response = api_client.get("/api/predictions/current/?model=ensemble")
        assert response.status_code == 200
        assert "ffwai:predictions:current:ensemble" in cached_writes
        assert "ffwai:predictions:current" in cached_writes



