"""
ML Services Client Layer — Fight Fire With AI
Dispatches requests to containerized U-Net and PINN services and combines ensemble outputs.
"""
from __future__ import annotations

import os
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

UNET_SERVICE_URL = os.getenv("UNET_SERVICE_URL", "http://localhost:8081")
PINN_SERVICE_URL = os.getenv("PINN_SERVICE_URL", "http://localhost:8082")
DEFAULT_W_UNET = float(os.getenv("DEFAULT_W_UNET", "0.6"))
DEFAULT_W_PINN = float(os.getenv("DEFAULT_W_PINN", "0.4"))


async def call_inference_service(url: str, payload: dict[str, Any], timeout: float = 120.0) -> dict[str, Any]:
    """Posts a prediction payload to a downstream inference service."""
    predict_endpoint = f"{url.rstrip('/')}/predict"
    logger.info("Calling inference service: %s", predict_endpoint)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(predict_endpoint, json=payload)
        response.raise_for_status()
        return response.json()


async def call_unet(
    bbox: tuple[float, float, float, float] | list[float],
    time_horizon: int = 6,
    date: str | None = None,
    seed_points: list[tuple[float, float]] | list[list[float]] | None = None,
    timeout: float = 120.0,
) -> dict[str, Any]:
    """Queries the U-Net inference service."""
    if date is None:
        date = datetime.now(timezone.utc).isoformat()
    payload: dict[str, Any] = {
        "bbox": list(bbox),
        "time_horizon": time_horizon,
        "model_type": "unet",
        "date": date,
    }
    if seed_points is not None:
        payload["seed_points"] = seed_points
    return await call_inference_service(UNET_SERVICE_URL, payload, timeout=timeout)


async def call_pinn(
    bbox: tuple[float, float, float, float] | list[float],
    time_horizon: int = 6,
    date: str | None = None,
    seed_points: list[tuple[float, float]] | list[list[float]] | None = None,
    timeout: float = 120.0,
) -> dict[str, Any]:
    """Queries the PINN inference service."""
    if date is None:
        date = datetime.now(timezone.utc).isoformat()
    payload: dict[str, Any] = {
        "bbox": list(bbox),
        "time_horizon": time_horizon,
        "model_type": "pinn",
        "date": date,
    }
    if seed_points is not None:
        payload["seed_points"] = seed_points
    return await call_inference_service(PINN_SERVICE_URL, payload, timeout=timeout)


def _compute_risk_label(horizon: int, probability: float) -> str:
    if horizon == 0 or probability >= 0.999:
        return "ACTIVE_FIRE"
    if probability >= 0.4:
        return "HIGH_RISK"
    if probability >= 0.15:
        return "MODERATE_RISK"
    return "LOW_RISK"


def combine_ensemble_features(
    unet_fc: dict[str, Any] | None,
    pinn_fc: dict[str, Any] | None,
    w_unet: float = DEFAULT_W_UNET,
    w_pinn: float = DEFAULT_W_PINN,
    notes: list[str] | None = None,
) -> dict[str, Any]:
    """
    Combines U-Net and PINN GeoJSON FeatureCollections into a unified ensemble.
    Uses union with weighted scaling as agreed in the design specification.
    """
    notes = list(notes or [])
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Graceful degradation if only one model response is available
    if unet_fc is None and pinn_fc is not None:
        pinn_copy = dict(pinn_fc)
        pinn_copy.setdefault("metadata", {})
        pinn_copy["metadata"]["ensemble_notes"] = "; ".join(notes or ["UNET unavailable; served PINN only"])
        return pinn_copy

    if pinn_fc is None and unet_fc is not None:
        unet_copy = dict(unet_fc)
        unet_copy.setdefault("metadata", {})
        unet_copy["metadata"]["ensemble_notes"] = "; ".join(notes or ["PINN unavailable; served UNET only"])
        return unet_copy

    if unet_fc is None and pinn_fc is None:
        return {
            "type": "FeatureCollection",
            "metadata": {
                "timestamp": now_iso,
                "source_model": "ensemble",
                "status": "error",
                "ensemble_notes": "All downstream models failed",
            },
            "features": [],
        }

    unet_features = unet_fc.get("features", [])
    pinn_features = pinn_fc.get("features", [])

    # If U-Net returned empty features (e.g. status == "no_active_fire") but PINN has features,
    # don't suppress PINN by 0.4 — promote PINN to full weight (1.0)!
    if not unet_features and pinn_features:
        w_u = 0.0
        w_p = 1.0
        notes.append("U-Net detected no active fire in GOES-18; promoted PINN to full weight (1.0)")
    elif not pinn_features and unet_features:
        w_u = 1.0
        w_p = 0.0
        notes.append("PINN detected no active fire; promoted U-Net to full weight (1.0)")
    else:
        # Normalize weights
        total_w = w_unet + w_pinn
        w_u = round(w_unet / total_w, 4) if total_w > 0 else 0.5
        w_p = round(w_pinn / total_w, 4) if total_w > 0 else 0.5

    # Index by (grid_id, horizon_hours)
    unet_map: dict[tuple[int, int], dict[str, Any]] = {}
    for feat in unet_features:
        props = feat.get("properties", {})
        key = (props.get("grid_id"), props.get("horizon_hours", 0))
        unet_map[key] = feat

    pinn_map: dict[tuple[int, int], dict[str, Any]] = {}
    for feat in pinn_features:
        props = feat.get("properties", {})
        key = (props.get("grid_id"), props.get("horizon_hours", 0))
        pinn_map[key] = feat

    all_keys = set(unet_map.keys()).union(set(pinn_map.keys()))
    combined_features = []

    for key in sorted(all_keys):
        grid_id, horizon = key
        in_unet = key in unet_map
        in_pinn = key in pinn_map

        if in_unet and in_pinn:
            geom = unet_map[key]["geometry"]
            p_u = unet_map[key]["properties"].get("fire_probability", 0.0)
            p_p = pinn_map[key]["properties"].get("fire_probability", 0.0)
            blended_p = w_u * p_u + w_p * p_p
            members = 2
        elif in_unet:
            geom = unet_map[key]["geometry"]
            p_u = unet_map[key]["properties"].get("fire_probability", 0.0)
            blended_p = w_u * p_u
            members = 1
        else:
            geom = pinn_map[key]["geometry"]
            p_p = pinn_map[key]["properties"].get("fire_probability", 0.0)
            blended_p = w_p * p_p
            members = 1

        blended_p = round(float(blended_p), 4)

        combined_features.append({
            "type": "Feature",
            "geometry": geom,
            "properties": {
                "grid_id": grid_id,
                "fire_probability": blended_p,
                "horizon_hours": horizon,
                "risk_label": _compute_risk_label(horizon, blended_p),
                "source_model": "ensemble",
                "w_unet": w_u,
                "w_pinn": w_p,
                "members": members,
            },
        })

    status = "ok" if combined_features else "no_active_fire"
    metadata = {
        "timestamp": now_iso,
        "source_model": "ensemble",
        "model_version": "ensemble-v1.0",
        "grid_resolution_km": 1.0,
        "total_cells": len(combined_features),
        "status": status,
        "w_unet": w_u,
        "w_pinn": w_p,
        "ensemble_notes": "; ".join(notes) if notes else "nominal",
    }

    return {
        "type": "FeatureCollection",
        "status": status,
        "metadata": metadata,
        "features": combined_features,
    }



async def probe_services_health() -> dict[str, Any]:
    """Probes the /health endpoint of U-Net and PINN services."""
    results: dict[str, Any] = {}
    async with httpx.AsyncClient(timeout=5.0) as client:
        # Check U-Net
        try:
            r = await client.get(f"{UNET_SERVICE_URL.rstrip('/')}/health")
            results["unet"] = r.json() if r.status_code == 200 else {"status": "error", "code": r.status_code}
        except Exception as exc:
            results["unet"] = {"status": "unreachable", "error": str(exc)}

        # Check PINN
        try:
            r = await client.get(f"{PINN_SERVICE_URL.rstrip('/')}/health")
            results["pinn"] = r.json() if r.status_code == 200 else {"status": "error", "code": r.status_code}
        except Exception as exc:
            results["pinn"] = {"status": "unreachable", "error": str(exc)}

    return results
