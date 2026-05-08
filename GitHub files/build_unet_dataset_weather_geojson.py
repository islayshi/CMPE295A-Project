"""
Build U-Net-style training samples from:
  - Multi-city daily weather CSVs (manifest with lat/lon per station)
  - California historic fire perimeters GeoJSON → rasterized masks

Each sample (for calendar day d):
  - Weather: interpolated from station values on day d to a Mercator grid (same bbox as fire masks).
  - PrevFireMask: binary fire mask for day d-1 (zeros on d=first day of range).
  - y (FireMask label): binary fire mask for day d+1 ('next day spread' target).

Output: one compressed .npz per day with keys
  X: float32 (H, W, 12) — normalized like Next-Day Wildfire Spread / your U-Net script
  y: float32 (H, W, 1)
  date: str 'YYYY-MM-DD' (center day d)

Requires: pandas, numpy, matplotlib (for Path rasterize; same as geojson_to_firemask).

Example (Bay Area–wide grid centered between SF and SJ):
  python build_unet_dataset_weather_geojson.py ^
    --manifest bay_area_weather_manifest.csv ^
    --data-dir . ^
    --center-lat 37.55 --center-lon -122.15 --radius-km 120 --pixels 64 ^
    --date-start 2020-01-02 --date-end 2020-12-30 ^
    --out-dir unet_bay_area_2020
"""

from __future__ import annotations

import argparse
import os
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from geojson_to_firemask import (
    FireFeature,
    _load_candidate_features,
    build_firemask_for_day,
    _lonlat_to_web_mercator,
)

# Match wildfire_cnn_us_california.py
INPUT_FEATURES = [
    "elevation",
    "th",
    "vs",
    "tmmn",
    "tmmx",
    "sph",
    "pr",
    "pdsi",
    "NDVI",
    "population",
    "erc",
    "PrevFireMask",
]

DATA_STATS = {
    "elevation": (1233.0, 1064.0),
    "th": (212.0, 99.0),
    "vs": (3.9, 1.8),
    "tmmn": (281.0, 10.0),
    "tmmx": (298.0, 11.0),
    "sph": (0.0071, 0.0042),
    "pr": (0.5, 2.8),
    "pdsi": (-1.3, 2.5),
    "NDVI": (0.31, 0.21),
    "population": (61.0, 530.0),
    "erc": (52.0, 29.0),
    "PrevFireMask": (0.0, 1.0),
}


def _safe_float(x, default: float = 0.0) -> float:
    try:
        if x is None or (isinstance(x, float) and np.isnan(x)):
            return default
        if isinstance(x, str) and x.strip() == "":
            return default
        return float(x)
    except Exception:
        return default


def _normalize(name: str, grid: np.ndarray) -> np.ndarray:
    mean, std = DATA_STATS[name]
    if std <= 0 or name == "PrevFireMask":
        return grid.astype(np.float32)
    return ((grid - mean) / std).astype(np.float32)


def _mercator_pixel_grid(
    grid_bbox: Tuple[float, float, float, float], pixels: int
) -> Tuple[np.ndarray, np.ndarray]:
    """Pixel centers in Web Mercator meters, shape (pixels, pixels)."""
    minx, miny, maxx, maxy = grid_bbox
    w = max(1e-6, maxx - minx)
    h = max(1e-6, maxy - miny)
    xs = minx + (np.arange(pixels) + 0.5) * (w / pixels)
    ys = miny + (np.arange(pixels) + 0.5) * (h / pixels)
    XX, YY = np.meshgrid(xs, ys)
    return XX.astype(np.float32), YY.astype(np.float32)


def _idw(
    *,
    station_xy: np.ndarray,
    values: np.ndarray,
    grid_xx: np.ndarray,
    grid_yy: np.ndarray,
    power: float = 2.0,
    eps: float = 500.0,
) -> np.ndarray:
    """
    Inverse distance weighting. station_xy: (n, 2), values: (n,).
    eps: minimum distance (meters) to avoid blow-up.
    """
    n = station_xy.shape[0]
    if n == 0:
        return np.zeros_like(grid_xx, dtype=np.float32)
    if n == 1:
        return np.full_like(grid_xx, float(values[0]), dtype=np.float32)

    gx = grid_xx.reshape(-1, 1)
    gy = grid_yy.reshape(-1, 1)
    sx = station_xy[np.newaxis, :, 0]
    sy = station_xy[np.newaxis, :, 1]
    d2 = (gx - sx) ** 2 + (gy - sy) ** 2
    d = np.sqrt(np.maximum(d2, eps * eps))
    w = 1.0 / (d ** power)
    v = values.reshape(1, -1)
    num = (w * v).sum(axis=1)
    den = w.sum(axis=1)
    out = (num / np.maximum(den, 1e-12)).astype(np.float32)
    return out.reshape(grid_xx.shape)


def load_manifest_tables(
    manifest_path: Path,
    data_dir: Path,
) -> Tuple[pd.DataFrame, Dict[date, Dict[str, Dict[str, float]]]]:
    """
    Returns (manifest_df, weather_by_date)
    weather_by_date[d][city_key] = {tmin, tmax, wspd, wdir, prcp, ...}
    """
    man = pd.read_csv(manifest_path)
    for col in ("city", "lat", "lon", "csv"):
        if col not in man.columns:
            raise ValueError(f"Manifest must have columns city,lat,lon,csv; got {list(man.columns)}")

    # Coerce lat/lon (they may be blank initially). We'll validate later.
    man = man.copy()
    man["lat"] = pd.to_numeric(man["lat"], errors="coerce")
    man["lon"] = pd.to_numeric(man["lon"], errors="coerce")

    weather_by_date: Dict[date, Dict[str, Dict[str, float]]] = {}

    for _, row in man.iterrows():
        city = str(row["city"])
        csv_name = str(row["csv"])
        csv_path = data_dir / csv_name if not os.path.isabs(csv_name) else Path(csv_name)
        if not csv_path.is_file():
            raise FileNotFoundError(f"Missing weather file: {csv_path}")

        df = pd.read_csv(csv_path)
        if "date" not in df.columns:
            raise ValueError(f"{csv_path} missing 'date' column")
        df = df.copy()
        df["_d"] = pd.to_datetime(df["date"], errors="coerce").dt.date

        for _, r in df.iterrows():
            d = r["_d"]
            if d is pd.NaT or d is None:
                continue
            if not isinstance(d, date):
                continue
            if d not in weather_by_date:
                weather_by_date[d] = {}
            weather_by_date[d][city] = {
                "tmin": _safe_float(r.get("tmin"), 0.0),
                "tmax": _safe_float(r.get("tmax"), 0.0),
                "wspd": _safe_float(r.get("wspd"), 0.0),
                "wdir": _safe_float(r.get("wdir"), float("nan")),
                "prcp": _safe_float(r.get("prcp"), 0.0),
                "tavg": _safe_float(r.get("tavg"), 0.0),
                "pres": _safe_float(r.get("pres"), 1013.0),
            }

    return man, weather_by_date


def build_X_tensor(
    *,
    man: pd.DataFrame,
    weather_by_date: Dict[date, Dict[str, Dict[str, float]]],
    day: date,
    grid_bbox: Tuple[float, float, float, float],
    pixels: int,
    prev_fire: np.ndarray,
    static: Dict[str, float],
    idw_power: float = 2.0,
) -> np.ndarray:
    """12-channel tensor, last channel is PrevFireMask (not normalized)."""
    XX, YY = _mercator_pixel_grid(grid_bbox, pixels)
    station_xy_list: List[Tuple[float, float]] = []
    tmin_list: List[float] = []
    tmax_list: List[float] = []
    wspd_list: List[float] = []
    wdir_list: List[float] = []
    prcp_list: List[float] = []

    day_w = weather_by_date.get(day, {})
    for _, row in man.iterrows():
        city = str(row["city"])
        if not np.isfinite(row["lat"]) or not np.isfinite(row["lon"]):
            raise ValueError(
                f"Manifest is missing lat/lon for city='{city}'. "
                "Fill lat/lon in the manifest CSV before building gridded maps."
            )
        lat, lon = float(row["lat"]), float(row["lon"])
        mx, my = _lonlat_to_web_mercator(lon=lon, lat=lat)
        station_xy_list.append((mx, my))
        w = day_w.get(city, {})
        tmin_list.append(w.get("tmin", 0.0) + 273.15)
        tmax_list.append(w.get("tmax", 0.0) + 273.15)
        wspd_list.append(w.get("wspd", 0.0))
        wd = w.get("wdir", float("nan"))
        wdir_list.append(0.0 if not np.isfinite(wd) else float(wd))
        prcp_list.append(w.get("prcp", 0.0))

    pts = np.asarray(station_xy_list, dtype=np.float64)
    tmmn = _idw(
        station_xy=pts,
        values=np.asarray(tmin_list, dtype=np.float64),
        grid_xx=XX,
        grid_yy=YY,
        power=idw_power,
    )
    tmmx = _idw(
        station_xy=pts,
        values=np.asarray(tmax_list, dtype=np.float64),
        grid_xx=XX,
        grid_yy=YY,
        power=idw_power,
    )
    vs = _idw(
        station_xy=pts,
        values=np.asarray(wspd_list, dtype=np.float64),
        grid_xx=XX,
        grid_yy=YY,
        power=idw_power,
    )
    th = _idw(
        station_xy=pts,
        values=np.asarray(wdir_list, dtype=np.float64),
        grid_xx=XX,
        grid_yy=YY,
        power=idw_power,
    )
    pr = _idw(
        station_xy=pts,
        values=np.asarray(prcp_list, dtype=np.float64),
        grid_xx=XX,
        grid_yy=YY,
        power=idw_power,
    )

    H, W = pixels, pixels
    elev = np.full((H, W), static.get("elevation", 150.0), dtype=np.float32)
    sph = np.full((H, W), static.get("sph", 0.0071), dtype=np.float32)
    pdsi = np.full((H, W), static.get("pdsi", 0.0), dtype=np.float32)
    ndvi = np.full((H, W), static.get("NDVI", 0.31), dtype=np.float32)
    pop = np.full((H, W), static.get("population", 200.0), dtype=np.float32)
    erc = np.full((H, W), static.get("erc", 52.0), dtype=np.float32)

    prev = prev_fire.astype(np.float32)
    if prev.shape != (H, W):
        raise ValueError(f"prev_fire shape {prev.shape} != ({H},{W})")

    layers = {
        "elevation": elev,
        "th": th.astype(np.float32),
        "vs": vs.astype(np.float32),
        "tmmn": tmmn.astype(np.float32),
        "tmmx": tmmx.astype(np.float32),
        "sph": sph,
        "pr": pr.astype(np.float32),
        "pdsi": pdsi,
        "NDVI": ndvi,
        "population": pop,
        "erc": erc,
        "PrevFireMask": prev,
    }

    chans = []
    for name in INPUT_FEATURES:
        chans.append(_normalize(name, layers[name])[..., None])
    return np.concatenate(chans, axis=-1).astype(np.float32)


def main() -> None:
    ap = argparse.ArgumentParser(description="Build U-Net .npz samples from manifest weather + GeoJSON.")
    ap.add_argument("--manifest", default="bay_area_weather_manifest.csv")
    ap.add_argument("--data-dir", default=".", help="Directory containing CSV files listed in manifest.")
    ap.add_argument(
        "--geojson",
        default="California_Historic_Fire_Perimeters_-4891938132824355098.geojson",
    )
    ap.add_argument("--center-lat", type=float, required=True)
    ap.add_argument("--center-lon", type=float, required=True)
    ap.add_argument("--radius-km", type=float, default=120.0)
    ap.add_argument("--pixels", type=int, default=64)
    ap.add_argument("--date-start", default="2020-01-02")
    ap.add_argument("--date-end", default="2020-12-30")
    ap.add_argument("--out-dir", default="unet_bay_area_2020")
    ap.add_argument("--max-samples", type=int, default=0, help="0 = no limit.")
    ap.add_argument(
        "--idw-power",
        type=float,
        default=2.0,
        help="Inverse-distance weighting power.",
    )
    args = ap.parse_args()

    root = Path(__file__).resolve().parent
    manifest_path = Path(args.manifest) if os.path.isabs(args.manifest) else root / args.manifest
    data_dir = Path(args.data_dir) if os.path.isabs(args.data_dir) else root / args.data_dir
    geo_path = Path(args.geojson) if os.path.isabs(args.geojson) else root / args.geojson
    out_dir = Path(args.out_dir) if os.path.isabs(args.out_dir) else root / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    man, weather_by_date = load_manifest_tables(manifest_path, data_dir)
    print(f"stations={len(man)} dates_with_any_weather={len(weather_by_date)}")

    candidates, grid_bbox = _load_candidate_features(
        str(geo_path),
        center_lat=args.center_lat,
        center_lon=args.center_lon,
        radius_km=args.radius_km,
    )
    print(f"geojson_candidates={len(candidates)} grid_bbox_merc=(...) pixels={args.pixels}")

    d0 = pd.to_datetime(args.date_start).date()
    d1 = pd.to_datetime(args.date_end).date()
    if d1 < d0:
        raise SystemExit("date-end must be >= date-start")

    static = {"elevation": 200.0, "sph": 0.0071, "pdsi": -0.5, "NDVI": 0.35, "population": 250.0, "erc": 48.0}

    n_written = 0
    d = d0
    while d <= d1:
        d_prev = d - timedelta(days=1)
        d_next = d + timedelta(days=1)

        mask_prev = build_firemask_for_day(
            candidates=candidates, day=d_prev, grid_bbox_merc=grid_bbox, pixels=args.pixels
        )
        mask_next = build_firemask_for_day(
            candidates=candidates, day=d_next, grid_bbox_merc=grid_bbox, pixels=args.pixels
        )

        if d not in weather_by_date:
            d += timedelta(days=1)
            continue

        prev_f = mask_prev.astype(np.float32)
        if prev_f.max() > 1.5:
            prev_f = prev_f / 255.0

        X = build_X_tensor(
            man=man,
            weather_by_date=weather_by_date,
            day=d,
            grid_bbox=grid_bbox,
            pixels=args.pixels,
            prev_fire=prev_f,
            static=static,
            idw_power=args.idw_power,
        )
        # Masks are 0/1 uint8
        y = (mask_next.astype(np.float32) / 255.0) if mask_next.max() > 1 else mask_next.astype(np.float32)
        y = np.clip(y, 0.0, 1.0)[..., np.newaxis]

        out_path = out_dir / f"unet_{d.isoformat()}.npz"
        np.savez_compressed(out_path, X=X, y=y, date=np.array(d.isoformat()))
        n_written += 1
        if args.max_samples and n_written >= args.max_samples:
            break
        d += timedelta(days=1)

    print(f"wrote_samples={n_written} out_dir={out_dir}")


if __name__ == "__main__":
    main()
