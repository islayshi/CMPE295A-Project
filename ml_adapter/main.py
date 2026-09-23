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

FIXTURE_PATH: Path = Path(__file__).parent / "fixtures" / "bay_area_fixture.json"


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class PredictionRequest(BaseModel):
    """
    Payload sent by the Django Celery harvester.

    In Month 1, only `date` and `mock` are used.
    In Month 2, `features` will carry the assembled feature tensor
    (derived from GOES-18, VIIRS, vegetation indices, and weather data).
    """
    date: str
    mock: bool = True
    # Month 2: features: dict | None = None


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
      Reads and returns the static bay_area_fixture.json GeoJSON.
      This simulates a full U-Net + PINN + RL Agent ensemble response.

    Month 2 (MOCK_INFERENCE=false):
      Assembles the feature tensor from the request payload and invokes
      the Vertex AI managed endpoints. Returns their combined GeoJSON.

    Design Doc §8.B, §14 ML Integration Contract.
    FR-E09: Mock mode for Month 1 development and CI/CD without trained models.
    """
    if MOCK_INFERENCE or request.mock:
        return _serve_mock_fixture()

    # --- Month 2 placeholder ---
    # TODO: Invoke Vertex AI endpoints with request.features
    # from adapters.vertex import call_unet, call_pinn, call_rl_agent
    # unet_output   = call_unet(request.features)
    # pinn_output   = call_pinn(request.features)
    # rl_output     = call_rl_agent(request.features)
    # geojson       = ensemble_combine(unet_output, pinn_output, rl_output)
    # return JSONResponse(content=geojson)

    raise HTTPException(
        status_code=501,
        detail=(
            "Live Vertex AI inference is not yet implemented. "
            "Set MOCK_INFERENCE=true to use the static Bay Area fixture."
        ),
    )


@app.post("/predict/ensemble")
def predict_ensemble(request: PredictionRequest) -> JSONResponse:
    """
    POST /predict/ensemble

    Explicit ensemble endpoint that combines all available model outputs
    using weighted voting / probability averaging.
    Extends Paper 3's Cellular Automata Rule 30 majority-vote pattern
    (Malik et al., IEEE CCWC 2022).

    Month 1: delegates to mock fixture (same as /predict/progression).
    Month 2: orchestrates all three Vertex AI models and combines outputs.
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
    Loads and returns the static bay_area_fixture.json GeoJSON.
    Stamps the current UTC timestamp so each response looks fresh.
    """
    if not FIXTURE_PATH.exists():
        raise HTTPException(
            status_code=500,
            detail=f"Mock fixture not found at {FIXTURE_PATH}. Check ml_adapter/fixtures/.",
        )

    with FIXTURE_PATH.open("r") as f:
        geojson = json.load(f)

    # Stamp with the current run time so Django can track inference cadence
    geojson["metadata"]["timestamp"] = datetime.now(timezone.utc).isoformat()

    return JSONResponse(content=geojson)
