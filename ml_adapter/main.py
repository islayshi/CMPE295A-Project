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

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

# Load root .env file if present
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

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
    seed_points: list[tuple[float, float]] | list[list[float]] | None = None
    ignition_points: list[tuple[float, float]] | list[list[float]] | None = None


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
        return _serve_mock_fixture(model_type=request.model_type, target_bbox=request.bbox)

    try:
        seeds = request.seed_points or request.ignition_points
        if request.model_type == 'unet':
            kwargs = {"bbox": request.bbox, "time_horizon": request.time_horizon, "date": request.date}
            if seeds is not None:
                kwargs["seed_points"] = seeds
            geojson = await call_unet(**kwargs)
            return JSONResponse(content=geojson)
        elif request.model_type == 'pinn':
            kwargs = {"bbox": request.bbox, "time_horizon": request.time_horizon, "date": request.date}
            if seeds is not None:
                kwargs["seed_points"] = seeds
            geojson = await call_pinn(**kwargs)
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
        return _serve_mock_fixture(model_type="ensemble", target_bbox=request.bbox)

    notes: list[str] = []
    unet_res = None
    pinn_res = None
    seeds = request.seed_points or request.ignition_points

    try:
        kwargs = {"bbox": request.bbox, "time_horizon": request.time_horizon, "date": request.date}
        if seeds is not None:
            kwargs["seed_points"] = seeds
        unet_res = await call_unet(**kwargs)
    except Exception as exc:
        logger.warning("U-Net query failed in ensemble: %s", exc)
        notes.append(f"unet_error: {exc}")

    try:
        kwargs = {"bbox": request.bbox, "time_horizon": request.time_horizon, "date": request.date}
        if seeds is not None:
            kwargs["seed_points"] = seeds
        pinn_res = await call_pinn(**kwargs)
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

def _translate_coordinates(coords, delta_lon: float, delta_lat: float):
    if not coords:
        return coords
    if isinstance(coords[0], (int, float)):
        return [round(coords[0] + delta_lon, 6), round(coords[1] + delta_lat, 6)]
    return [_translate_coordinates(c, delta_lon, delta_lat) for c in coords]


def _serve_mock_fixture(
    model_type: str = "ensemble",
    target_bbox: tuple[float, float, float, float] | list[float] | None = None,
) -> JSONResponse:
    """
    Loads and normalizes the raw GeoJSON schemas from frontend_team_geojson_files.
    Merges all horizon outputs into a single unified FeatureCollection.
    Standardizes the root metadata.
    If target_bbox is provided, translates polygon coordinate rings by (delta_lon, delta_lat)
    calculated from the fixture reference center (-122.15, 37.05) to the target bbox center.
    """
    if not FIXTURE_DIR.exists():
        raise HTTPException(
            status_code=500,
            detail=f"Mock fixture directory not found at {FIXTURE_DIR}.",
        )

    delta_lon = 0.0
    delta_lat = 0.0
    grid_id_offset = 0
    if target_bbox and len(target_bbox) == 4:
        ref_lon, ref_lat = -122.15, 37.05
        target_center_lon = (target_bbox[0] + target_bbox[2]) / 2.0
        target_center_lat = (target_bbox[1] + target_bbox[3]) / 2.0
        delta_lon = round(target_center_lon - ref_lon, 6)
        delta_lat = round(target_center_lat - ref_lat, 6)
        if abs(delta_lon) > 1e-5 or abs(delta_lat) > 1e-5:
            coord_str = f"{round(delta_lon, 4):.4f}_{round(delta_lat, 4):.4f}"
            hash_int = int(hashlib.md5(coord_str.encode()).hexdigest()[:8], 16)
            grid_id_offset = ((hash_int % 100_000) + 1) * 10000

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
    if abs(delta_lon) > 1e-5 or abs(delta_lat) > 1e-5:
        metadata["spatial_colocation"] = {
            "reference_center": [-122.15, 37.05],
            "target_center": [round(target_center_lon, 6), round(target_center_lat, 6)],
            "delta": [delta_lon, delta_lat],
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

                # Translate coordinates if target_bbox provided
                if (abs(delta_lon) > 1e-5 or abs(delta_lat) > 1e-5) and "geometry" in feature:
                    translated_geom = dict(feature["geometry"])
                    if "coordinates" in translated_geom:
                        translated_geom["coordinates"] = _translate_coordinates(
                            translated_geom["coordinates"], delta_lon, delta_lat
                        )
                    feature["geometry"] = translated_geom

                if grid_id_offset != 0 and "grid_id" in feature["properties"]:
                    feature["properties"]["grid_id"] = feature["properties"]["grid_id"] + grid_id_offset

                all_features.append(feature)

    metadata["source"] = list(metadata["source"])
    metadata["model_version"] = list(metadata["model_version"])

    unified_geojson = {
        "type": "FeatureCollection",
        "metadata": metadata,
        "features": all_features
    }

    return JSONResponse(content=unified_geojson)
