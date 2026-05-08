"""
Run the trained U-Net on one .npz sample and export the predicted next-day FireMask
as a GeoJSON polygon layer (for simulation software).

Inputs:
  - .keras model (e.g., wildfire_unet_bay_18_21.keras)
  - .npz sample (unet_YYYY-MM-DD.npz) containing X (H,W,12)

Output:
  - GeoJSON FeatureCollection of Polygon/MultiPolygon in WGS84 lon/lat

Notes:
  - We approximate polygons by extracting contours from the thresholded mask.
  - This is demo-grade vectorization (no topology fixing). For production, you’d
    typically use rasterio/shapely.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np


def _lonlat_to_web_mercator(lon: float, lat: float) -> Tuple[float, float]:
    lat = float(np.clip(lat, -85.05112878, 85.05112878))
    lon = float(lon)
    r = 6378137.0
    x = r * np.deg2rad(lon)
    y = r * np.log(np.tan(np.pi / 4.0 + np.deg2rad(lat) / 2.0))
    return float(x), float(y)


def _web_mercator_to_lonlat(x: float, y: float) -> Tuple[float, float]:
    r = 6378137.0
    lon = np.rad2deg(x / r)
    lat = np.rad2deg(2.0 * np.arctan(np.exp(y / r)) - np.pi / 2.0)
    return float(lon), float(lat)


def _meters_buffer_for_km(radius_km: float) -> float:
    return float(radius_km * 1000.0)


def grid_bbox_mercator(center_lat: float, center_lon: float, radius_km: float) -> Tuple[float, float, float, float]:
    cx, cy = _lonlat_to_web_mercator(lon=center_lon, lat=center_lat)
    b = _meters_buffer_for_km(radius_km)
    return (cx - b, cy - b, cx + b, cy + b)


def load_npz_X(path: Path) -> np.ndarray:
    z = np.load(path)
    X = np.asarray(z["X"], dtype=np.float32)
    return X


def mask_to_polygons_geojson(
    mask01: np.ndarray,
    *,
    bbox_merc: Tuple[float, float, float, float],
) -> Dict[str, Any]:
    """
    Convert a binary mask (H,W) into a GeoJSON FeatureCollection.
    Uses matplotlib.contour to extract polygon-like rings.
    """
    import matplotlib.pyplot as plt

    H, W = mask01.shape
    cs = plt.contour(mask01.astype(np.float32), levels=[0.5])
    minx, miny, maxx, maxy = bbox_merc
    dx = (maxx - minx) / W
    dy = (maxy - miny) / H

    # Matplotlib API differs slightly across versions; handle both.
    path_lists = []
    if hasattr(cs, "collections"):
        for coll in cs.collections:  # type: ignore[attr-defined]
            path_lists.extend(coll.get_paths())
    elif hasattr(cs, "get_paths"):
        path_lists.extend(cs.get_paths())  # type: ignore[attr-defined]

    features = []
    for path in path_lists:
        v = path.vertices  # (N,2) in (x=col, y=row) coordinates
        if v.shape[0] < 4:
            continue

        coords_lonlat = []
        for x_img, y_img in v:
            col = float(x_img)
            row = float(y_img)
            x = minx + (col + 0.5) * dx
            y = maxy - (row + 0.5) * dy  # flip y
            lon, lat = _web_mercator_to_lonlat(x, y)
            coords_lonlat.append([lon, lat])

        if coords_lonlat[0] != coords_lonlat[-1]:
            coords_lonlat.append(coords_lonlat[0])

        features.append(
            {
                "type": "Feature",
                "properties": {},
                "geometry": {"type": "Polygon", "coordinates": [coords_lonlat]},
            }
        )

    plt.close()
    return {"type": "FeatureCollection", "features": features}


def main() -> None:
    ap = argparse.ArgumentParser(description="Predict next FireMask and export as GeoJSON polygons.")
    ap.add_argument("--model", required=True, help="Path to trained .keras model")
    ap.add_argument("--npz", required=True, help="Path to one unet_YYYY-MM-DD.npz sample")
    ap.add_argument("--center-lat", type=float, required=True)
    ap.add_argument("--center-lon", type=float, required=True)
    ap.add_argument("--radius-km", type=float, required=True)
    ap.add_argument("--pixels", type=int, default=64, help="Grid size (must match X H/W)")
    ap.add_argument("--threshold", type=float, default=0.7, help="Probability threshold to binarize")
    ap.add_argument("--out", required=True, help="Output GeoJSON path")
    args = ap.parse_args()

    import tensorflow as tf

    model = tf.keras.models.load_model(args.model, compile=False)
    X = load_npz_X(Path(args.npz))
    if X.shape[0] != args.pixels or X.shape[1] != args.pixels:
        raise SystemExit(f"X shape {X.shape} does not match --pixels {args.pixels}")

    pred = model.predict(X[None, ...], verbose=0)[0][..., 0]
    pred = np.clip(pred.astype(np.float32), 0.0, 1.0)
    mask01 = (pred >= float(args.threshold)).astype(np.uint8)

    bbox = grid_bbox_mercator(args.center_lat, args.center_lon, args.radius_km)
    fc = mask_to_polygons_geojson(mask01, bbox_merc=bbox)

    # Attach some metadata
    fc["properties"] = {
        "npz": str(args.npz),
        "model": str(args.model),
        "threshold": float(args.threshold),
        "center": {"lat": float(args.center_lat), "lon": float(args.center_lon)},
        "radius_km": float(args.radius_km),
        "pixels": int(args.pixels),
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(fc), encoding="utf-8")
    print(f"wrote={out.resolve()} features={len(fc['features'])}")


if __name__ == "__main__":
    main()

