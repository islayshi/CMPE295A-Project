"""
Unit & Integration Tests for FastAPI ML Adapter.
Verifies mock mode, live dispatch to U-Net and PINN, ensemble blending, and health probing.
"""
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from ml_adapter.main import app

client = TestClient(app)

SAMPLE_UNET_FC = {
    "type": "FeatureCollection",
    "metadata": {
        "timestamp": "2026-10-23T12:00:00Z",
        "source_model": "unet",
        "model_version": "unet-v1.0",
        "grid_resolution_km": 1.0,
        "total_cells": 2,
    },
    "features": [
        {
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [[[-122.2, 37.1], [-122.1, 37.1], [-122.1, 37.2], [-122.2, 37.2], [-122.2, 37.1]]]},
            "properties": {
                "grid_id": 1001,
                "fire_probability": 0.8,
                "horizon_hours": 1,
                "risk_label": "HIGH_RISK",
                "source_model": "unet",
                "members": 1,
            },
        },
        {
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [[[-122.1, 37.1], [-122.0, 37.1], [-122.0, 37.2], [-122.1, 37.2], [-122.1, 37.1]]]},
            "properties": {
                "grid_id": 1002,
                "fire_probability": 0.5,
                "horizon_hours": 1,
                "risk_label": "MODERATE_RISK",
                "source_model": "unet",
                "members": 1,
            },
        },
    ],
}

SAMPLE_PINN_FC = {
    "type": "FeatureCollection",
    "metadata": {
        "timestamp": "2026-10-23T12:00:00Z",
        "source_model": "pinn",
        "model_version": "pinn-0.3.1",
        "grid_resolution_km": 1.0,
        "total_cells": 2,
    },
    "features": [
        {
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [[[-122.2, 37.1], [-122.1, 37.1], [-122.1, 37.2], [-122.2, 37.2], [-122.2, 37.1]]]},
            "properties": {
                "grid_id": 1001,
                "fire_probability": 0.6,
                "horizon_hours": 1,
                "risk_label": "HIGH_RISK",
                "source_model": "pinn",
                "members": 1,
            },
        },
        {
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [[[-122.0, 37.1], [-121.9, 37.1], [-121.9, 37.2], [-122.0, 37.2], [-122.0, 37.1]]]},
            "properties": {
                "grid_id": 1003,
                "fire_probability": 0.4,
                "horizon_hours": 1,
                "risk_label": "MODERATE_RISK",
                "source_model": "pinn",
                "members": 1,
            },
        },
    ],
}


def test_health_mock_mode():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "mock" in data


@patch("ml_adapter.main.probe_services_health", new_callable=AsyncMock)
def test_health_live_mode(mock_probe):
    mock_probe.return_value = {
        "unet": {"status": "ok", "url": "http://localhost:8081"},
        "pinn": {"status": "ok", "url": "http://localhost:8082"},
    }
    with patch("ml_adapter.main.MOCK_INFERENCE", False):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["mock"] is False
        assert data["models_loaded"] is True
        assert "downstream_services" in data
        assert data["downstream_services"]["unet"]["status"] == "ok"


def test_predict_progression_mock():
    payload = {
        "bbox": [-122.9, 36.9, -121.5, 38.3],
        "time_horizon": 24,
        "model_type": "unet",
        "mock": True,
    }
    response = client.post("/predict/progression", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "FeatureCollection"
    assert "metadata" in data
    assert data["metadata"]["mock"] is True
    assert any(f.get("properties", {}).get("horizon_hours") == 24 for f in data["features"])


def test_predict_progression_mock_pinn():
    payload = {
        "bbox": [-122.9, 36.9, -121.5, 38.3],
        "time_horizon": 24,
        "model_type": "pinn",
        "mock": True,
    }
    response = client.post("/predict/progression", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) > 0
    assert data["metadata"]["source_model"] == "pinn"
    assert all(f.get("properties", {}).get("source_model") == "pinn" for f in data["features"])


@patch("ml_adapter.main.call_unet", new_callable=AsyncMock)
def test_predict_progression_unet_live(mock_call_unet):
    mock_call_unet.return_value = SAMPLE_UNET_FC
    with patch("ml_adapter.main.MOCK_INFERENCE", False):
        payload = {
            "bbox": [-122.9, 36.9, -121.5, 38.3],
            "time_horizon": 3,
            "model_type": "unet",
            "date": "2026-10-23",
            "mock": False,
        }
        response = client.post("/predict/progression", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "FeatureCollection"
        assert len(data["features"]) == 2
        assert data["features"][0]["properties"]["source_model"] == "unet"
        mock_call_unet.assert_awaited_once_with(
            bbox=(-122.9, 36.9, -121.5, 38.3),
            time_horizon=3,
            date="2026-10-23",
        )


@patch("ml_adapter.main.call_pinn", new_callable=AsyncMock)
def test_predict_progression_pinn_live(mock_call_pinn):
    mock_call_pinn.return_value = SAMPLE_PINN_FC
    with patch("ml_adapter.main.MOCK_INFERENCE", False):
        payload = {
            "bbox": [-122.9, 36.9, -121.5, 38.3],
            "time_horizon": 3,
            "model_type": "pinn",
            "date": "2026-10-23",
            "mock": False,
        }
        response = client.post("/predict/progression", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "FeatureCollection"
        assert len(data["features"]) == 2
        assert data["features"][0]["properties"]["source_model"] == "pinn"
        mock_call_pinn.assert_awaited_once_with(
            bbox=(-122.9, 36.9, -121.5, 38.3),
            time_horizon=3,
            date="2026-10-23",
        )


@patch("ml_adapter.main.call_pinn", new_callable=AsyncMock)
@patch("ml_adapter.main.call_unet", new_callable=AsyncMock)
def test_predict_ensemble_live_blending(mock_call_unet, mock_call_pinn):
    mock_call_unet.return_value = SAMPLE_UNET_FC
    mock_call_pinn.return_value = SAMPLE_PINN_FC
    with patch("ml_adapter.main.MOCK_INFERENCE", False):
        payload = {
            "bbox": [-122.9, 36.9, -121.5, 38.3],
            "time_horizon": 3,
            "model_type": "ensemble",
            "date": "2026-10-23",
            "mock": False,
        }
        response = client.post("/predict/ensemble", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "FeatureCollection"
        assert data["metadata"]["source_model"] == "ensemble"
        assert data["metadata"]["w_unet"] == 0.6
        assert data["metadata"]["w_pinn"] == 0.4

        features_by_id = {f["properties"]["grid_id"]: f["properties"] for f in data["features"]}
        assert set(features_by_id.keys()) == {1001, 1002, 1003}

        # Cell 1001 (overlapping): 0.6 * 0.8 + 0.4 * 0.6 = 0.48 + 0.24 = 0.72
        assert round(features_by_id[1001]["fire_probability"], 4) == 0.72
        assert features_by_id[1001]["members"] == 2
        assert features_by_id[1001]["w_unet"] == 0.6

        # Cell 1002 (U-Net only): 0.6 * 0.5 = 0.3
        assert round(features_by_id[1002]["fire_probability"], 4) == 0.3
        assert features_by_id[1002]["members"] == 1

        # Cell 1003 (PINN only): 0.4 * 0.4 = 0.16
        assert round(features_by_id[1003]["fire_probability"], 4) == 0.16
        assert features_by_id[1003]["members"] == 1


@patch("ml_adapter.main.call_pinn", new_callable=AsyncMock)
@patch("ml_adapter.main.call_unet", new_callable=AsyncMock)
def test_predict_ensemble_graceful_degradation(mock_call_unet, mock_call_pinn):
    mock_call_unet.return_value = SAMPLE_UNET_FC
    mock_call_pinn.side_effect = Exception("PINN service connection refused")
    with patch("ml_adapter.main.MOCK_INFERENCE", False):
        payload = {
            "bbox": [-122.9, 36.9, -121.5, 38.3],
            "time_horizon": 3,
            "model_type": "ensemble",
            "mock": False,
        }
        response = client.post("/predict/ensemble", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "FeatureCollection"
        assert len(data["features"]) == 2
        assert "pinn_error" in data["metadata"].get("ensemble_notes", "").lower()


def test_serve_mock_fixture_spatial_colocation():
    """
    Verifies that _serve_mock_fixture translates polygon coordinates
    according to (delta_lon, delta_lat) when target_bbox is provided.
    """
    # Target center: (-122.0, 37.25)
    # Ref center: (-122.15, 37.05)
    # delta_lon: +0.15, delta_lat: +0.20
    target_bbox = [-122.05, 37.20, -121.95, 37.30]
    payload = {
        "bbox": target_bbox,
        "time_horizon": 24,
        "model_type": "ensemble",
        "mock": True,
    }
    response = client.post("/predict/progression", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "FeatureCollection"
    assert "spatial_colocation" in data["metadata"]
    assert data["metadata"]["spatial_colocation"]["delta"] == [0.15, 0.2]

    # Verify translated coordinates
    coords = data["features"][0]["geometry"]["coordinates"][0]
    # In base fixture (current_fire_goes18), first ring coord is [-122.15, 37.05]
    # Translated: [-122.15 + 0.15, 37.05 + 0.20] = [-122.0, 37.25]
    assert round(coords[0][0], 2) == -122.00
    assert round(coords[0][1], 2) == 37.25


@patch("ml_adapter.main.call_unet", new_callable=AsyncMock)
def test_predict_progression_unet_live_with_seed_points(mock_call_unet):
    """
    Verifies that seed_points in PredictionRequest are forwarded to call_unet.
    """
    mock_call_unet.return_value = SAMPLE_UNET_FC
    with patch("ml_adapter.main.MOCK_INFERENCE", False):
        payload = {
            "bbox": [-122.25, 37.05, -121.65, 37.35],
            "time_horizon": 6,
            "model_type": "unet",
            "mock": False,
            "seed_points": [[-122.05, 37.20], [-121.72, 37.17]],
        }
        response = client.post("/predict/progression", json=payload)
        assert response.status_code == 200
        mock_call_unet.assert_awaited_once_with(
            bbox=(-122.25, 37.05, -121.65, 37.35),
            time_horizon=6,
            date=None,
            seed_points=[[-122.05, 37.2], [-121.72, 37.17]],
        )


@patch("ml_adapter.main.call_pinn", new_callable=AsyncMock)
@patch("ml_adapter.main.call_unet", new_callable=AsyncMock)
def test_predict_ensemble_live_with_seed_points(mock_call_unet, mock_call_pinn):
    """
    Verifies that seed_points in PredictionRequest are forwarded to both call_unet and call_pinn
    when requesting ensemble prediction.
    """
    mock_call_unet.return_value = SAMPLE_UNET_FC
    mock_call_pinn.return_value = SAMPLE_PINN_FC
    with patch("ml_adapter.main.MOCK_INFERENCE", False):
        payload = {
            "bbox": [-122.25, 37.05, -121.65, 37.35],
            "time_horizon": 6,
            "model_type": "ensemble",
            "mock": False,
            "seed_points": [[-122.05, 37.20], [-121.72, 37.17]],
        }
        response = client.post("/predict/ensemble", json=payload)
        assert response.status_code == 200
        mock_call_unet.assert_awaited_once_with(
            bbox=(-122.25, 37.05, -121.65, 37.35),
            time_horizon=6,
            date=None,
            seed_points=[[-122.05, 37.2], [-121.72, 37.17]],
        )
        mock_call_pinn.assert_awaited_once_with(
            bbox=(-122.25, 37.05, -121.65, 37.35),
            time_horizon=6,
            date=None,
            seed_points=[[-122.05, 37.2], [-121.72, 37.17]],
        )


def test_serve_mock_fixture_deterministic_grid_id_offset():
    """
    Verifies that _serve_mock_fixture produces identical, deterministic grid_ids
    for repeated requests with the same target_bbox.
    """
    target_bbox = [-122.05, 37.20, -121.95, 37.30]
    payload = {
        "bbox": target_bbox,
        "time_horizon": 24,
        "model_type": "ensemble",
        "mock": True,
    }
    r1 = client.post("/predict/progression", json=payload).json()
    r2 = client.post("/predict/progression", json=payload).json()
    ids1 = [f["properties"]["grid_id"] for f in r1["features"]]
    ids2 = [f["properties"]["grid_id"] for f in r2["features"]]
    assert ids1 == ids2


