"""
Tests for Celery Active Fire Scout: clustering, chord fanout, FireIncident linking,
and aggregate predictions.
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from harvester.firms_client import FireCluster
from harvester.tasks import (
    trigger_active_inference,
    run_async_inference,
    aggregate_active_predictions,
)
from predictions.models import FireIncident, PredictionPolygon


@pytest.mark.django_db
def test_trigger_active_inference_zero_fires():
    with patch("harvester.tasks.fetch_bay_area_hotspots", return_value=[]):
        res = trigger_active_inference.apply().result
        assert res["status"] == "success"
        assert res["fires_detected"] == 0


@pytest.mark.django_db
def test_trigger_active_inference_retries_on_error():
    import requests
    with patch("harvester.tasks.fetch_bay_area_hotspots", side_effect=requests.RequestException("FIRMS timeout")):
        with patch.object(trigger_active_inference, "retry", side_effect=Exception("TaskRetried")) as mock_retry:
            with pytest.raises(Exception, match="TaskRetried"):
                trigger_active_inference.apply(throw=True)
            mock_retry.assert_called_once()


@pytest.mark.django_db
def test_trigger_active_inference_clusters_and_dispatches():
    cluster1 = FireCluster(
        cluster_id=1,
        centroid_lat=37.5,
        centroid_lon=-122.1,
        count=3,
        bbox=[-122.38, 37.27, -121.82, 37.73],
        points=[{"latitude": 37.5, "longitude": -122.1, "confidence": "high"}]
    )
    cluster2 = FireCluster(
        cluster_id=2,
        centroid_lat=38.1,
        centroid_lon=-122.5,
        count=1,
        bbox=[-122.78, 37.87, -122.22, 38.33],
        points=[{"latitude": 38.1, "longitude": -122.5, "confidence": "nominal"}]
    )

    with patch("harvester.tasks.fetch_bay_area_hotspots", return_value=[cluster1, cluster2]), \
         patch("harvester.tasks.chord") as mock_chord:
        mock_chord_instance = MagicMock()
        mock_chord.return_value = mock_chord_instance

        res = trigger_active_inference.apply().result
        assert res["status"] == "success"
        assert res["fires_detected"] == 2

        # Verify chord was dispatched with 2 tasks
        mock_chord.assert_called_once()
        header_tasks = mock_chord.call_args[0][0]
        assert len(header_tasks) == 2

        # Verify FireIncident records were created
        incidents = FireIncident.objects.filter(is_active=True)
        assert incidents.count() == 2


@pytest.mark.django_db
def test_run_async_inference_payload_and_storage():
    mock_fc = {
        "type": "FeatureCollection",
        "metadata": {"timestamp": datetime.now(timezone.utc).isoformat(), "source_model": "ensemble"},
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [[[-122.1, 37.5], [-122.0, 37.5], [-122.0, 37.6], [-122.1, 37.6], [-122.1, 37.5]]]},
                "properties": {"grid_id": 99991, "fire_probability": 0.85, "horizon_hours": 1, "source_model": "ensemble"}
            }
        ]
    }
    incident = FireIncident.objects.create(name="Test Incident", start_time=datetime.now(timezone.utc), is_active=True)

    with patch("harvester.tasks.requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_fc
        mock_post.return_value = mock_resp

        res = run_async_inference.apply(args=([-122.3, 37.3, -121.9, 37.7], "ensemble", incident.id)).result
        assert res["type"] == "FeatureCollection"

        # Verify payload sent to ML Adapter
        sent_payload = mock_post.call_args[1]["json"]
        assert sent_payload["time_horizon"] == 6
        assert sent_payload["model_type"] == "ensemble"
        assert "date" in sent_payload
        assert sent_payload["date"] is not None

        # Verify PredictionPolygon created and linked to FireIncident
        polygon = PredictionPolygon.objects.filter(grid_id=99991).first()
        assert polygon is not None
        assert polygon.fire_incident_id == incident.id
        assert polygon.fire_probability == 0.85


def test_aggregate_active_predictions():
    fc1 = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "properties": {"grid_id": 1, "fire_probability": 0.8}}
        ]
    }
    fc2 = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "properties": {"grid_id": 2, "fire_probability": 0.5}}
        ]
    }

    with patch("harvester.tasks.cache.set") as mock_cache_set:
        res = aggregate_active_predictions.apply(args=([fc1, fc2],)).result
        assert res["status"] == "success"
        assert res["total_cells"] == 2
        mock_cache_set.assert_called_once()
        key = mock_cache_set.call_args[0][0]
        assert key == "ffwai:predictions:current"
