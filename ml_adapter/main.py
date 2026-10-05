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
import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

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

FIXTURE_DIR: Path = Path(__file__).parent / "ml_adapter/fixtures"


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
def health() -> dict:
    """
    GET /health

    Returns the operational status of the ML Adapter.
    Consumed by Django's GET /api/health/ endpoint (NFR-O02).
    """
    return {
        "status": "ok",
        "mock": MOCK_INFERENCE,
        "models_loaded": not MOCK_INFERENCE,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/predict/progression")
def predict_progression(request: PredictionRequest) -> JSONResponse:
    """
    POST /predict/progression

    Month 1 (MOCK_INFERENCE=true):
      Reads and normalizes the mock GeoJSONs.

    Month 2 (MOCK_INFERENCE=false):
      Invokes the Vertex AI managed endpoints. Returns their combined GeoJSON.
    """
    if MOCK_INFERENCE or request.mock:
        if request.model_type == 'unet':
            return _serve_mock_fixture()
        
        # Placeholder for other model types (e.g., pinn, rl_agent)
        return JSONResponse(content={
            "type": "FeatureCollection",
            "metadata": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "mock": True,
                "model_type": request.model_type
            },
            "features": []
        })

    # --- Month 2 placeholder ---
    # TODO: Invoke Vertex AI endpoints with request.bbox and request.time_horizon
    # from adapters.vertex import call_unet, call_pinn, call_rl_agent
    # if request.model_type == 'unet':
    #     geojson = call_unet(request.bbox, request.time_horizon)
    # elif request.model_type == 'pinn':
    #     geojson = call_pinn(request.bbox, request.time_horizon)
    # else:
    #     unet_output   = call_unet(request.bbox, request.time_horizon)
    #     pinn_output   = call_pinn(request.bbox, request.time_horizon)
    #     rl_output     = call_rl_agent(request.bbox, request.time_horizon)
    #     geojson       = ensemble_combine(unet_output, pinn_output, rl_output)
    # return JSONResponse(content=geojson)

    raise HTTPException(
        status_code=501,
        detail=(
            "Live Vertex AI inference is not yet implemented. "
            "Set MOCK_INFERENCE=true to use the static fixture."
        ),
    )


@app.post("/predict/ensemble")
def predict_ensemble(request: PredictionRequest) -> JSONResponse:
    """
    POST /predict/ensemble
    """
    if MOCK_INFERENCE or request.mock:
        return _serve_mock_fixture()

    raise HTTPException(
        status_code=501,
        detail="Ensemble inference not yet implemented. Set MOCK_INFERENCE=true.",
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _serve_mock_fixture() -> JSONResponse:
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
        "Palisades_2025-01-11_h24.geojson"
    ]

    all_features = []
    
    # Generate a single timestamp to avoid race conditions/mismatches across files
    current_timestamp = datetime.now(timezone.utc).isoformat()
    
    metadata: dict = {
        "timestamp": current_timestamp,
        "mock": True,
        "grid_resolution_km": 1.0,
        "source": set(),
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
                all_features.append(feature)

    metadata["source"] = list(metadata["source"])
    metadata["model_version"] = list(metadata["model_version"])

    unified_geojson = {
        "type": "FeatureCollection",
        "metadata": metadata,
        "features": all_features
    }

    return JSONResponse(content=unified_geojson)
