import argparse
import json
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd


def _parse_alarm_date(s: str) -> Optional[date]:
    # Example in your GeoJSON: 'Tue, 07 Jan 2025 08:00:00 GMT'
    if not s or not isinstance(s, str):
        return None
    try:
        return datetime.strptime(s, "%a, %d %b %Y %H:%M:%S %Z").date()
    except Exception:
        return None


def _lonlat_to_web_mercator(lon: float, lat: float) -> Tuple[float, float]:
    # EPSG:3857 (meters). Same conversion used in make_fire_labels_from_perimeters.py
    lat = float(np.clip(lat, -85.05112878, 85.05112878))
    lon = float(lon)
    r = 6378137.0
    x = r * np.deg2rad(lon)
    y = r * np.log(np.tan(np.pi / 4.0 + np.deg2rad(lat) / 2.0))
    return float(x), float(y)


def _meters_buffer_for_km(radius_km: float) -> float:
    return float(radius_km * 1000.0)


def _bbox_intersects(
    bbox: Tuple[float, float, float, float], query: Tuple[float, float, float, float]
) -> bool:
    minx, miny, maxx, maxy = bbox
    qminx, qminy, qmaxx, qmaxy = query
    return not (maxx < qminx or minx > qmaxx or maxy < qminy or miny > qmaxy)


def _feature_bbox(geom: dict) -> Optional[Tuple[float, float, float, float]]:
    """
    Compute bbox (minx, miny, maxx, maxy) for Polygon/MultiPolygon.
    Works directly from coordinates without shapely/geopandas.
    """
    if not geom:
        return None
    gtype = geom.get("type")
    coords = geom.get("coordinates")
    if not coords:
        return None

    xs: List[float] = []
    ys: List[float] = []

    def add_ring(ring):
        for x, y in ring:
            xs.append(float(x))
            ys.append(float(y))

    if gtype == "Polygon":
        for ring in coords:
            add_ring(ring)
    elif gtype == "MultiPolygon":
        for poly in coords:
            for ring in poly:
                add_ring(ring)
    else:
        return None

    if not xs:
        return None
    return (min(xs), min(ys), max(xs), max(ys))


def _iter_polygons_xy(geom: dict) -> Iterable[List[List[Tuple[float, float]]]]:
    """
    Yield polygons as list-of-rings, each ring is list[(x,y)].
    Supports Polygon and MultiPolygon.
    """
    gtype = (geom or {}).get("type")
    coords = (geom or {}).get("coordinates") or []
    if gtype == "Polygon":
        yield [[(float(x), float(y)) for x, y in ring] for ring in coords]
    elif gtype == "MultiPolygon":
        for poly in coords:
            yield [[(float(x), float(y)) for x, y in ring] for ring in poly]


def _rings_to_mask(
    *,
    rings: List[List[Tuple[float, float]]],
    bbox: Tuple[float, float, float, float],
    pixels: int,
) -> np.ndarray:
    """
    Rasterize a single polygon (with possible holes).
    Implementation uses matplotlib.path.Path to avoid heavy geo deps.
    """
    from matplotlib.path import Path

    minx, miny, maxx, maxy = bbox
    w = max(1e-6, (maxx - minx))
    h = max(1e-6, (maxy - miny))

    # Pixel centers in world coords
    xs = minx + (np.arange(pixels) + 0.5) * (w / pixels)
    ys = miny + (np.arange(pixels) + 0.5) * (h / pixels)
    XX, YY = np.meshgrid(xs, ys)
    pts = np.stack([XX.reshape(-1), YY.reshape(-1)], axis=1)

    def ring_path(ring_xy: List[Tuple[float, float]]) -> Path:
        verts = np.asarray(ring_xy, dtype=np.float64)
        if len(verts) < 3:
            # Degenerate
            verts = np.zeros((0, 2), dtype=np.float64)
        return Path(verts, closed=True)

    # Outer ring fills; inner rings subtract (holes)
    outer = ring_path(rings[0]) if rings else None
    if outer is None:
        return np.zeros((pixels, pixels), dtype=np.uint8)

    inside = outer.contains_points(pts).reshape(pixels, pixels)
    if len(rings) > 1:
        for hole in rings[1:]:
            hp = ring_path(hole)
            inside_hole = hp.contains_points(pts).reshape(pixels, pixels)
            inside = np.logical_and(inside, ~inside_hole)

    # Note: ys increases upward; image row 0 is "top". Flip vertically for nicer plotting.
    return inside[::-1].astype(np.uint8)


@dataclass
class FireFeature:
    alarm: date
    cont: date
    geom: dict
    bbox: Tuple[float, float, float, float]


def _load_candidate_features(
    geojson_path: str,
    *,
    center_lat: float,
    center_lon: float,
    radius_km: float,
) -> Tuple[List[FireFeature], Tuple[float, float, float, float]]:
    """
    Load features and prefilter by bbox around center point.
    Returns (candidates, query_bbox_mercator).
    """
    cx, cy = _lonlat_to_web_mercator(lon=center_lon, lat=center_lat)
    b = _meters_buffer_for_km(radius_km)
    query_bbox = (cx - b, cy - b, cx + b, cy + b)

    with open(geojson_path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    feats = obj.get("features", [])

    out: List[FireFeature] = []
    for feat in feats:
        geom = feat.get("geometry") or {}
        bbox = _feature_bbox(geom)
        if bbox is None:
            continue
        if not _bbox_intersects(bbox, query_bbox):
            continue
        props = feat.get("properties") or {}
        alarm = _parse_alarm_date(props.get("ALARM_DATE"))
        if alarm is None:
            continue
        cont = _parse_alarm_date(props.get("CONT_DATE")) or alarm
        if cont < alarm:
            cont = alarm
        out.append(FireFeature(alarm=alarm, cont=cont, geom=geom, bbox=bbox))
    return out, query_bbox


def _dates_from_weather_csv(path: str, date_col: str) -> List[date]:
    df = pd.read_csv(path)
    if date_col not in df.columns:
        raise ValueError(f"Weather CSV missing '{date_col}'. Have: {list(df.columns)}")
    dt = pd.to_datetime(df[date_col], errors="coerce")
    if dt.isna().all():
        raise ValueError(f"Could not parse any dates from '{date_col}'")
    days = sorted(set(d.date() for d in dt.dropna().tolist()))
    return days


def _dates_from_range(start: str, end: str) -> List[date]:
    s = pd.to_datetime(start).date()
    e = pd.to_datetime(end).date()
    if e < s:
        raise ValueError("END must be >= START")
    out = []
    d = s
    while d <= e:
        out.append(d)
        d = d + timedelta(days=1)
    return out


def build_firemask_for_day(
    *,
    candidates: List[FireFeature],
    day: date,
    grid_bbox_merc: Tuple[float, float, float, float],
    pixels: int,
) -> np.ndarray:
    """
    Returns mask shape (pixels, pixels), uint8 in {0,1}.
    """
    acc = np.zeros((pixels, pixels), dtype=np.uint8)
    for feat in candidates:
        if not (feat.alarm <= day <= feat.cont):
            continue
        # Quick reject: feature bbox doesn't intersect our raster bbox
        if not _bbox_intersects(feat.bbox, grid_bbox_merc):
            continue
        for poly_rings in _iter_polygons_xy(feat.geom):
            m = _rings_to_mask(rings=poly_rings, bbox=grid_bbox_merc, pixels=pixels)
            acc = np.maximum(acc, m)
    return acc


def save_mask_png(mask: np.ndarray, out_path: str) -> None:
    import matplotlib.pyplot as plt

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    plt.imsave(out_path, mask, cmap="Reds", vmin=0, vmax=1)


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Rasterize CA fire perimeter GeoJSON into daily FireMask images (binary)."
    )
    ap.add_argument(
        "--geojson",
        default="California_Historic_Fire_Perimeters_-4891938132824355098.geojson",
        help="Path to perimeter GeoJSON (Web Mercator coordinates).",
    )
    ap.add_argument("--weather-csv", default=None, help="Optional weather CSV with a date column.")
    ap.add_argument("--date-col", default="date", help="Date column name (default: date)")
    ap.add_argument(
        "--date-range",
        nargs=2,
        metavar=("START", "END"),
        default=None,
        help="Optional explicit date range YYYY-MM-DD YYYY-MM-DD (inclusive).",
    )
    ap.add_argument("--lat", type=float, required=True, help="Center latitude (e.g., LA ~ 34.05)")
    ap.add_argument("--lon", type=float, required=True, help="Center longitude (e.g., LA ~ -118.24)")
    ap.add_argument("--radius-km", type=float, default=50.0, help="Half-width of square raster in km.")
    ap.add_argument("--pixels", type=int, default=64, help="Image size in pixels (default: 64).")
    ap.add_argument("--out-dir", default="firemasks", help="Output directory for PNG masks.")
    ap.add_argument(
        "--also-prev-mask",
        action="store_true",
        help="Also write PrevFireMask (previous day's mask) alongside FireMask.",
    )
    args = ap.parse_args()

    if (args.weather_csv is None) == (args.date_range is None):
        raise SystemExit("Provide exactly one of --weather-csv or --date-range")

    if args.weather_csv:
        days = _dates_from_weather_csv(args.weather_csv, args.date_col)
    else:
        start, end = args.date_range
        days = _dates_from_range(start, end)

    print(f"days={len(days)} first={days[0]} last={days[-1]}")

    candidates, query_bbox = _load_candidate_features(
        args.geojson, center_lat=args.lat, center_lon=args.lon, radius_km=args.radius_km
    )
    print(f"candidate_features_prefiltered={len(candidates)} within_bbox_km={args.radius_km}")

    # Our raster bbox is the same as the query bbox (square around the point)
    grid_bbox = query_bbox

    prev_mask = None
    for d in days:
        mask = build_firemask_for_day(
            candidates=candidates, day=d, grid_bbox_merc=grid_bbox, pixels=args.pixels
        )
        out_fire = os.path.join(args.out_dir, f"FireMask_{d.isoformat()}.png")
        save_mask_png(mask, out_fire)

        if args.also_prev_mask:
            if prev_mask is None:
                prev_mask = np.zeros_like(mask)
            out_prev = os.path.join(args.out_dir, f"PrevFireMask_{d.isoformat()}.png")
            save_mask_png(prev_mask, out_prev)
            prev_mask = mask

    print(f"wrote_masks_dir={args.out_dir}")


if __name__ == "__main__":
    main()

