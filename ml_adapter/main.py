"""
FastAPI ML Adapter — Fight Fire With AI
========================================
Isolated translation layer between the Django/Celery backend and the
ML models (U-Net and PINN microservices / Vertex AI).

Mock mode behaviour (MOCK_INFERENCE=true or request.mock=True):
  - Returns a clean GeoJSON FeatureCollection with features: [] and status: "no_active_fire".
  - Mock fixture files and synthetic translations are completely purged.

Live mode behaviour (MOCK_INFERENCE=false):
  - Dispatches to live containerized U-Net and PINN inference services.
  - Forwards seed_points (hotspots) to trigger active fire spread forecasts.
  - Combines multi-model predictions via weighted spatial union.
  - When models report 0 features, returns features: [] with status: "no_active_fire".

Design Doc §1.1 FastAPI ML Adapter, §3.2, §8.B, §14 ML Integration Contract.
"""

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
        "Dispatches prediction requests to live containerized U-Net and PINN services."
    ),
    version="1.0.0",
)

MOCK_INFERENCE: bool = os.getenv("MOCK_INFERENCE", "false").lower() == "true"



# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class PredictionRequest(BaseModel):
    """
    Payload sent by the Django Celery harvester.
    """
    bbox: tuple[float, float, float, float] = (-122.9, 36.9, -121.5, 38.3)
    time_horizon: int = 6
    model_type: str = "unet"
    date: str | None = None
    mock: bool = False
    seed_points: list[tuple[float, float]] | list[list[float]] | None = None
    ignition_points: list[tuple[float, float]] | list[list[float]] | None = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _clean_empty_feature_collection(
    model_type: str = "unet",
    status: str = "no_active_fire",
    mock: bool = False,
) -> JSONResponse:
    now_iso = datetime.now(timezone.utc).isoformat()
    content = {
        "type": "FeatureCollection",
        "status": status,
        "metadata": {
            "timestamp": now_iso,
            "source_model": model_type,
            "status": status,
            "mock": mock,
            "total_cells": 0,
        },
        "features": [],
    }
    return JSONResponse(content=content)


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

    Dispatches prediction requests to downstream inference services (U-Net, PINN, or Ensemble).
    When live models report 0 features, returns a clean GeoJSON FeatureCollection with
    features: [] and status: "no_active_fire".
    """
    if MOCK_INFERENCE or request.mock:
        return _clean_empty_feature_collection(model_type=request.model_type, status="no_active_fire", mock=True)

    try:
        seeds = request.seed_points or request.ignition_points
        if request.model_type == 'unet':
            kwargs = {"bbox": request.bbox, "time_horizon": request.time_horizon, "date": request.date}
            if seeds is not None:
                kwargs["seed_points"] = seeds
            geojson = await call_unet(**kwargs)
            if not geojson.get("features"):
                return _clean_empty_feature_collection(model_type='unet', status="no_active_fire", mock=False)
            if "status" not in geojson:
                geojson["status"] = geojson.get("metadata", {}).get("status", "ok")
            return JSONResponse(content=geojson)
        elif request.model_type == 'pinn':
            kwargs = {"bbox": request.bbox, "time_horizon": request.time_horizon, "date": request.date}
            if seeds is not None:
                kwargs["seed_points"] = seeds
            geojson = await call_pinn(**kwargs)
            if not geojson.get("features"):
                return _clean_empty_feature_collection(model_type='pinn', status="no_active_fire", mock=False)
            if "status" not in geojson:
                geojson["status"] = geojson.get("metadata", {}).get("status", "ok")
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
    When live models report 0 features, returns a clean GeoJSON FeatureCollection with
    features: [] and status: "no_active_fire".
    """
    if MOCK_INFERENCE or request.mock:
        return _clean_empty_feature_collection(model_type="ensemble", status="no_active_fire", mock=True)

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
    if not combined_fc.get("features"):
        return _clean_empty_feature_collection(model_type="ensemble", status="no_active_fire", mock=False)
    if "status" not in combined_fc:
        combined_fc["status"] = combined_fc.get("metadata", {}).get("status", "ok")
    return JSONResponse(content=combined_fc)

