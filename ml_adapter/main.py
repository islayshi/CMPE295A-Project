"""
FastAPI ML Adapter — Fight Fire With AI
========================================
Isolated translation layer between the Django/Celery backend and the
ML models hosted on Vertex AI.

Month 1 behaviour (MOCK_INFERENCE=true):
  - POST /predict/progression returns bay_area_fixture.json directly.
  - No Vertex AI calls are made.

Month 2 behaviour (MOCK_INFERENCE=false):
  - POST /predict/progression invokes the trained U-Net, PINN, and RL
    Agent endpoints on Vertex AI and returns the combined GeoJSON.

Design Doc §1.1 FastAPI ML Adapter, §8.B, §14 ML Integration Contract.
FR-E09: Mock mode required for Month 1 development and CI/CD.
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ml_adapter.services_client import (
    call_unet,
    call_pinn,
    combine_ensemble_features,
    probe_services_health,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App initialisation
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Fight Fire With AI — ML Adapter",
    description=(
        "Translates harvested feature data into fire risk GeoJSON predictions. "
        "Calls Vertex AI model endpoints in production; returns a static Bay Area "
        "fixture when MOCK_INFERENCE=true."
    ),
    version="1.0.0",
)

MOCK_INFERENCE: bool = os.getenv("MOCK_INFERENCE", "true").lower() == "true"

FIXTURE_DIR: Path = Path(__file__).parent / "fixtures/frontend_team_geojson_files"


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class PredictionRequest(BaseModel):
    """
    Payload sent by the Django Celery harvester.

    In Month 1, only `bbox`, `time_horizon`, `model_type`, `date` and `mock` are used.
    In Month 2, features will be fetched or processed based on the spatial bounds.
    """
    bbox: tuple[float, float, float, float] = (-122.9, 36.9, -121.5, 38.3)
    time_horizon: int = 24
    model_type: str = "unet"
    date: str | None = None
    mock: bool = True


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health() -> dict:
    """
    GET /health

    Returns the operational status of the ML Adapter.
    Consumed by Django's GET /api/health/ endpoint (NFR-O02).
    """
    res = {
        "status": "ok",
        "mock": MOCK_INFERENCE,
        "models_loaded": not MOCK_INFERENCE,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if not MOCK_INFERENCE:
        res["downstream_services"] = await probe_services_health()
    return res


@app.post("/predict/progression")
async def predict_progression(request: PredictionRequest) -> JSONResponse:
    """
    POST /predict/progression

    Month 1 (MOCK_INFERENCE=true):
      Reads and normalizes the mock GeoJSONs.

    Month 2 (MOCK_INFERENCE=false):
      Dispatches prediction requests to downstream inference services (U-Net, PINN, or Ensemble).
    """
    if MOCK_INFERENCE or request.mock:
        return _serve_mock_fixture(model_type=request.model_type)

    try:
        if request.model_type == 'unet':
            geojson = await call_unet(
                bbox=request.bbox,
                time_horizon=request.time_horizon,
                date=request.date,
            )
            return JSONResponse(content=geojson)
        elif request.model_type == 'pinn':
            geojson = await call_pinn(
                bbox=request.bbox,
                time_horizon=request.time_horizon,
                date=request.date,
            )
            return JSONResponse(content=geojson)
        elif request.model_type == 'ensemble':
            return await predict_ensemble(request)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported model_type: {request.model_type}. Allowed: unet, pinn, ensemble",
            )
    except HTTPException:
        raise
    except httpx.HTTPStatusError as exc:
        logger.error("Downstream service HTTP error: %s", exc)
        raise HTTPException(
            status_code=exc.response.status_code,
            detail=f"Downstream service returned error: {exc.response.text}",
        )
    except Exception as exc:
        logger.error("Failed to query %s service: %s", request.model_type, exc)
        raise HTTPException(
            status_code=502,
            detail=f"Failed to communicate with {request.model_type} service: {exc}",
        )


@app.post("/predict/ensemble")
async def predict_ensemble(request: PredictionRequest) -> JSONResponse:
    """
    POST /predict/ensemble

    Queries both U-Net and PINN services and combines them using weighted union scaling.
    Applies graceful degradation if one model fails.
    """
    if MOCK_INFERENCE or request.mock:
        return _serve_mock_fixture()

    notes: list[str] = []
    unet_res = None
    pinn_res = None

    try:
        unet_res = await call_unet(
            bbox=request.bbox,
            time_horizon=request.time_horizon,
            date=request.date,
        )
    except Exception as exc:
        logger.warning("U-Net query failed in ensemble: %s", exc)
        notes.append(f"unet_error: {exc}")

    try:
        pinn_res = await call_pinn(
            bbox=request.bbox,
            time_horizon=request.time_horizon,
            date=request.date,
        )
    except Exception as exc:
        logger.warning("PINN query failed in ensemble: %s", exc)
        notes.append(f"pinn_error: {exc}")

    if unet_res is None and pinn_res is None:
        raise HTTPException(
            status_code=502,
            detail=f"All ensemble services failed: {'; '.join(notes)}",
        )

    combined_fc = combine_ensemble_features(unet_res, pinn_res, notes=notes)
    return JSONResponse(content=combined_fc)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _serve_mock_fixture(model_type: str = "ensemble") -> JSONResponse:
    """
    Loads and normalizes the raw GeoJSON schemas from frontend_team_geojson_files.
    Merges all horizon outputs into a single unified FeatureCollection.
    Standardizes the root metadata.
    """
    if not FIXTURE_DIR.exists():
        raise HTTPException(
            status_code=500,
            detail=f"Mock fixture directory not found at {FIXTURE_DIR}.",
        )

    files_to_load = [
        "current_fire_goes18_20250110T21Z.geojson",
        "spread_goes_20250110T21Z_h1.geojson",
        "spread_goes_20250110T21Z_h3.geojson",
        "spread_goes_20250110T21Z_h6.geojson",
        "spread_goes_20250110T21Z_h24.geojson",
    ]

    all_features = []
    
    # Generate a single timestamp to avoid race conditions/mismatches across files
    current_timestamp = datetime.now(timezone.utc).isoformat()
    
    metadata: dict = {
        "timestamp": current_timestamp,
        "mock": True,
        "grid_resolution_km": 1.0,
        "source": set(),
        "source_model": model_type,
        "model_version": set()
    }

    for filename in files_to_load:
        filepath = FIXTURE_DIR / filename
        if not filepath.exists():
            continue
        
        with filepath.open("r") as f:
            data = json.load(f)
            
            # Intercept root metadata timestamp
            if "metadata" not in data or not isinstance(data["metadata"], dict):
                data["metadata"] = {}
            data["metadata"]["timestamp"] = current_timestamp
            
            # Normalize metadata
            if "source" in data:
                metadata["source"].add(data["source"])
            if "model_version" in data:
                metadata["model_version"].add(data["model_version"])
                
            # Ensure horizon_hours is always present, defaulting to 0 for current fire
            data.setdefault("horizon_hours", 0)

            # Extract ML properties that are at the root (like w_unet, members, horizon_hours, etc.)
            exclude_root_keys = {
                "type", "features", "timestamp",
                "layer", "window_start", "window_end", "valid_time", "valid_start"
            }
            root_ml_props = {k: v for k, v in data.items() if k not in exclude_root_keys}
            
            # Merge features and preserve properties
            for feature in data.get("features", []):
                feature.setdefault("properties", {})
                for k, v in root_ml_props.items():
                    if k not in feature["properties"]:
                        feature["properties"][k] = v
                feature["properties"]["source_model"] = model_type
                if model_type == "pinn":
                    feature["properties"].setdefault("members", 10)
                    feature["properties"].setdefault("w_pinn", 1.0)
                elif model_type == "unet":
                    feature["properties"].setdefault("members", 1)
                    feature["properties"].setdefault("w_unet", 1.0)
                else:  # ensemble
                    feature["properties"].setdefault("members", 11)
                    feature["properties"].setdefault("w_unet", 0.6)
                    feature["properties"].setdefault("w_pinn", 0.4)
                all_features.append(feature)

    metadata["source"] = list(metadata["source"])
    metadata["model_version"] = list(metadata["model_version"])

    unified_geojson = {
        "type": "FeatureCollection",
        "metadata": metadata,
        "features": all_features
    }

    return JSONResponse(content=unified_geojson)
