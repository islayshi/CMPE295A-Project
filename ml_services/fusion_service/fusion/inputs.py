"""Build the fusion UNet's 33 input layers for a live request, exactly as the training data were collected
(WildfirePINN rl/ens/fusion_collect.py), but from live sources instead of replay files:

  U-Net      the U-Net service's own code and weights (GOES-18 fire, weather, terrain, NDVI -> +1/+3/+6 h),
             run on GOES alone and with recent VIIRS detections added as seed points
  PIML       the PIML service's calibrated level-set forecast (FIRMS VIIRS start), run from the VIIRS start
             and again with its start brought up to the issue time and merged with GOES fire cells
  physics    burnable share, raw and calibrated spread rate, start mask (mean of the PIML's 180 m cells per 1 km)
  VIIRS      cells detected at or before the issue time (FIRMS, last 5 days) and in the last 12 h

Everything lives on the U-Net's 1 km EPSG:3310 model grid, so grid_id = row * 1000 + col.
"""
from __future__ import annotations

import datetime as dt
import threading

import numpy as np

from pinn_service import calibrated as cal
from pinn_service import forecaster as fc
from pinn_service import native_ingestion as ni
from pinn_service.contract import PredictionRequest
from pinn_service.lattice import LATTICE_NCOLS, LATTICE_X0, LATTICE_Y0, RES_M, from_3310, to_3310
from pinn_service.physics import spread_rate

from .channels import CH, IDX

_LOCK = threading.Lock()          # the PIML hooks below are module-level; one forecast at a time


class Patch:
    """The U-Net's model grid (lattice-aligned, 1 km): maps lon/lat to flat patch indices."""

    def __init__(self, grid):
        self.h, self.w = int(grid.h), int(grid.w)
        self.r0 = int(round((LATTICE_Y0 - grid.y0) / RES_M))
        self.c0 = int(round((grid.x0 - LATTICE_X0) / RES_M))
        self.x0, self.y0 = float(grid.x0), float(grid.y0)

    def rc(self, lon, lat):
        x, y = to_3310(np.asarray(lon, float), np.asarray(lat, float))
        row = np.floor((LATTICE_Y0 - np.asarray(y)) / RES_M).astype(np.int64) - self.r0
        col = np.floor((np.asarray(x) - LATTICE_X0) / RES_M).astype(np.int64) - self.c0
        return row, col

    def locate(self, lon, lat):
        """Same contract as the PIML grid's locate(): flat patch index (row * w + col) or -1 outside."""
        row, col = self.rc(lon, lat)
        ok = (row >= 0) & (row < self.h) & (col >= 0) & (col < self.w)
        return np.where(ok, row * self.w + col, -1)

    def mask(self, lon, lat):
        m = np.zeros((self.h, self.w), bool)
        if len(lon):
            f = self.locate(lon, lat)
            m.ravel()[f[f >= 0]] = True
        return m

    def dense(self, probs):
        a = np.zeros((self.h, self.w), np.float32)
        for k, v in probs.items():
            if 0 <= int(k) < a.size:
                a.ravel()[int(k)] = v
        return a

    def grid_ids(self):
        r = self.r0 + np.arange(self.h)[:, None]
        c = self.c0 + np.arange(self.w)[None, :]
        return (r * LATTICE_NCOLS + c).astype(np.int64)

    def lonlat_bbox(self):
        xs = [self.x0, self.x0 + self.w * RES_M]
        ys = [self.y0 - self.h * RES_M, self.y0]
        lon, lat = from_3310([xs[0], xs[1], xs[1], xs[0]], [ys[0], ys[0], ys[1], ys[1]])
        return [float(np.min(lon)), float(np.min(lat)), float(np.max(lon)), float(np.max(lat))]


# ------------------------------------------------------------------- PIML hooks: capture physics, GOES start

_HOOK = {"windows": [], "states": [], "goes": None, "patch": None}
_window, _calibrate = fc.window, cal.calibrate


def _win(*a, **k):
    w = _window(*a, **k)
    _HOOK["windows"].append(w)
    return w


def _cal(xs, ys, fx, fy, times_s, fuel, slope, env, res, ref_s, radius_m=cal.VIIRS_RADIUS_M):
    out = _calibrate(xs, ys, fx, fy, times_s, fuel, slope, env, res, ref_s, radius_m)
    w = _HOOK["windows"][-1]
    _HOOK["states"].append({"w": w, "fuel": fuel, "slope": slope, "env": env, "res": res, "ref_s": ref_s,
                            "start": out["start"].copy(), "t_b": out["t_b"], "alpha": out["alpha"], "act": out["act"]})
    goes = _HOOK["goes"]
    if goes is not None and goes.any():
        # bring the VIIRS start up to the issue time with the calibrated physics, then add GOES fire cells
        phi = cal.signed_distance(out["start"], res)
        if ref_s > out["t_b"]:
            phi = cal.roll(phi, res, fuel, slope, env, out["t_b"], ref_s, out["alpha"] * out["act"], 0.0)
        f = _HOOK["patch"].locate(w["lon"], w["lat"])
        g = np.zeros(f.shape, bool)
        g[f >= 0] = goes.ravel()[f[f >= 0]]
        out = dict(out)
        out["start"] = (phi < 0) | g
        out["t_b"] = max(out["t_b"], ref_s)
    return out


def run_piml(bbox, issue: dt.datetime, patch: Patch, source, goes=None):
    """PIML +1/+3/+6 h probabilities on the patch (3, H, W), its metadata and the captured physics states."""
    req = PredictionRequest.model_validate({
        "bbox": list(bbox), "time_horizon": 6, "model_type": "pinn",
        "date": issue.strftime("%Y-%m-%dT%H:%M:%SZ"), "additional_params": {"method": "calibrated"}})
    with _LOCK:
        _HOOK.update(windows=[], states=[], goes=goes, patch=patch)
        fc.window, cal.calibrate = _win, _cal
        try:
            probs, meta = fc.forecast(req, source, patch)
        finally:
            fc.window, cal.calibrate = _window, _calibrate
        states = list(_HOOK["states"])
    arr = np.stack([patch.dense(probs.get(h, {})) for h in (1, 3, 6)])
    return arr, meta, states


def physics_fields(states, patch: Patch):
    """Mean over the PIML's 180 m cells in each 1 km cell: burnable share, raw and calibrated spread rate, start."""
    n = patch.h * patch.w
    tot = np.zeros((4, n))
    cnt = np.zeros(n)
    for s in states:
        f = patch.locate(s["w"]["lon"], s["w"]["lat"]).ravel()
        ok = f >= 0
        if not ok.any():
            continue
        ws, wd, emc, _ = cal.mean_conditions(s["env"], s["ref_s"], s["ref_s"] + 6 * 3600.0)
        raw = spread_rate(s["fuel"], s["slope"], np.full(s["fuel"].shape, ws), np.full(s["fuel"].shape, emc))[0]
        calr = raw * s["alpha"] * s["act"]
        vals = [(raw > 0), raw, calr, s["start"]]
        cnt += np.bincount(f[ok], minlength=n)
        for i, v in enumerate(vals):
            tot[i] += np.bincount(f[ok], weights=np.asarray(v, float).ravel()[ok], minlength=n)
    with np.errstate(invalid="ignore", divide="ignore"):
        out = np.where(cnt > 0, tot / np.maximum(cnt, 1), 0.0)
    return out.reshape(4, patch.h, patch.w).astype(np.float32)


# ------------------------------------------------------------------------------------------- U-Net

def unet_run(unet, bundles, x):
    out = []
    for h in (1, 3, 6):
        b = bundles.get(h)
        if b is None:
            out.append(np.zeros(x.shape[:2], np.float32))
            continue
        p = b["model"](unet.goes_normalize(x, b["mu"], b["sd"])[None], training=False).numpy()[0, :, :, 0]
        p = np.minimum(b["calibrator"].predict(p.ravel()).reshape(p.shape), unet.P_MAX)
        out.append(p.astype(np.float32))
    return np.stack(out)


# ------------------------------------------------------------------------------------------- stack

def stack(a: dict) -> np.ndarray:
    """(33, H, W) in training order; identical to fusion_data.stack (use_unet=True)."""
    H, W = a["viirs_prior"].shape
    z = np.zeros((len(CH), H, W), np.float32)
    has_unet = "unet_goes" in a
    if has_unet:
        z[0:3] = a["unet_seed"].astype(np.float32)
        z[3:6] = a["unet_goes"].astype(np.float32)
    if "pinn" in a:
        z[6:9] = a["pinn"].astype(np.float32)
        z[9:12] = a["pinn_goes"].astype(np.float32)
        ph = a["phys"].astype(np.float32)
        z[12], z[13], z[14], z[15] = ph[0], np.log1p(100 * ph[1]), np.log1p(100 * ph[2]), ph[3]
    z[16], z[17] = a["viirs_prior"], a["viirs_recent"]
    if "x" in a:
        x = np.nan_to_num(a["x"].astype(np.float32))
        z[18] = a["goes_burned24"]
        z[19:31] = np.moveaxis(x, -1, 0)
        z[IDX["has_goes_fire"]] = float((x[..., 0] >= 0.5).any())
    z[IDX["has_unet"]] = float(has_unet)
    return np.nan_to_num(z)


def collect(bbox, issue: dt.datetime, unet, source, cfg: dict) -> tuple[Patch, dict, dict]:
    """All layers for one request on the U-Net model grid around the bbox. Returns (patch, arrays, notes)."""
    import pandas as pd

    grid = unet.model_grid_for_bbox(tuple(bbox))
    patch = Patch(grid)
    notes: dict = {"grid_cells": [patch.h, patch.w]}
    a: dict = {}
    ts = issue.timestamp()

    # VIIRS (FIRMS NRT S-NPP / NOAA-20 / NOAA-21, nominal + high confidence)
    dets = ni.firms_detections(patch.lonlat_bbox(), issue, float(cfg["viirs_history_hours"]))
    t = dets.time_s
    recent = np.isfinite(t) & (t > ts - float(cfg["viirs_recent_hours"]) * 3600.0)
    a["viirs_prior"] = patch.mask(dets.lon, dets.lat)
    a["viirs_recent"] = patch.mask(dets.lon[recent], dets.lat[recent])
    notes["viirs_detections"] = int(len(dets))
    notes["viirs_recent_detections"] = int(recent.sum())

    # PIML first (VIIRS start + physics fields): its weather request goes out before the U-Net's burst of
    # GOES and Open-Meteo downloads, and with no wildland fire there is nothing to forecast, so stop early.
    p, pmeta, states = run_piml(bbox, issue, patch, source)
    notes["piml_fires"] = int(pmeta.get("fires_detected", 0))
    if not states:
        return patch, a, notes
    a["pinn"] = p.astype(np.float16)
    a["phys"] = physics_fields(states, patch).astype(np.float16)

    # U-Net inputs once, then GOES alone and GOES + VIIRS seeds
    goes_now = None
    try:
        x, burned = unet.hourly_inputs(grid, pd.Timestamp(issue))
        x = np.asarray(x, np.float32)
        bundles = unet.get_hourly_bundles()
        if not bundles:
            raise RuntimeError("U-Net hourly models are not loaded")
        a["x"] = x.astype(np.float16)            # stored as float16 in training, as here
        a["goes_burned24"] = np.asarray(burned, bool)
        a["unet_goes"] = unet_run(unet, bundles, x).astype(np.float16)
        goes_now = x[..., 0] >= 0.5
        if a["viirs_recent"].any():
            xs_ = x.copy()
            m = a["viirs_recent"].astype(np.float32)
            for c in (0, 1, 2):
                xs_[..., c] = np.maximum(xs_[..., c], m)
            a["unet_seed"] = unet_run(unet, bundles, xs_).astype(np.float16)
        else:
            a["unet_seed"] = a["unet_goes"]
        notes["goes_fire_cells"] = int(goes_now.sum())
    except Exception as exc:          # the model still runs without the U-Net (trained with such samples)
        notes["unet_error"] = f"{type(exc).__name__}: {exc}"

    # PIML again with its start brought up to the issue time and merged with GOES fire (weather is cached)
    if goes_now is not None and goes_now.any():
        pg, _, _ = run_piml(bbox, issue, patch, source, goes=goes_now)
        a["pinn_goes"] = pg.astype(np.float16)
    else:
        a["pinn_goes"] = a["pinn"]
    return patch, a, notes
