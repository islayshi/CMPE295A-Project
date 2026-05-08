import argparse
import json
from datetime import datetime, date
from typing import Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd


def _parse_alarm_date(s: str) -> Optional[date]:
    """
    Example: 'Tue, 07 Jan 2025 08:00:00 GMT'
    """
    if not s or not isinstance(s, str):
        return None
    try:
        dt = datetime.strptime(s, "%a, %d %b %Y %H:%M:%S %Z")
        return dt.date()
    except Exception:
        return None


def _parse_cont_date(s: str) -> Optional[date]:
    # Same format as alarm date in this dataset.
    return _parse_alarm_date(s)


def _deg_buffer_for_km(lat: float, radius_km: float) -> Tuple[float, float]:
    """
    Approximate degrees buffer for a small radius around a point.
    Returns (dlat, dlon).
    """
    dlat = radius_km / 111.0
    dlon = radius_km / (111.0 * max(0.1, np.cos(np.deg2rad(lat))))
    return float(dlat), float(dlon)


def _lonlat_to_web_mercator(lon: float, lat: float) -> Tuple[float, float]:
    """
    Convert lon/lat in degrees to Web Mercator (EPSG:3857) meters.
    """
    # Clamp latitude to Mercator limits
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
    Compute bbox (min_lon, min_lat, max_lon, max_lat) for Polygon/MultiPolygon.
    Works directly from coordinates without shapely/geopandas.
    """
    if not geom:
        return None
    gtype = geom.get("type")
    coords = geom.get("coordinates")
    if not coords:
        return None

    lons = []
    lats = []

    def add_ring(ring):
        for lon, lat in ring:
            lons.append(lon)
            lats.append(lat)

    if gtype == "Polygon":
        for ring in coords:
            add_ring(ring)
    elif gtype == "MultiPolygon":
        for poly in coords:
            for ring in poly:
                add_ring(ring)
    else:
        return None

    if not lons:
        return None
    return (min(lons), min(lats), max(lons), max(lats))


def _infer_crs_is_web_mercator(sample_bbox: Tuple[float, float, float, float]) -> bool:
    """
    Heuristic: if coordinate magnitudes look like meters (e.g., ~1e6 to 1e7),
    treat as Web Mercator. If they look like degrees, treat as lon/lat.
    """
    minx, miny, maxx, maxy = sample_bbox
    # Degrees should be roughly within [-180, 180] and [-90, 90]
    if all(abs(v) <= 360.0 for v in [minx, maxx]) and all(abs(v) <= 180.0 for v in [miny, maxy]):
        return False
    return True


def _load_candidate_fires(
    geojson_path: str,
    *,
    lat: float,
    lon: float,
    radius_km: float,
) -> List[Tuple[date, Optional[date]]]:
    """
    Returns list of (alarm_date, cont_date) for fires whose geometry bbox intersects
    the query point buffer bbox. This is a fast prefilter; it's not a true spatial
    intersection test.
    """
    with open(geojson_path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    feats = obj.get("features", [])

    # Determine coordinate system from first usable bbox
    sample_bbox = None
    for feat in feats[:50]:
        bbox = _feature_bbox((feat.get("geometry") or {}))
        if bbox is not None:
            sample_bbox = bbox
            break
    if sample_bbox is None:
        return []
    is_merc = _infer_crs_is_web_mercator(sample_bbox)

    if is_merc:
        qx, qy = _lonlat_to_web_mercator(lon=lon, lat=lat)
        b = _meters_buffer_for_km(radius_km)
        query_bbox = (qx - b, qy - b, qx + b, qy + b)
    else:
        dlat, dlon = _deg_buffer_for_km(lat, radius_km)
        query_bbox = (lon - dlon, lat - dlat, lon + dlon, lat + dlat)

    out: List[Tuple[date, Optional[date]]] = []
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
        cont = _parse_cont_date(props.get("CONT_DATE"))
        out.append((alarm, cont))

    return out


def build_labels_for_dates(
    dates: Iterable[date],
    *,
    candidate_fires: List[Tuple[date, Optional[date]]],
) -> pd.DataFrame:
    """
    Creates fire_start and fire_present labels for each date.
    - fire_start(d) = 1 if any candidate fire alarm_date == d
    - fire_present(d) = 1 if any candidate fire is active on d
      (alarm_date <= d <= cont_date if cont_date exists, else alarm_date == d)
    """
    # Pre-index starts and active ranges
    starts = {}
    ranges: List[Tuple[date, date]] = []
    for alarm, cont in candidate_fires:
        starts[alarm] = starts.get(alarm, 0) + 1
        if cont is not None and cont >= alarm:
            ranges.append((alarm, cont))
        else:
            ranges.append((alarm, alarm))

    rows = []
    for d in dates:
        fire_start = 1 if starts.get(d, 0) > 0 else 0
        fire_present = 0
        for a, c in ranges:
            if a <= d <= c:
                fire_present = 1
                break
        rows.append({"date": d.isoformat(), "fire_start": fire_start, "fire_present": fire_present})
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Create binary fire/no-fire labels from CA historic perimeter GeoJSON for a given point + radius."
    )
    ap.add_argument("--geojson", required=True, help="Path to California Historic Fire Perimeters GeoJSON")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--weather-csv", help="Weather time-series CSV (must include a date column)")
    src.add_argument(
        "--date-range",
        nargs=2,
        metavar=("START", "END"),
        help="Generate labels for this date range (YYYY-MM-DD YYYY-MM-DD), inclusive.",
    )
    ap.add_argument("--date-col", default="date", help="Date column name in weather CSV")
    ap.add_argument("--lat", type=float, required=True, help="Latitude of the point (e.g., city/station)")
    ap.add_argument("--lon", type=float, required=True, help="Longitude of the point")
    ap.add_argument("--radius-km", type=float, default=25.0, help="Radius around point to consider (km)")
    ap.add_argument("--out", default="fire_labels.csv", help="Output CSV path")
    args = ap.parse_args()

    if args.weather_csv:
        w = pd.read_csv(args.weather_csv)
        if args.date_col not in w.columns:
            raise SystemExit(f"Weather CSV missing date column '{args.date_col}'. Columns: {list(w.columns)}")

        dt = pd.to_datetime(w[args.date_col], errors="coerce")
        if dt.isna().all():
            raise SystemExit(f"Could not parse any dates from column '{args.date_col}'.")
        w["_date_only"] = dt.dt.date

        unique_dates = sorted(set(d for d in w["_date_only"].tolist() if d is not None))
        print(f"weather_rows={len(w)} unique_dates={len(unique_dates)}")
    else:
        start_s, end_s = args.date_range
        start_d = pd.to_datetime(start_s).date()
        end_d = pd.to_datetime(end_s).date()
        if end_d < start_d:
            raise SystemExit("END must be >= START")
        unique_dates = [d.date() for d in pd.date_range(start_d, end_d, freq="D")]
        w = pd.DataFrame({"date": [d.isoformat() for d in unique_dates]})
        w["_date_only"] = pd.to_datetime(w["date"]).dt.date
        print(f"date_range_days={len(unique_dates)} start={start_d} end={end_d}")

    candidates = _load_candidate_fires(args.geojson, lat=args.lat, lon=args.lon, radius_km=args.radius_km)
    print(f"candidate_fires_prefiltered={len(candidates)} (bbox filter only; radius_km={args.radius_km})")

    labels = build_labels_for_dates(unique_dates, candidate_fires=candidates)
    out = w.merge(labels, left_on=w["_date_only"].astype(str), right_on="date", how="left")
    out = out.drop(columns=["_date_only"])
    out["fire_start"] = out["fire_start"].fillna(0).astype(int)
    out["fire_present"] = out["fire_present"].fillna(0).astype(int)

    out.to_csv(args.out, index=False)
    print(f"wrote={args.out}")


if __name__ == "__main__":
    main()

