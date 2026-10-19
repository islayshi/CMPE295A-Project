"""
Telemetry Views — Fight Fire With AI
"""

import json
import logging
import os
import ee
from pathlib import Path
from datetime import datetime, timedelta
from django.conf import settings
from django.http import JsonResponse
from django.core.cache import cache
from rest_framework.decorators import api_view
from rest_framework.response import Response
import csv
import requests
import calendar
import xml.etree.ElementTree as ET

from .models import EmergencyShelter

logger = logging.getLogger(__name__)

WIND_CACHE_KEY = "ffwai:wind_current"
ALERTS_CACHE_KEY = "ffwai:nws_alerts"
AQI_CACHE_KEY = "ffwai:aqi_data"

# --- Earth Engine Initialization ---
SERVICE_ACCOUNT_FILE = settings.BASE_DIR / 'gee_service_account.json'

try:
    credentials = ee.ServiceAccountCredentials(key_file=str(SERVICE_ACCOUNT_FILE))
    ee.Initialize(credentials)
    logger.info("Google Earth Engine initialized successfully in telemetry app.")
except Exception as e:
    logger.warning(f"GEE Initialization Warning: {e}")


@api_view(["GET"])
def get_gee_ndvi_tile(request):
    """
    GET /api/telemetry/gee/ndvi-tile/
    """
    try:
        # 1. Parse date parameter or default to today
        end_date_str = request.GET.get('end_date', datetime.utcnow().strftime('%Y-%m-%d'))
        end_dt = datetime.strptime(end_date_str, '%Y-%m-%d')
        
        # Look back 30 days to collect enough overlapping passes for full coverage
        start_date_str = (end_dt - timedelta(days=30)).strftime('%Y-%m-%d')

        # 2. Bounding box covering the entire SF Bay Area
        bay_area_roi = ee.Geometry.BBox(-123.1, 36.8, -121.5, 38.8)

        # 3. Filter image collection across space and time
        s2_collection = (
            ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
            .filterBounds(bay_area_roi)
            .filterDate(start_date_str, end_date_str)
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 30))
        )

        # Check if imagery exists in this range
        count = s2_collection.size().getInfo()
        if count == 0:
            return JsonResponse({
                'status': 'error',
                'message': f'No imagery found between {start_date_str} and {end_date_str}.'
            }, status=404)

        # 4. Create a median composite across all images and clip to Bay Area ROI
        composite = s2_collection.median().clip(bay_area_roi)

        # 5. Compute NDVI on the seamless composite
        ndvi = composite.normalizedDifference(['B8', 'B4']).rename('NDVI')

        # 6. Color palette (Red = low vegetation/dry, Green = healthy vegetation)
        vis_params = {
            'min': 0.0,
            'max': 0.8,
            'palette': ['d73027', 'f46d43', 'fdae61', 'fee08b', 'd9ef8b', 'a6d96a', '66bd63', '1a9850']
        }

        # 7. Generate Leaflet-compatible tile URL
        map_id_dict = ndvi.getMapId(vis_params)
        tile_url = map_id_dict['tile_fetcher'].url_format

        return JsonResponse({
            'status': 'success',
            'tile_url': tile_url,
            'date_range': f"{start_date_str} to {end_date_str}",
            'description': 'SF Bay Area Sentinel-2 30-Day NDVI Composite'
        })

    except Exception as e:
        logger.error(f"GEE tile generation failed: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@api_view(["GET"])
def get_gee_available_dates(request):
    """
    GET /api/telemetry/gee/available-dates/
    """
    try:
        bay_area_roi = ee.Geometry.BBox(-123.1, 36.8, -121.5, 38.8)

        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=365)

        s2_collection = (
            ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
            .filterBounds(bay_area_roi)
            .filterDate(start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 30))
        )

        timestamps = s2_collection.aggregate_array('system:time_start').getInfo()

        available_dates = sorted(list(set([
            datetime.utcfromtimestamp(ts / 1000.0).strftime('%Y-%m-%d')
            for ts in timestamps
        ])))

        return JsonResponse({
            'status': 'success',
            'dates': available_dates
        })

    except Exception as e:
        logger.error(f"GEE available dates query failed: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@api_view(["GET"])
def aqi_data(request):
    cached = cache.get(AQI_CACHE_KEY)
    if cached:
        return Response(json.loads(cached))

    logger.warning("aqi_data: Redis cache miss — harvester has not populated AQI data yet.")
    return Response({"aqi": None, "status": "Unavailable", "pm25": None})


@api_view(["GET"])
def wind_telemetry(request):
    cached = cache.get(WIND_CACHE_KEY)
    if cached:
        return Response(json.loads(cached))

    logger.warning("wind_telemetry: Redis cache miss — harvester has not populated live wind data.")
    return Response([])


@api_view(["GET"])
def nws_alerts(request):
    cached = cache.get(ALERTS_CACHE_KEY)
    if cached:
        return Response(json.loads(cached))

    logger.warning("nws_alerts: Redis cache miss — returning mock red flag warning")
    return Response({
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [-122.10, 37.69],
                        [-122.03, 37.69],
                        [-122.03, 37.64],
                        [-122.10, 37.64],
                        [-122.10, 37.69]
                    ]]
                }
            }
        ]
    })


@api_view(["GET"])
def emergency_shelters(request):
    queryset = EmergencyShelter.objects.all()

    county = request.query_params.get("county")
    if county:
        queryset = queryset.filter(county__icontains=county)

    features = []
    for shelter in queryset:
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [shelter.location.x, shelter.location.y],
            },
            "properties": {
                "id": shelter.id,
                "name": shelter.name,
                "address": shelter.address,
                "county": shelter.county,
                "capacity": shelter.capacity,
                "source": shelter.source,
            },
        })

    return Response({
        "type": "FeatureCollection",
        "total": len(features),
        "features": features,
    })
    
FIRMS_MAP_KEY = os.getenv("FIRMS_MAP_KEY")

@api_view(["GET"])
def get_firms_hotspots(request):
    """
    GET /api/telemetry/firms/
    Accepts optional query params: ?date=YYYY-MM-DD&time=HHMM
    """
    target_date = request.GET.get('date')
    target_time = request.GET.get('time')  # e.g., '2115'

    # SF Bay Area Bounding Box: West, South, East, North
    bbox = "-123.1,36.8,-121.5,38.8"
    
    # Query VIIRS Suomi-NPP detections for the Bay Area (5-day max limit for Area API)
    url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{FIRMS_MAP_KEY}/VIIRS_SNPP_NRT/{bbox}/5"

    try:
        res = requests.get(url, timeout=12)
        if res.status_code != 200:
            return JsonResponse({'status': 'error', 'message': f'FIRMS API returned status {res.status_code}'}, status=500)

        lines = res.text.strip().splitlines()
        if len(lines) <= 1:
            return JsonResponse({'status': 'success', 'hotspots': [], 'passes': {}})

        reader = csv.DictReader(lines)
        all_hotspots = []
        passes_map = {}

        for row in reader:
            acq_date = row['acq_date']
            acq_time = row['acq_time'].zfill(4)

            if acq_date not in passes_map:
                passes_map[acq_date] = set()
            passes_map[acq_date].add(acq_time)

            all_hotspots.append({
                "lat": float(row['latitude']),
                "lon": float(row['longitude']),
                "frp": float(row['frp']),
                "confidence": row['confidence'],
                "bright_ti4": float(row['bright_ti4']),
                "acq_date": acq_date,
                "acq_time": acq_time,
                "satellite": row['satellite'],
                "daynight": row['daynight']
            })

        formatted_passes = {d: sorted(list(t_set)) for d, t_set in passes_map.items()}

        filtered_hotspots = all_hotspots
        if target_date:
            filtered_hotspots = [h for h in filtered_hotspots if h['acq_date'] == target_date]
        if target_time:
            filtered_hotspots = [h for h in filtered_hotspots if h['acq_time'] == target_time]

        return JsonResponse({
            'status': 'success',
            'passes': formatted_passes,
            'hotspots': filtered_hotspots,
            'total_count': len(filtered_hotspots)
        })

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@api_view(["GET"])
def get_firms_active_dates(request):
    """
    GET /api/telemetry/firms/active-dates/?year=YYYY&month=MM
    Queries NASA FIRMS in 10-day chunks to adhere to API limits.
    """
    year_str = request.GET.get('year')
    month_str = request.GET.get('month')

    now = datetime.utcnow()
    year = int(year_str) if year_str else now.year
    month = int(month_str) if month_str else now.month

    bbox = "-123.1,36.8,-121.5,38.8"
    is_current_month = (year == now.year and month == now.month)

    active_dates = set()

    try:
        if is_current_month:
            # Query 5-day NRT window for the current month
            url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{FIRMS_MAP_KEY}/VIIRS_SNPP_NRT/{bbox}/5"
            res = requests.get(url, timeout=12)
            if res.status_code == 200:
                lines = res.text.strip().splitlines()
                if len(lines) > 1:
                    reader = csv.DictReader(lines)
                    for row in reader:
                        active_dates.add(row['acq_date'])
        else:
            # Archive query: Chunk the month into 10-day windows (Days 1, 11, 21)
            last_day = calendar.monthrange(year, month)[1]
            chunk_starts = [1, 11, 21]

            for start_day in chunk_starts:
                if start_day > last_day:
                    break
                
                # Calculate days in chunk (capped at 10)
                days_in_chunk = min(10, last_day - start_day + 1)
                start_date_str = f"{year}-{month:02d}-{start_day:02d}"

                url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{FIRMS_MAP_KEY}/VIIRS_SNPP_SP/{bbox}/{days_in_chunk}/{start_date_str}"
                
                res = requests.get(url, timeout=12)
                if res.status_code == 200:
                    lines = res.text.strip().splitlines()
                    if len(lines) > 1:
                        reader = csv.DictReader(lines)
                        for row in reader:
                            active_dates.add(row['acq_date'])

        return JsonResponse({
            'status': 'success',
            'dates': sorted(list(active_dates))
        })

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

# Representative Bay Area Weather Monitoring Locations
BAY_AREA_WEATHER_STATIONS = [
    {"id": "OAK-HILLS", "name": "Oakland Hills (Redwood Ridge)", "subRegion": "East Bay", "lat": 37.81, "lon": -122.21},
    {"id": "MT-TAM", "name": "Mt. Tamalpais Peak", "subRegion": "North Bay", "lat": 37.92, "lon": -122.59},
    {"id": "SJ-FOOTHILLS", "name": "Alum Rock Foothills", "subRegion": "South Bay", "lat": 37.36, "lon": -121.82},
    {"id": "SF-COAST", "name": "Presidio / Ocean Beach", "subRegion": "San Francisco", "lat": 37.79, "lon": -122.47},
    {"id": "SCRM-GAP", "name": "Santa Cruz Mountains (Summit)", "subRegion": "Peninsula / South", "lat": 37.16, "lon": -121.98},
    {"id": "NAPA-VALLEY", "name": "Napa Valley Foothills", "subRegion": "North Bay", "lat": 38.30, "lon": -122.29},
]

@api_view(["GET"])
def get_weather_telemetry(request):
    """
    GET /api/telemetry/weather/?date=YYYY-MM-DD
    Fetches hourly surface meteorology across Bay Area stations and computes fire-weather risk indicators.
    """
    target_date = request.GET.get('date')
    if not target_date:
        target_date = datetime.utcnow().strftime('%Y-%m-%d')

    all_station_data = []
    max_wind_gust = 0.0
    min_relative_humidity = 100.0
    max_temperature = -100.0
    dominant_wind_dir_sum = 0.0
    total_samples = 0

    try:
        for station in BAY_AREA_WEATHER_STATIONS:
            # Query Open-Meteo Weather API for hourly surface parameters (Imperial units for US wildfire standards)
            url = (
                f"https://api.open-meteo.com/v1/forecast?"
                f"latitude={station['lat']}&longitude={station['lon']}&"
                f"start_date={target_date}&end_date={target_date}&"
                f"hourly=temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,wind_gusts_10m&"
                f"wind_speed_unit=mph&temperature_unit=fahrenheit&timezone=UTC"
            )

            res = requests.get(url, timeout=10)
            if not res.ok:
                continue

            data = res.json()
            hourly = data.get("hourly", {})
            times = hourly.get("time", [])
            temps = hourly.get("temperature_2m", [])
            rhs = hourly.get("relative_humidity_2m", [])
            wind_speeds = hourly.get("wind_speed_10m", [])
            wind_dirs = hourly.get("wind_direction_10m", [])
            wind_gusts = hourly.get("wind_gusts_10m", [])

            hourly_records = []
            for i in range(len(times)):
                t = temps[i] if idx_valid(temps, i) else 0.0
                rh = rhs[i] if idx_valid(rhs, i) else 50.0
                ws = wind_speeds[i] if idx_valid(wind_speeds, i) else 0.0
                wd = wind_dirs[i] if idx_valid(wind_dirs, i) else 0.0
                wg = wind_gusts[i] if idx_valid(wind_gusts, i) else ws

                # Track global summary metrics
                if wg > max_wind_gust:
                    max_wind_gust = wg
                if rh < min_relative_humidity:
                    min_relative_humidity = rh
                if t > max_temperature:
                    max_temperature = t

                dominant_wind_dir_sum += wd
                total_samples += 1

                hourly_records.append({
                    "time": times[i].replace("T", " "),
                    "temperature": round(t, 1),
                    "relativeHumidity": round(rh, 1),
                    "windSpeed": round(ws, 1),
                    "windDirection": round(wd, 1),
                    "windGust": round(wg, 1),
                })

            all_station_data.append({
                "stationId": station["id"],
                "stationName": station["name"],
                "subRegion": station["subRegion"],
                "lat": station["lat"],
                "lon": station["lon"],
                "hourly": hourly_records,
            })

        avg_wind_dir = round(dominant_wind_dir_sum / total_samples, 1) if total_samples > 0 else 0.0

        # Assess Critical Fire Weather Trigger (Red Flag Criteria: Low RH + High Gusts)
        is_red_flag = (min_relative_humidity <= 15.0 and max_wind_gust >= 25.0) or (max_wind_gust >= 35.0)

        return JsonResponse({
            "status": "success",
            "date": target_date,
            "summary": {
                "maxWindGustMph": round(max_wind_gust, 1),
                "minRelativeHumidity": round(min_relative_humidity, 1),
                "maxTemperatureF": round(max_temperature, 1),
                "avgWindDirectionDeg": avg_wind_dir,
                "isRedFlagCondition": is_red_flag,
            },
            "stations": all_station_data,
        })

    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


def idx_valid(lst, idx):
    return idx < len(lst) and lst[idx] is not None

import re
import requests
from datetime import datetime, timedelta
from django.http import JsonResponse
from rest_framework.decorators import api_view

@api_view(["GET"])
def get_goes_fire_telemetry(request):
    """
    GET /api/telemetry/goes/?channel=07
    Scrapes NOAA NESDIS STAR PSW directory directly for active image frames.
    """
    channel = request.GET.get('channel', '07')  # '07' (Shortwave IR) or 'GEOCOLOR'
    sector = "psw"
    base_url = f"https://cdn.star.nesdis.noaa.gov/GOES18/ABI/SECTOR/{sector}/{channel}/"
    
    today = datetime.utcnow().date()
    available_dates = [(today - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(14)]
    
    try:
        res = requests.get(base_url, timeout=6)
        frames = []

        if res.ok:
            # Extract .jpg files from directory HTML
            jpg_files = sorted(set(re.findall(r'href="([^"]+\.jpg)"', res.text)))
            
            # Filter for timestamped files (must start with digit year like 2026...) and a uniform resolution size
            valid_jpgs = [
                f for f in jpg_files 
                if re.match(r'^\d{11}_', f) and "600x600" in f  # Uses fast 600x600 resolution snapshots
            ]
            
            # If 600x600 isn't explicitly matched, fall back to any timestamped files
            if not valid_jpgs:
                valid_jpgs = [f for f in jpg_files if re.match(r'^\d{11}_', f)]

            unique_frames = []
            for fname in valid_jpgs:
                # NOAA filename pattern: YYYYDDDHHMM_...
                match = re.search(r'^\d{4}\d{3}(\d{2})(\d{2})_', fname)
                if match:
                    hour, minute = match.group(1), match.group(2)
                    time_label = f"{hour}:{minute} UTC"
                else:
                    time_label = "Scan"
                    
                unique_frames.append({
                    "time": time_label,
                    "url": base_url + fname
                })

            # Subsample down to 12 frames spaced across the available sequence (~2 hour intervals)
            if len(unique_frames) > 12:
                step = max(1, len(unique_frames) // 12)
                frames = unique_frames[::step][:12]
            else:
                frames = unique_frames

        return JsonResponse({
            "status": "success",
            "date": available_dates[0],
            "availableDates": available_dates,
            "channel": channel,
            "totalFrames": len(frames),
            "frames": frames
        })

    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)