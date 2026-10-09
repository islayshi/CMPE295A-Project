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

