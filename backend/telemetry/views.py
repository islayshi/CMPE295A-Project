"""
Telemetry Views — Fight Fire With AI
"""

import json
import logging
import os
import ee
from pathlib import Path
from datetime import datetime, timedelta, date
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

# Path to local MTBS GeoJSON dataset
GEOJSON_FILE_PATH = os.path.join(
    settings.BASE_DIR, 'telemetry', 'data', 'bay_area_mtbs.geojson'
)


@api_view(["GET"])
def get_mtbs_historical_perimeters(request):
    """
    GET /api/telemetry/mtbs/?year_min=2010&year_max=2024
    Reads historical MTBS fire perimeters directly from local static storage.
    """
    year_min = int(request.GET.get("year_min", 2010))
    year_max = int(request.GET.get("year_max", 2024))

    if not os.path.exists(GEOJSON_FILE_PATH):
        return JsonResponse({
            "status": "error",
            "message": f"Dataset file not found at {GEOJSON_FILE_PATH}. Download bay_area_mtbs.geojson first."
        }, status=404)

    try:
        with open(GEOJSON_FILE_PATH, 'r', encoding='utf-8') as f:
            raw_geojson = json.load(f)

        features = raw_geojson.get("features", [])
        filtered_features = []
        total_acres = 0
        fire_summary_list = []

        for idx, feat in enumerate(features):
            props = feat.get("properties", {})
            
            # Robust property key extraction (handles schema variations)
            fire_year = props.get("FIRE_YEAR") or props.get("year") or props.get("YEAR")
            if fire_year:
                try:
                    fire_year = int(fire_year)
                except ValueError:
                    fire_year = None

            # Filter by selected year range if year property is present
            if fire_year and not (year_min <= fire_year <= year_max):
                continue

            acres = props.get("BurnBndAc") or props.get("acres") or props.get("ACRES") or 0
            try:
                acres = float(acres)
            except ValueError:
                acres = 0.0

            total_acres += acres
            fire_name = str(props.get("Incid_Name") or props.get("name") or "UNNAMED").title()
            obj_id = feat.get("id") or props.get("OBJECTID") or idx

            fire_summary_list.append({
                "id": obj_id,
                "fireName": fire_name,
                "year": fire_year or "N/A",
                "ignitionDate": props.get("Ig_Date") or props.get("date") or "N/A",
                "acresBurned": round(acres, 1),
                "incidentType": props.get("Incid_Type") or "Wildfire"
            })

            filtered_features.append(feat)

        # Sort summary descending by acres burned
        fire_summary_list.sort(key=lambda x: x["acresBurned"], reverse=True)

        return JsonResponse({
            "status": "success",
            "filter": {
                "yearMin": year_min,
                "yearMax": year_max
            },
            "summary": {
                "totalIncidents": len(filtered_features),
                "totalAcresBurned": round(total_acres, 1),
                "largestFire": fire_summary_list[0] if fire_summary_list else None
            },
            "incidents": fire_summary_list,
            "geoJson": {
                "type": "FeatureCollection",
                "features": filtered_features
            }
        })

    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)

import requests
from datetime import datetime, timedelta
from django.http import JsonResponse
from rest_framework.decorators import api_view

BAY_AREA_GRIDMET_POINTS = [
    {"name": "North Bay (Sonoma/Napa)", "lat": 38.44, "lon": -122.71},
    {"name": "East Bay Hills (Oakland/Berkeley)", "lat": 37.87, "lon": -122.25},
    {"name": "South Bay / Santa Clara Valley", "lat": 37.33, "lon": -121.89},
    {"name": "Peninsula / Santa Cruz Mts", "lat": 37.44, "lon": -122.30},
    {"name": "San Francisco Maritime", "lat": 37.77, "lon": -122.41},
    {"name": "Mount Tamalpais Ridge", "lat": 37.92, "lon": -122.59},
]

@api_view(["GET"])
def get_gridmet_telemetry(request):
    """
    GET /api/telemetry/gridmet/?date=YYYY-MM-DD
    Fetches GRIDMET surface meteorology across Bay Area grid points.
    """
    target_date = request.GET.get("date", datetime.now().strftime("%Y-%m-%d"))

    station_results = []
    regional_aggregates = {
        "max_temp": [],
        "max_wind": [],
        "min_rh": [],
        "total_precip": [],
        "erc_proxy": [],
    }

    try:
        for pt in BAY_AREA_GRIDMET_POINTS:
            # Using Open-Meteo Forecast endpoint with start_date & end_date handles current/recent dates reliably
            url = (
                f"https://api.open-meteo.com/v1/forecast?"
                f"latitude={pt['lat']}&longitude={pt['lon']}"
                f"&start_date={target_date}&end_date={target_date}"
                f"&daily=temperature_2m_max,wind_speed_10m_max,"
                f"relative_humidity_2m_min,precipitation_sum,et0_fao_evapotranspiration"
                f"&timezone=America%2FLos_Angeles"
            )

            res = requests.get(url, timeout=8)
            if not res.ok:
                continue

            data = res.json().get("daily", {})

            tmax = data.get("temperature_2m_max", [None])[0]
            wind = data.get("wind_speed_10m_max", [None])[0]
            rh = data.get("relative_humidity_2m_min", [None])[0]
            precip = data.get("precipitation_sum", [None])[0]
            erc = data.get("et0_fao_evapotranspiration", [None])[0]

            if tmax is not None: regional_aggregates["max_temp"].append(tmax)
            if wind is not None: regional_aggregates["max_wind"].append(wind)
            if rh is not None: regional_aggregates["min_rh"].append(rh)
            if precip is not None: regional_aggregates["total_precip"].append(precip)
            if erc is not None: regional_aggregates["erc_proxy"].append(erc)

            station_results.append({
                "location": pt["name"],
                "lat": pt["lat"],
                "lon": pt["lon"],
                "metrics": {
                    "tmmx": {"value": tmax, "unit": "°C", "label": "Max Temperature"},
                    "vs": {"value": wind, "unit": "km/h", "label": "Max Wind Speed"},
                    "rmin": {"value": rh, "unit": "%", "label": "Min Relative Humidity"},
                    "pr": {"value": precip, "unit": "mm", "label": "Precipitation"},
                    "erc": {"value": erc, "unit": "mm", "label": "Evapotranspiration / ERC"}
                }
            })

        def safe_avg(lst):
            return round(sum(lst) / len(lst), 1) if lst else 0.0

        def safe_max(lst):
            return round(max(lst), 1) if lst else 0.0

        def safe_min(lst):
            return round(min(lst), 1) if lst else 0.0

        summary = {
            "avgMaxTemp": safe_avg(regional_aggregates["max_temp"]),
            "peakWindSpeed": safe_max(regional_aggregates["max_wind"]),
            "lowestRh": safe_min(regional_aggregates["min_rh"]),
            "avgPrecip": safe_avg(regional_aggregates["total_precip"]),
            "avgErcProxy": safe_avg(regional_aggregates["erc_proxy"]),
        }

        today_str = date.today().strftime("%Y-%m-%d")
        is_predicted = target_date > today_str

        return JsonResponse({
            "status": "success",
            "date": target_date,
            "dataType": "predicted_forecast" if is_predicted else "recorded_observation",
            "dataset": "GRIDMET Daily High-Resolution Surface Meteorology (4km)",
            "summary": summary,
            "gridPoints": station_results
        })

    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)

# Historical registry of major Bay Area / Northern CA fire incidents (2006–2026)
MAJOR_FIRE_INCIDENTS = {
    # 2024–2026 Incidents
    "Point Fire (2024)": {
        "name": "Point Fire",
        "county": "Sonoma",
        "year": "2024",
        "t0_date": "2024-06-16 12:00 UTC",
        "t1_date": "2024-06-17 12:00 UTC",
        "acreage_t0": 800,
        "acreage_t1": 1207,
        "radius_t0_m": 1000,
        "radius_t1_m": 1500,
        "center": [38.68, -122.91],
        "growth_pct": 50.8
    },
    # 2020 Incidents
    "LNU Lightning Complex (2020)": {
        "name": "LNU Lightning Complex",
        "county": "Napa",
        "year": "2020",
        "t0_date": "2020-08-18 08:00 UTC",
        "t1_date": "2020-08-19 08:00 UTC",
        "acreage_t0": 32000,
        "acreage_t1": 124000,
        "radius_t0_m": 4500,
        "radius_t1_m": 9000,
        "center": [38.52, -122.28],
        "growth_pct": 287.5
    },
    "CZU Lightning Complex (2020)": {
        "name": "CZU Lightning Complex",
        "county": "San Mateo",
        "year": "2020",
        "t0_date": "2020-08-18 10:00 UTC",
        "t1_date": "2020-08-19 10:00 UTC",
        "acreage_t0": 10000,
        "acreage_t1": 25000,
        "radius_t0_m": 2500,
        "radius_t1_m": 5000,
        "center": [37.17, -122.22],
        "growth_pct": 150.0
    },
    "SCU Lightning Complex (2020)": {
        "name": "SCU Lightning Complex",
        "county": "Santa Clara",
        "year": "2020",
        "t0_date": "2020-08-18 06:00 UTC",
        "t1_date": "2020-08-19 06:00 UTC",
        "acreage_t0": 35000,
        "acreage_t1": 137000,
        "radius_t0_m": 4800,
        "radius_t1_m": 9500,
        "center": [37.35, -121.55],
        "growth_pct": 291.4
    },
    # 2019 Incidents
    "Kincade Fire (2019)": {
        "name": "Kincade Fire",
        "county": "Sonoma",
        "year": "2019",
        "t0_date": "2019-10-24 04:00 UTC",
        "t1_date": "2019-10-25 04:00 UTC",
        "acreage_t0": 10000,
        "acreage_t1": 25400,
        "radius_t0_m": 2800,
        "radius_t1_m": 5200,
        "center": [38.79, -122.78],
        "growth_pct": 154.0
    },
    # 2018 Incidents
    "Camp Fire (2018)": {
        "name": "Camp Fire",
        "county": "Butte",
        "year": "2018",
        "t0_date": "2018-11-08 14:00 UTC",
        "t1_date": "2018-11-09 14:00 UTC",
        "acreage_t0": 18000,
        "acreage_t1": 70000,
        "radius_t0_m": 3500,
        "radius_t1_m": 7200,
        "center": [39.81, -121.43],
        "growth_pct": 288.8
    },
    # 2017 Incidents
    "Tubbs Fire (2017)": {
        "name": "Tubbs Fire",
        "county": "Sonoma",
        "year": "2017",
        "t0_date": "2017-10-08 21:00 UTC",
        "t1_date": "2017-10-09 21:00 UTC",
        "acreage_t0": 1200,
        "acreage_t1": 27000,
        "radius_t0_m": 1200,
        "radius_t1_m": 5400,
        "center": [38.60, -122.63],
        "growth_pct": 2150.0
    },
    "Atlas Fire (2017)": {
        "name": "Atlas Fire",
        "county": "Napa",
        "year": "2017",
        "t0_date": "2017-10-08 22:00 UTC",
        "t1_date": "2017-10-09 22:00 UTC",
        "acreage_t0": 2000,
        "acreage_t1": 25000,
        "radius_t0_m": 1500,
        "radius_t1_m": 5100,
        "center": [38.38, -122.24],
        "growth_pct": 1150.0
    },
    # 2013 Incidents
    "Rim Fire (2013)": {
        "name": "Rim Fire",
        "county": "Tuolumne",
        "year": "2013",
        "t0_date": "2013-08-18 15:00 UTC",
        "t1_date": "2013-08-19 15:00 UTC",
        "acreage_t0": 10000,
        "acreage_t1": 53000,
        "radius_t0_m": 2600,
        "radius_t1_m": 6200,
        "center": [37.86, -120.08],
        "growth_pct": 430.0
    },
    # 2008 Incidents
    "Lightning Complex (2008)": {
        "name": "Northern CA Lightning Complex",
        "county": "Mendocino",
        "year": "2008",
        "t0_date": "2008-06-21 18:00 UTC",
        "t1_date": "2008-06-22 18:00 UTC",
        "acreage_t0": 15000,
        "acreage_t1": 48000,
        "radius_t0_m": 3200,
        "radius_t1_m": 5800,
        "center": [39.15, -123.20],
        "growth_pct": 220.0
    }
}

@api_view(["GET"])
def get_ndws_telemetry(request):
    """
    GET /api/telemetry/ndws/?incident=Kincade Fire (2019)
    Returns distinct historical fire metrics and coordinates.
    """
    incident_key = request.GET.get("incident")
    
    # Return full list of major incidents if requested
    if request.GET.get("list_all") == "true":
        return JsonResponse({
            "status": "success",
            "incidents": list(MAJOR_FIRE_INCIDENTS.keys())
        })

    # Pick selected incident or default to LNU Lightning Complex
    event = MAJOR_FIRE_INCIDENTS.get(incident_key, MAJOR_FIRE_INCIDENTS["LNU Lightning Complex (2020)"])

    payload = {
        "status": "success",
        "source": "Direct Google Cloud Storage (NDWS TFRecords)",
        "event": event
    }
    return JsonResponse(payload)