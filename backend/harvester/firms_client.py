"""
NASA FIRMS Satellite Client — Fight Fire With AI
=================================================
Fetches active fire detections (VIIRS 375m across Suomi-NPP, NOAA-20, NOAA-21),
suppresses petrochemical refinery and landfill flares, clusters nearby wildland hotspots
into fire incident envelopes for ML inference, and provides raw telemetry hotspots.
"""
from __future__ import annotations

import csv
import io
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any

import requests

logger = logging.getLogger(__name__)

BAY_AREA_BBOX = (-122.9, 36.9, -121.5, 38.5)
CALIFORNIA_BOUNDS = (-124.5, 32.5, -114.0, 42.1)

# Known East Bay and South Bay industrial flaring sites (name, lat, lon, exclusion radius km)
REFINERY_ZONES: list[tuple[str, float, float, float]] = [
    ("Chevron Richmond Refinery", 37.9358, -122.3858, 2.5),
    ("Phillips 66 Rodeo Refinery", 38.0336, -122.2547, 2.5),
    ("Martinez Refining Co.", 38.0194, -122.1336, 2.5),
    ("Valero Benicia Refinery", 38.0642, -122.1481, 2.5),
    ("Newby Island Landfill (Alviso)", 37.4557, -121.9323, 2.5),
]

VIIRS_SOURCES = ["VIIRS_SNPP_NRT", "VIIRS_NOAA20_NRT", "VIIRS_NOAA21_NRT"]

VIIRS_AREA_API_URL_TEMPLATE = "https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/{source}/{bbox}/2"
VIIRS_AREA_API_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/VIIRS_SNPP_NRT/{bbox}/2"

VIIRS_KEYLESS_CSV_URLS = {
    "VIIRS_SNPP_NRT": "https://firms.modaps.eosdis.nasa.gov/data/active_fire/suomi-npp-viirs-c2/csv/SUOMI_VIIRS_C2_USA_contiguous_and_Hawaii_24h.csv",
    "VIIRS_NOAA20_NRT": "https://firms.modaps.eosdis.nasa.gov/data/active_fire/noaa-20-viirs-c2/csv/J1_VIIRS_C2_USA_contiguous_and_Hawaii_24h.csv",
    "VIIRS_NOAA21_NRT": "https://firms.modaps.eosdis.nasa.gov/data/active_fire/noaa-21-viirs-c2/csv/J2_VIIRS_C2_USA_contiguous_and_Hawaii_24h.csv",
}
VIIRS_24H_CSV_URL = VIIRS_KEYLESS_CSV_URLS["VIIRS_SNPP_NRT"]

SENSOR_DISPLAY_NAMES = {
    "VIIRS_SNPP_NRT": "Suomi-NPP",
    "VIIRS_NOAA20_NRT": "NOAA-20",
    "VIIRS_NOAA21_NRT": "NOAA-21",
    "N": "Suomi-NPP",
    "SNPP": "Suomi-NPP",
    "1": "NOAA-20",
    "J1": "NOAA-20",
    "N20": "NOAA-20",
    "JPSS-1": "NOAA-20",
    "NOAA-20": "NOAA-20",
    "2": "NOAA-21",
    "J2": "NOAA-21",
    "N21": "NOAA-21",
    "JPSS-2": "NOAA-21",
    "NOAA-21": "NOAA-21",
}


@dataclass
class FireCluster:
    cluster_id: int
    centroid_lat: float
    centroid_lon: float
    count: int
    bbox: list[float]  # [w, s, e, n]
    points: list[dict[str, Any]] = field(default_factory=list)


class FireClusterResult(list):
    """
    Subclass of list holding FireCluster instances.
    Preserves backwards compatibility with list[FireCluster] while attaching
    raw_hotspots metadata containing both wildland detections and suppressed flares.
    """
    def __init__(self, clusters: list[FireCluster] | None = None, raw_hotspots: list[dict[str, Any]] | None = None):
        super().__init__(clusters or [])
        self.raw_hotspots: list[dict[str, Any]] = raw_hotspots or []


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


def check_refinery_zone(lat: float, lon: float) -> tuple[bool, str | None]:
    """Returns (True, site_name) if coordinate is within radius of a known refinery/landfill."""
    for name, r_lat, r_lon, radius_km in REFINERY_ZONES:
        dist = haversine_distance_km(lat, lon, r_lat, r_lon)
        if dist <= radius_km:
            return True, name
    return False, None


def is_near_refinery(lat: float, lon: float) -> bool:
    """Returns True if the coordinate is within the exclusion radius of a known refinery/landfill."""
    is_flare, name = check_refinery_zone(lat, lon)
    if is_flare:
        logger.info("Dropping hotspot at (%.4f, %.4f): within refinery/landfill zone %s", lat, lon, name)
    return is_flare


def is_valid_firms_csv(csv_text: str) -> bool:
    """Checks whether the response body looks like a valid FIRMS CSV rather than an error or HTML."""
    if not csv_text or not csv_text.strip():
        return False
    stripped = csv_text.strip()
    if stripped.startswith(("Invalid", "Error", "Bad Request", "<!DOCTYPE", "<html", "<?xml")):
        return False
    first_line = stripped.splitlines()[0].lower()
    return "latitude" in first_line and "longitude" in first_line


def parse_firms_csv(csv_text: str, default_source: str = "") -> list[dict[str, Any]]:
    """Parses raw NASA FIRMS CSV text into a list of row dictionaries."""
    if not is_valid_firms_csv(csv_text):
        return []

    rows: list[dict[str, Any]] = []
    reader = csv.DictReader(io.StringIO(csv_text.strip()))
    for row in reader:
        try:
            raw_sat = str(row.get("satellite") or "").strip()
            if raw_sat and raw_sat in SENSOR_DISPLAY_NAMES:
                sat_display = SENSOR_DISPLAY_NAMES[raw_sat]
            elif default_source and default_source in SENSOR_DISPLAY_NAMES:
                sat_display = SENSOR_DISPLAY_NAMES[default_source]
            elif default_source:
                sat_display = default_source
            else:
                raw_fallback = str(row.get("instrument") or "VIIRS").strip()
                sat_display = SENSOR_DISPLAY_NAMES.get(raw_fallback, raw_fallback)

            parsed = {
                "latitude": float(row["latitude"]),
                "longitude": float(row["longitude"]),
                "confidence": str(row.get("confidence", "nominal")).lower(),
                "frp": float(row.get("frp", 0.0)) if row.get("frp") else 0.0,
                "acq_date": row.get("acq_date", ""),
                "acq_time": row.get("acq_time", ""),
                "satellite": sat_display,
            }
            rows.append(parsed)
        except (ValueError, KeyError) as exc:
            logger.debug("Skipping invalid FIRMS row %s: %s", row, exc)
    return rows


def deduplicate_hotspots(points: list[dict[str, Any]], threshold_km: float = 0.5) -> list[dict[str, Any]]:
    """
    Deduplicates overlapping detections across satellite orbits within threshold_km.
    Detections with higher Fire Radiative Power (FRP) take precedence.
    """
    if not points:
        return []
    sorted_pts = sorted(points, key=lambda p: float(p.get("frp", 0.0)), reverse=True)
    deduped: list[dict[str, Any]] = []
    for pt in sorted_pts:
        is_dup = False
        for kept in deduped:
            dist = haversine_distance_km(pt["latitude"], pt["longitude"], kept["latitude"], kept["longitude"])
            if dist <= threshold_km:
                is_dup = True
                break
        if not is_dup:
            deduped.append(pt)
    return deduped


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


def process_hotspots_for_telemetry_and_clustering(
    rows: list[dict[str, Any]],
    bbox: tuple[float, float, float, float] = BAY_AREA_BBOX,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Processes FIRMS detections within bbox:
    Returns (wildland_points, all_bay_area_hotspots_with_metadata).
    """
    min_lon, min_lat, max_lon, max_lat = bbox
    wildland_points: list[dict[str, Any]] = []
    all_hotspots: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc)
    # Rolling 2-calendar-day window matching NASA FIRMS "24HRS" portal definition:
    # "From [Yesterday 00:00:00 UTC] to present" (up to 48 hours)
    yesterday_midnight_utc = datetime.combine(
        now.date() - timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc
    )

    for pt in rows:
        lat = pt["latitude"]
        lon = pt["longitude"]

        # Geographic bounds check
        if not (min_lat <= lat <= max_lat and min_lon <= lon <= max_lon):
            continue

        # 2-calendar-day rolling window check (From yesterday 00:00:00 UTC to present)
        acq_date = pt.get("acq_date")
        acq_time = pt.get("acq_time")
        if acq_date and acq_time:
            try:
                time_str = f"{acq_date} {str(acq_time).zfill(4)}"
                dt = datetime.strptime(time_str, "%Y-%m-%d %H%M").replace(tzinfo=timezone.utc)
                if dt < yesterday_midnight_utc:
                    continue
            except Exception:
                pass

        # Confidence check (reject low confidence)
        conf = pt.get("confidence", "nominal")
        if conf in ("low", "l"):
            continue
        try:
            if float(conf) < 50.0:
                continue
        except ValueError:
            pass

        is_flare, site_name = check_refinery_zone(lat, lon)
        enriched_pt = dict(pt)
        enriched_pt["is_industrial_flare"] = is_flare
        enriched_pt["flare_site_name"] = site_name

        all_hotspots.append(enriched_pt)

        if not is_flare:
            wildland_points.append(enriched_pt)

    return wildland_points, all_hotspots


def cluster_hotspots(
    points: list[dict[str, Any]],
    radius_km: float = 3.0,
    buffer_km: float = 20.0,
) -> list[FireCluster]:
    """
    Clusters nearby hotspot points into distinct fire incidents and calculates
    padded bounding boxes (+buffer_km) suitable for ML spread modeling.
    """
    if not points:
        return []

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

    result: list[FireCluster] = []
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
) -> FireClusterResult:
    """
    Fetches active fire hotspots across all three VIIRS sensors (Suomi-NPP, NOAA-20, NOAA-21),
    deduplicates detections across orbits, suppresses refinery/landfill flares, clusters wildland
    detections for ML inference, and attaches all raw telemetry hotspots to the result.
    """
    key = firms_map_key.strip()
    all_raw_rows: list[dict[str, Any]] = []
    valid_keyed_sensors = 0

    if key:
        bbox_str = f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}"
        for source in VIIRS_SOURCES:
            url = VIIRS_AREA_API_URL_TEMPLATE.format(key=key, source=source, bbox=bbox_str)
            logger.info("Fetching FIRMS Area API (%s): %s", source, url)
            try:
                resp = requests.get(url, timeout=timeout)
                resp.raise_for_status()
                if not is_valid_firms_csv(resp.text):
                    raise ValueError(f"NASA FIRMS Area API returned invalid response: {resp.text.strip()[:80]}")
                parsed = parse_firms_csv(resp.text, default_source=source)
                all_raw_rows.extend(parsed)
                valid_keyed_sensors += 1
            except Exception as exc:
                logger.warning("Failed fetching FIRMS sensor %s: %s", source, exc)

        if valid_keyed_sensors == 0:
            logger.warning(
                "All keyed FIRMS Area API sensor queries failed or were rejected. "
                "Falling back to public keyless CSVs for continuity (NFR-R04)."
            )

    if not key or valid_keyed_sensors == 0:
        for source, url in VIIRS_KEYLESS_CSV_URLS.items():
            logger.info("Fetching public keyless FIRMS CSV (%s): %s", source, url)
            try:
                resp = requests.get(url, timeout=timeout)
                resp.raise_for_status()
                if not is_valid_firms_csv(resp.text):
                    raise ValueError(f"NASA FIRMS keyless CSV returned invalid response: {resp.text.strip()[:80]}")
                parsed = parse_firms_csv(resp.text, default_source=source)
                all_raw_rows.extend(parsed)
            except Exception as exc:
                logger.warning("Failed fetching keyless FIRMS sensor %s: %s", source, exc)

    wildland_pts, all_bay_hotspots = process_hotspots_for_telemetry_and_clustering(all_raw_rows, bbox=bbox)
    deduped_all_hotspots = deduplicate_hotspots(all_bay_hotspots, threshold_km=0.5)
    deduped_wildland = [pt for pt in deduped_all_hotspots if not pt.get("is_industrial_flare")]

    clusters = cluster_hotspots(deduped_wildland)
    return FireClusterResult(clusters, raw_hotspots=deduped_all_hotspots)
