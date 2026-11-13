"""Request -> GeoJSON for the fusion UNet (model_type "fusion"), in the team's prediction contract:

  one FeatureCollection, horizons {0, 1, 3, 6} <= time_horizon (the Mapbox time scrubber needs all four), closed [lon, lat] Polygons on the 1 km EPSG:3310 lattice clipped to the bbox, properties grid_id,
  fire_probability, horizon_hours, source_model = "fusion", members = 1, risk_label.

Probabilities are Platt-calibrated (fitted on the dev fires) chances that a cell newly burns, as seen by VIIRS,
by the horizon. Cells burning at issue time are returned with probability 1.0 (burning_at_issue = true). The
fusion model forecasts +3 h and +6 h only, so the +1 h layer shows just the fire at issue time. Only
cells within 10 km of the fire are forecast, the domain the model was trained and scored on.
"""
from __future__ import annotations

import datetime as dt
import json
import time
from pathlib import Path

import numpy as np
from scipy import ndimage

from pinn_service.lattice import LatticeGrid

from .channels import CROP, IDX
from .net import load_copies, logit, predict_raw

HERE = Path(__file__).resolve().parent
CONFIG = json.loads((HERE / "config.json").read_text())
SOURCE_MODEL = "fusion"
DEFAULT_HOUR_UTC = 21
LATTICE = LatticeGrid()


class ContractError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


# ------------------------------------------------------------------------------------------- request parsing

def parse_request(req: dict) -> dict:
    model_type = str(req.get("model_type", SOURCE_MODEL)).strip().lower()
    if model_type != SOURCE_MODEL:
        raise ContractError(f"this service serves model_type 'fusion' only; got '{model_type}'")
    try:
        bbox = [float(v) for v in req.get("bbox")]
    except Exception:
        raise ContractError("bbox must be [min_lon, min_lat, max_lon, max_lat] in degrees")
    if len(bbox) != 4 or not (-180 <= bbox[0] < bbox[2] <= 180 and -90 <= bbox[1] < bbox[3] <= 90):
        raise ContractError("bbox must be [min_lon, min_lat, max_lon, max_lat] with min < max")
    params = req.get("additional_params") or {}
    try:
        limit = int(req.get("time_horizon", 6))
        conf = float(params.get("confidence_threshold", 0.0) or 0.0)
    except (TypeError, ValueError):
        raise ContractError("time_horizon must be a whole number of hours and confidence_threshold a number")
    if not 0 <= limit <= 72:
        raise ContractError("time_horizon must be between 0 and 72 hours (forecasts go to 6 h)")
    return {"bbox": bbox, "horizons": [h for h in (0, 1, 3, 6) if h <= limit], "issue": parse_issue_time(req.get("date"), params),
            "threshold": max(conf, float(CONFIG["emit_threshold"]))}


def parse_issue_time(value, params) -> dt.datetime:
    now = dt.datetime.now(dt.timezone.utc).replace(minute=0, second=0, microsecond=0)
    s = str(value or "").strip()
    try:
        if not s:
            t = now
        elif len(s) <= 10:
            t = dt.datetime.fromisoformat(s).replace(tzinfo=dt.timezone.utc) + dt.timedelta(hours=DEFAULT_HOUR_UTC)
        else:
            t = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
            t = t.replace(tzinfo=dt.timezone.utc) if t.tzinfo is None else t.astimezone(dt.timezone.utc)
    except ValueError:
        raise ContractError(f"could not read date {s!r}; use 'YYYY-MM-DD' or an ISO-8601 UTC timestamp")
    if params.get("hour") is not None:
        t = t.replace(hour=int(params["hour"]))
    t = t.replace(minute=0, second=0, microsecond=0)
    return min(t, now)


# ------------------------------------------------------------------------------------------- model

_NETS: list = []


def nets():
    if not _NETS:
        _NETS.extend(load_copies())
    return _NETS


def calibrated(p_raw, h):
    c = CONFIG["calibration"][f"h{h}"]
    return 1 / (1 + np.exp(-(c["a"] * logit(p_raw) + c["b"])))


def fire_now(z):
    """Cells burning at issue time: recent VIIRS, GOES fire now, or the PIML's start (its burned area now)."""
    return (z[IDX["viirs_recent"]] > 0) | (z[IDX["goes_fire_now"]] >= 0.5) | (z[IDX["pinn_start"]] > 0)


def crop(arr, r, c, size=CROP):
    """Crop (..., H, W) around (r, c), zero-padded at the patch edge (as in training). Returns crop and offsets."""
    h = size // 2
    H, W = arr.shape[-2:]
    out = np.zeros(arr.shape[:-2] + (size, size), arr.dtype)
    r0, c0 = r - h, c - h
    rs, cs = max(r0, 0), max(c0, 0)
    re, ce = min(r0 + size, H), min(c0 + size, W)
    if re > rs and ce > cs:
        out[..., rs - r0:re - r0, cs - c0:ce - c0] = arr[..., rs:re, cs:ce]
    return out, r0, c0


def wildland_fire(z):
    """Burning cells that belong to a fire the PIML accepted: it drops hot spots with little burnable fuel
    (refineries, flares, crop burns), and the fusion model follows it, so those are neither shown nor forecast."""
    piml = (z[IDX["pinn_start"]] > 0) | (z[IDX["pinn1"]] > 0)
    if not piml.any():
        return np.zeros(piml.shape, bool)
    return fire_now(z) & ndimage.binary_dilation(piml, iterations=3)


def fire_centres(z, max_n: int):
    """One crop centre per separate fire (largest first); fires closer than 8 km share a crop."""
    fire = wildland_fire(z)
    if not fire.any():
        return []
    lab, n = ndimage.label(ndimage.binary_dilation(fire, iterations=2))
    comps = []
    for k in range(1, n + 1):
        rr, cc = np.nonzero(fire & (lab == k))
        if len(rr):
            comps.append((len(rr), int(round(rr.mean())), int(round(cc.mean()))))
    comps.sort(reverse=True)
    centres = []
    for _, r, c in comps:
        if all(np.hypot(r - r2, c - c2) > 8 for r2, c2 in centres):
            centres.append((r, c))
        if len(centres) >= max_n:
            break
    return centres


def forecast_patch(z: np.ndarray, max_fires: int):
    """z: (33, H, W) stacked layers. Returns calibrated (P3, P6), copy spread SD6 and the burning mask, (H, W)."""
    H, W = z.shape[1:]
    P3, P6, SD = (np.zeros((H, W), np.float32) for _ in range(3))
    centres = fire_centres(z, max_fires)
    if not centres:
        return P3, P6, SD, np.zeros((H, W), bool), 0
    crops = [crop(z, r, c) for r, c in centres]
    p3, p6, sd = predict_raw(nets(), np.array([cz for cz, _, _ in crops]))
    near_km = float(CONFIG["near_fire_km"])
    for (cz, r0, c0), a3, a6, s6 in zip(crops, p3, p6, sd):
        f = fire_now(cz)
        if not f.any():
            f = cz[IDX["viirs_prior"]] > 0
        near = (cz[IDX["viirs_prior"]] <= 0) & (ndimage.distance_transform_edt(~f) <= near_km)
        q3 = np.where(near, calibrated(a3, 3), 0.0)
        q6 = np.where(near, calibrated(a6, 6), 0.0)                    # exactly as scored on the test fires
        q3 = np.minimum(q3, q6)                                          # burn probability cannot fall with time
        rs, cs = max(r0, 0), max(c0, 0)
        re, ce = min(r0 + CROP, H), min(c0 + CROP, W)
        win = (slice(rs - r0, re - r0), slice(cs - c0, ce - c0))
        P3[rs:re, cs:ce] = np.maximum(P3[rs:re, cs:ce], q3[win])
        P6[rs:re, cs:ce] = np.maximum(P6[rs:re, cs:ce], q6[win])
        SD[rs:re, cs:ce] = np.maximum(SD[rs:re, cs:ce], np.where(near, s6, 0.0)[win])
    return P3, P6, SD, wildland_fire(z), len(centres)


# ------------------------------------------------------------------------------------------- GeoJSON

def risk_label(p: float) -> str:
    if p >= CONFIG["operating_threshold"]:
        return "HIGH_RISK"
    if p >= CONFIG["moderate_threshold"]:
        return "MODERATE_RISK"
    return "LOW_RISK"


def feature_collection(layers: dict, burning, spread, grid_ids, bbox, issue, threshold, meta, status="ok"):
    feats, dropped = [], 0

    def emit(gid, p, h, extra):
        nonlocal dropped
        ring = LATTICE.ring(int(gid), bbox)
        if ring is None:
            dropped += 1
            return
        props = {"grid_id": int(gid), "fire_probability": round(float(p), 4), "horizon_hours": int(h),
                 "source_model": SOURCE_MODEL, "members": 1}
        props.update(extra)
        feats.append({"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [ring]}, "properties": props})

    for h in sorted(layers):
        P = layers[h]
        for r, c in zip(*np.nonzero(burning)):
            emit(grid_ids[r, c], 1.0, h, {"risk_label": "ACTIVE_FIRE", "burning_at_issue": True})
        if P is None:
            continue
        for r, c in zip(*np.nonzero((P >= threshold) & ~burning)):
            emit(grid_ids[r, c], P[r, c], h, {"risk_label": risk_label(float(P[r, c])), "burning_at_issue": False,
                                             "copy_spread": round(float(spread[r, c]), 4)})
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    metadata = {"timestamp": dt.datetime.now(dt.timezone.utc).strftime(fmt), "issue_time": issue.strftime(fmt),
                "reference_time": issue.strftime(fmt), "source_model": SOURCE_MODEL, "model_version": CONFIG["model_version"],
                "status": status, "grid": LATTICE.name, "grid_resolution_km": 1.0, "grid_ids_provisional": False,
                "horizons_hours": sorted(layers), "total_cells": len(feats), "cells_outside_bbox_dropped": dropped,
                "probability": "calibrated chance the cell newly burns (VIIRS) by the horizon; burning cells = 1.0",
                "operating_threshold": CONFIG["operating_threshold"], "test_results_11_fires": CONFIG["test_results_11_fires"]}
    metadata.update(meta)
    return {"type": "FeatureCollection", "metadata": metadata, "features": feats}


def handle(req: dict, unet=None, source=None) -> tuple[int, dict]:
    """(status, body). ``unet``/``source`` are injectable for tests; by default the U-Net service module and the
    PIML service's native (FIRMS / Open-Meteo / gridMET / LANDFIRE) source."""
    started = time.perf_counter()
    try:
        r = parse_request(req)
    except ContractError as exc:
        return exc.status, {"detail": str(exc)}
    from .inputs import collect, stack            # imports the PIML service code (and, lazily, TensorFlow)
    if unet is None:
        import inference as unet                  # noqa: F811  the U-Net service module (on sys.path)
    if source is None:
        from pinn_service.native_ingestion import NativeSource
        source = NativeSource()
    try:
        patch, arrays, notes = collect(r["bbox"], r["issue"], unet, source, CONFIG)
    except ValueError as exc:                     # e.g. bbox larger than the U-Net grid allows
        return 400, {"detail": str(exc)}
    except Exception as exc:
        status = getattr(exc, "status", 503)
        detail = str(getattr(exc, "detail", exc))
        return status, {"detail": f"input data unavailable: {detail}"}
    meta = {"inputs": notes, "has_unet": "unet_goes" in arrays}
    if "pinn" not in arrays:
        meta["note"] = "no wildland fire found by the PIML in or near the bbox; nothing to forecast"
        meta["runtime_s"] = round(time.perf_counter() - started, 2)
        return 200, feature_collection({}, np.zeros((0, 0), bool), None, None, r["bbox"], r["issue"], r["threshold"],
                                       meta, status="no_active_fire")
    z = stack(arrays)
    P3, P6, SD, burning, n = forecast_patch(z, int(CONFIG["max_fires_per_request"]))
    layers = {h: {0: None, 1: None, 3: P3, 6: P6}[h] for h in r["horizons"]}
    if 1 in layers:
        meta["horizon_1h_note"] = "the fusion model forecasts +3 h and +6 h; the +1 h layer shows the fire at issue time"
    meta.update(fires_forecast=n, runtime_s=round(time.perf_counter() - started, 2))
    return 200, feature_collection(layers, burning, SD, patch.grid_ids(), r["bbox"], r["issue"], r["threshold"], meta)
