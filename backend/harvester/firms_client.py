"""
NASA FIRMS Satellite Client — Fight Fire With AI
=================================================
Fetches active fire detections (VIIRS 375m), suppresses refinery false-alarms,
and clusters nearby hotspots into fire incident envelopes for ML inference.
"""
from __future__ import annotations

import csv
import io
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import requests

logger = logging.getLogger(__name__)

BAY_AREA_BBOX = (-122.9, 36.9, -121.5, 38.3)
CALIFORNIA_BOUNDS = (-124.5, 32.5, -114.0, 42.1)

# Known East Bay industrial flaring sites (lat, lon, exclusion radius km)
REFINERY_ZONES: list[tuple[str, float, float, float]] = [
    ("Richmond", 37.9358, -122.3858, 2.5),
    ("Rodeo", 38.0336, -122.2547, 2.5),
    ("Martinez", 38.0194, -122.1336, 2.5),
    ("Benicia", 38.0642, -122.1481, 2.5),
]

VIIRS_AREA_API_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/VIIRS_SNPP_NRT/{bbox}/1"
VIIRS_24H_CSV_URL = "https://firms.modaps.eosdis.nasa.gov/data/active_fire/suomi-npp-viirs-c2/csv/SUOMI_VIIRS_C2_USA_contiguous_and_Hawaii_24h.csv"


@dataclass
class FireCluster:
    cluster_id: int
    centroid_lat: float
    centroid_lon: float
    count: int
    bbox: list[float]  # [w, s, e, n]
    points: list[dict[str, Any]] = field(default_factory=list)


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates great-circle distance between two coordinates in kilometers."""
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return r * c


def is_near_refinery(lat: float, lon: float) -> bool:
    """Returns True if the coordinate is within the exclusion radius of a known refinery."""
    for name, r_lat, r_lon, radius_km in REFINERY_ZONES:
        dist = haversine_distance_km(lat, lon, r_lat, r_lon)
        if dist <= radius_km:
            logger.info("Dropping hotspot at (%.4f, %.4f): within %.1f km of %s refinery", lat, lon, dist, name)
            return True
    return False


def parse_firms_csv(csv_text: str) -> list[dict[str, Any]]:
    """Parses raw NASA FIRMS CSV text into a list of row dictionaries."""
    rows: list[dict[str, Any]] = []
    reader = csv.DictReader(io.StringIO(csv_text.strip()))
    for row in reader:
        try:
            parsed = {
                "latitude": float(row["latitude"]),
                "longitude": float(row["longitude"]),
                "confidence": str(row.get("confidence", "nominal")).lower(),
                "frp": float(row.get("frp", 0.0)) if row.get("frp") else 0.0,
                "acq_date": row.get("acq_date", ""),
                "acq_time": row.get("acq_time", ""),
            }
            rows.append(parsed)
        except (ValueError, KeyError) as exc:
            logger.debug("Skipping invalid FIRMS row %s: %s", row, exc)
    return rows


def filter_hotspots(
    rows: list[dict[str, Any]],
    bbox: tuple[float, float, float, float] = BAY_AREA_BBOX,
) -> list[dict[str, Any]]:
    """Filters FIRMS detections by geographic bounds, confidence, and refinery exclusion."""
    min_lon, min_lat, max_lon, max_lat = bbox
    valid_points: list[dict[str, Any]] = []

    for pt in rows:
        lat = pt["latitude"]
        lon = pt["longitude"]

        # Geographic bounds check
        if not (min_lat <= lat <= max_lat and min_lon <= lon <= max_lon):
            continue

        # Confidence check (reject low confidence)
        conf = pt["confidence"]
        if conf in ("low", "l"):
            continue
        try:
            if float(conf) < 50.0:
                continue
        except ValueError:
            pass

        # Industrial flare check
        if is_near_refinery(lat, lon):
            continue

        valid_points.append(pt)

    return valid_points


def cluster_hotspots(
    points: list[dict[str, Any]],
    radius_km: float = 3.0,
    buffer_km: float = 25.0,
) -> list[FireCluster]:
    """
    Clusters nearby hotspot points into distinct fire incidents and calculates
    padded bounding boxes (+buffer_km) suitable for ML spread modeling.
    """
    if not points:
        return []

    # Simple greedy distance clustering
    assigned: set[int] = set()
    clusters_points: list[list[dict[str, Any]]] = []

    for i, pt_a in enumerate(points):
        if i in assigned:
            continue
        cluster = [pt_a]
        assigned.add(i)

        for j, pt_b in enumerate(points):
            if j in assigned:
                continue
            dist = haversine_distance_km(pt_a["latitude"], pt_a["longitude"], pt_b["latitude"], pt_b["longitude"])
            if dist <= radius_km:
                cluster.append(pt_b)
                assigned.add(j)

        clusters_points.append(cluster)

    # Convert clusters to FireCluster with buffered bounding box
    result: list[FireCluster] = []
    # Approximate degree conversions around 38N
    lat_deg_pad = buffer_km / 111.0
    lon_deg_pad = buffer_km / (111.0 * math.cos(math.radians(38.0)))

    for cluster_id, c_pts in enumerate(clusters_points, start=1):
        lats = [p["latitude"] for p in c_pts]
        lons = [p["longitude"] for p in c_pts]

        c_lat = sum(lats) / len(lats)
        c_lon = sum(lons) / len(lons)

        min_lon = max(CALIFORNIA_BOUNDS[0], min(lons) - lon_deg_pad)
        min_lat = max(CALIFORNIA_BOUNDS[1], min(lats) - lat_deg_pad)
        max_lon = min(CALIFORNIA_BOUNDS[2], max(lons) + lon_deg_pad)
        max_lat = min(CALIFORNIA_BOUNDS[3], max(lats) + lat_deg_pad)

        result.append(
            FireCluster(
                cluster_id=cluster_id,
                centroid_lat=round(c_lat, 4),
                centroid_lon=round(c_lon, 4),
                count=len(c_pts),
                bbox=[round(min_lon, 4), round(min_lat, 4), round(max_lon, 4), round(max_lat, 4)],
                points=c_pts,
            )
        )

    return result


def fetch_bay_area_hotspots(
    firms_map_key: str = "",
    bbox: tuple[float, float, float, float] = BAY_AREA_BBOX,
    timeout: float = 30.0,
) -> list[FireCluster]:
    """
    Fetches active fire hotspots using NASA FIRMS Area API if key is available,
    otherwise falling back to keyless 24h VIIRS CSV, and returns clustered fires.
    """
    key = firms_map_key.strip()
    if key:
        bbox_str = f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}"
        url = VIIRS_AREA_API_URL.format(key=key, bbox=bbox_str)
        logger.info("Fetching FIRMS Area API: %s", url)
    else:
        url = VIIRS_24H_CSV_URL
        logger.info("Fetching public keyless FIRMS CSV: %s", url)

    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()

    all_rows = parse_firms_csv(resp.text)
    filtered = filter_hotspots(all_rows, bbox=bbox)
    return cluster_hotspots(filtered)
