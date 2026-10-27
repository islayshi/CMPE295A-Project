import json
from unittest.mock import patch, MagicMock
import pytest
from django.conf import settings
from django.core.cache import cache

from harvester.firms_client import (
    REFINERY_ZONES,
    is_near_refinery,
    check_refinery_zone,
    filter_hotspots,
    deduplicate_hotspots,
    fetch_bay_area_hotspots,
    VIIRS_SOURCES,
)


def test_firms_map_key_in_settings():
    """Verify that FIRMS_MAP_KEY is defined in Django settings."""
    assert hasattr(settings, "FIRMS_MAP_KEY")


def test_refinery_zones_includes_alviso_and_refineries():
    """Verify that REFINERY_ZONES includes Richmond, Rodeo, Martinez, Benicia, and Alviso."""
    zone_names = [z[0] for z in REFINERY_ZONES]
    assert any("Richmond" in name for name in zone_names)
    assert any("Rodeo" in name for name in zone_names)
    assert any("Martinez" in name for name in zone_names)
    assert any("Benicia" in name for name in zone_names)
    assert any("Alviso" in name for name in zone_names)

    # Test Alviso coordinate detection
    alviso_lat, alviso_lon = 37.4557, -121.9323
    assert is_near_refinery(alviso_lat, alviso_lon) is True
    is_flare, site_name = check_refinery_zone(alviso_lat, alviso_lon)
    assert is_flare is True
    assert "Alviso" in site_name

    # Test wildland coordinate is NOT near refinery
    wildland_lat, wildland_lon = 37.19, -121.68
    assert is_near_refinery(wildland_lat, wildland_lon) is False
    is_flare_wl, site_name_wl = check_refinery_zone(wildland_lat, wildland_lon)
    assert is_flare_wl is False
    assert site_name_wl is None


def test_deduplicate_hotspots():
    """Verify that detections across orbits within threshold distance are deduplicated, keeping highest FRP."""
    points = [
        {"latitude": 37.2001, "longitude": -121.7001, "frp": 15.0, "satellite": "VIIRS_SNPP_NRT"},
        {"latitude": 37.2002, "longitude": -121.7002, "frp": 25.0, "satellite": "VIIRS_NOAA20_NRT"},
        {"latitude": 37.8000, "longitude": -122.2000, "frp": 10.0, "satellite": "VIIRS_NOAA21_NRT"},
    ]
    deduped = deduplicate_hotspots(points, threshold_km=0.5)
    assert len(deduped) == 2
    # The higher FRP point (25.0) should be retained for the nearby pair
    nearby = [p for p in deduped if abs(p["latitude"] - 37.2) < 0.05]
    assert len(nearby) == 1
    assert nearby[0]["frp"] == 25.0
    assert nearby[0]["satellite"] == "VIIRS_NOAA20_NRT"


def test_fetch_bay_area_hotspots_queries_all_three_sensors():
    """Verify that fetch_bay_area_hotspots queries Suomi-NPP, NOAA-20, and NOAA-21 when key is provided."""
    sample_csv_snpp = "latitude,longitude,frp,confidence,acq_date,acq_time\n37.20,-121.70,12.0,nominal,2026-10-25,1800\n"
    sample_csv_noaa20 = "latitude,longitude,frp,confidence,acq_date,acq_time\n37.25,-121.80,18.0,high,2026-10-25,1900\n"
    sample_csv_noaa21 = "latitude,longitude,frp,confidence,acq_date,acq_time\n37.4557,-121.9323,30.0,high,2026-10-25,2000\n"

    def mock_get(url, *args, **kwargs):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        if "VIIRS_SNPP_NRT" in url:
            mock_resp.text = sample_csv_snpp
        elif "VIIRS_NOAA20_NRT" in url:
            mock_resp.text = sample_csv_noaa20
        elif "VIIRS_NOAA21_NRT" in url:
            mock_resp.text = sample_csv_noaa21
        else:
            mock_resp.text = ""
        mock_resp.raise_for_status = MagicMock()
        return mock_resp

    with patch("requests.get", side_effect=mock_get) as mock_req:
        result = fetch_bay_area_hotspots(firms_map_key="test_key")

        # Verify all three sensors were queried
        assert mock_req.call_count == 3
        urls_called = [call[0][0] for call in mock_req.call_args_list]
        for sensor in VIIRS_SOURCES:
            assert any(sensor in url for url in urls_called)

        # Result clusters should only contain wildland fires (not Alviso)
        assert len(result) >= 1
        for cluster in result:
            for pt in cluster.points:
                assert not is_near_refinery(pt["latitude"], pt["longitude"])

        # Result raw_hotspots should retain both wildland and suppressed flares
        assert hasattr(result, "raw_hotspots")
        raw_pts = result.raw_hotspots
        assert len(raw_pts) == 3

        alviso_pts = [p for p in raw_pts if p.get("is_industrial_flare")]
        assert len(alviso_pts) == 1
        assert "Alviso" in alviso_pts[0]["flare_site_name"]

        wildland_pts = [p for p in raw_pts if not p.get("is_industrial_flare")]
        assert len(wildland_pts) == 2


def test_trigger_active_inference_caches_hotspots_in_redis():
    """Verify that trigger_active_inference stores GeoJSON FeatureCollection in Redis key ffwai:telemetry:firms_hotspots."""
    from harvester.tasks import trigger_active_inference, FIRMS_HOTSPOTS_CACHE_KEY
    from harvester.firms_client import FireCluster, FireClusterResult

    sample_cluster = FireCluster(
        cluster_id=1,
        centroid_lat=37.2,
        centroid_lon=-121.7,
        count=1,
        bbox=[-121.9, 37.0, -121.5, 37.4],
        points=[{"latitude": 37.2, "longitude": -121.7, "frp": 12.0, "confidence": "nominal"}],
    )
    raw_hotspots = [
        {
            "latitude": 37.2,
            "longitude": -121.7,
            "frp": 12.0,
            "confidence": "nominal",
            "satellite": "Suomi-NPP",
            "is_industrial_flare": False,
            "flare_site_name": None,
        },
        {
            "latitude": 37.4557,
            "longitude": -121.9323,
            "frp": 25.0,
            "confidence": "high",
            "satellite": "NOAA-21",
            "is_industrial_flare": True,
            "flare_site_name": "Newby Island Landfill (Alviso)",
        },
    ]
    clusters = FireClusterResult([sample_cluster], raw_hotspots=raw_hotspots)

    fake_cache = {}

    def fake_cache_set(key, val, timeout=None):
        fake_cache[key] = val

    def fake_cache_get(key, default=None):
        return fake_cache.get(key, default)

    def fake_cache_delete(key):
        fake_cache.pop(key, None)

    with patch("harvester.tasks.fetch_bay_area_hotspots", return_value=clusters), \
         patch("predictions.models.FireIncident.objects.create") as mock_incident_create, \
         patch("harvester.tasks.chord") as mock_chord, \
         patch("harvester.tasks.cache.set", side_effect=fake_cache_set), \
         patch("harvester.tasks.cache.get", side_effect=fake_cache_get), \
         patch("harvester.tasks.cache.delete", side_effect=fake_cache_delete):
        mock_incident = MagicMock()
        mock_incident.id = 101
        mock_incident_create.return_value = mock_incident
        mock_chord_instance = MagicMock()
        mock_chord.return_value = mock_chord_instance

        res = trigger_active_inference.apply()
        assert res.result["status"] == "success"

        cached = fake_cache.get(FIRMS_HOTSPOTS_CACHE_KEY)
        assert cached is not None
        cached_data = json.loads(cached) if isinstance(cached, str) else cached
        assert cached_data.get("type") == "FeatureCollection"
        features = cached_data.get("features", [])
        assert len(features) == 2
        # Verify properties
        props = [f["properties"] for f in features]
        assert any(p["is_industrial_flare"] and "Alviso" in p["flare_site_name"] for p in props)
        assert any(not p["is_industrial_flare"] for p in props)



def test_parse_firms_csv_handles_satellite_sensor_codes():
    """Verify that parse_firms_csv correctly normalizes satellite codes ('1', '2', 'N', 'J1', 'J2')."""
    from harvester.firms_client import parse_firms_csv

    csv_text = (
        "latitude,longitude,satellite,instrument,confidence,frp\n"
        "37.20,-121.70,1,VIIRS,nominal,12.0\n"
        "37.25,-121.80,2,VIIRS,high,15.0\n"
        "37.30,-121.90,N,VIIRS,high,20.0\n"
        "37.35,-122.00,,VIIRS,high,25.0\n"
    )
    rows = parse_firms_csv(csv_text, default_source="VIIRS_NOAA20_NRT")
    assert len(rows) == 4
    assert rows[0]["satellite"] == "NOAA-20"  # '1' is JPSS-1 (NOAA-20)
    assert rows[1]["satellite"] == "NOAA-21"  # '2' is JPSS-2 (NOAA-21)
    assert rows[2]["satellite"] == "Suomi-NPP"  # 'N' is Suomi-NPP
    assert rows[3]["satellite"] == "NOAA-20"  # default_source should take precedence over generic instrument="VIIRS"


def test_parse_firms_csv_invalid_or_html_response():
    """Verify that HTML error pages or empty responses return an empty list without raising exceptions."""
    from harvester.firms_client import parse_firms_csv

    assert parse_firms_csv("<html><body>502 Bad Gateway</body></html>") == []
    assert parse_firms_csv("") == []
    assert parse_firms_csv("   \n\n ") == []
    assert parse_firms_csv("Invalid MAP_KEY\n") == []


def test_fetch_bay_area_hotspots_keyed_failure_falls_back_to_keyless():
    """
    Verify that if the keyed Area API fails (e.g. invalid map key, 403, 500, or 'Invalid MAP_KEY' 200 text),
    fetch_bay_area_hotspots gracefully falls back to the public keyless CSVs.
    """
    keyless_csv = "latitude,longitude,frp,confidence,acq_date,acq_time\n37.22,-121.72,16.0,high,2026-10-25,1830\n"

    def mock_get(url, *args, **kwargs):
        mock_resp = MagicMock()
        if "api/area" in url:
            # Simulated NASA error: 200 status with "Invalid MAP_KEY" text
            mock_resp.status_code = 200
            mock_resp.text = "Invalid MAP_KEY\n"
        else:
            # Keyless CSV URL
            mock_resp.status_code = 200
            mock_resp.text = keyless_csv
        mock_resp.raise_for_status = MagicMock()
        return mock_resp

    with patch("requests.get", side_effect=mock_get):
        result = fetch_bay_area_hotspots(firms_map_key="bad_or_expired_key")
        # Must not be empty: should have recovered using keyless CSV fallback!
        assert len(result.raw_hotspots) >= 1
        assert result.raw_hotspots[0]["latitude"] == 37.22


def test_aggregate_active_predictions_populates_ensemble_cache():
    """Verify that aggregate_active_predictions caches merged results in both current and current:ensemble keys."""
    from harvester.tasks import aggregate_active_predictions

    mock_results = [
        {
            "type": "FeatureCollection",
            "features": [{"type": "Feature", "properties": {"grid_id": 101, "horizon_hours": 1}}],
        },
        {
            "type": "FeatureCollection",
            "features": [{"type": "Feature", "properties": {"grid_id": 102, "horizon_hours": 3}}],
        },
    ]

    with patch("harvester.tasks.cache.set") as mock_cache_set:
        res = aggregate_active_predictions(mock_results)
        assert res["status"] == "success"
        assert res["total_cells"] == 2

        cached_keys = [call[0][0] for call in mock_cache_set.call_args_list]
        assert "ffwai:predictions:current" in cached_keys
        assert "ffwai:predictions:current:ensemble" in cached_keys


def test_aggregate_active_predictions_guards_against_empty_overwrite():
    """Verify that aggregate_active_predictions does not overwrite populated Redis cache with empty features."""
    from harvester.tasks import aggregate_active_predictions, CURRENT_RISK_CACHE_KEY

    existing_fc = {
        "type": "FeatureCollection",
        "metadata": {"total_cells": 1},
        "features": [{"type": "Feature", "properties": {"grid_id": 101, "horizon_hours": 1}}],
    }

    with patch("harvester.tasks.cache.get", return_value=json.dumps(existing_fc)), \
         patch("harvester.tasks.cache.set") as mock_cache_set:
        res = aggregate_active_predictions([])
        assert res["status"] in ("skipped_empty_overwrite", "ignored")
        # cache.set must NOT have been called with empty features!
        assert not any(call[0][0] == CURRENT_RISK_CACHE_KEY for call in mock_cache_set.call_args_list)


@pytest.mark.django_db
def test_archive_old_predictions_contains_incidents_after_24h_inactivity():
    """
    Verify that archive_old_predictions automatically marks active incidents as contained
    when 24 hours elapse without satellite hotspot detections within their bounding box,
    purging active Redis keys while retaining historical PostGIS PredictionPolygon rows.
    """
    from datetime import timedelta
    from django.utils import timezone
    from django.contrib.gis.geos import Polygon, Point
    from grid.models import BayAreaGrid
    from predictions.models import FireIncident, PredictionPolygon
    from harvester.tasks import archive_old_predictions, CURRENT_RISK_CACHE_KEY

    now = timezone.now()
    twenty_five_hours_ago = now - timedelta(hours=25)

    poly = Polygon(((9, 9), (9, 11), (11, 11), (11, 9), (9, 9)), srid=4326)
    grid = BayAreaGrid.objects.create(id=501, geometry=poly, centroid=Point(10, 10, srid=4326), row=0, col=0)

    incident = FireIncident.objects.create(
        name="Contained Test Fire",
        start_time=twenty_five_hours_ago,
        is_active=True,
    )
    pred = PredictionPolygon.objects.create(
        grid=grid,
        fire_incident=incident,
        timestamp=twenty_five_hours_ago,
        source_model="ensemble",
        fire_probability=0.85,
        lead_time_hours=1,
    )

    fake_cache = {
        CURRENT_RISK_CACHE_KEY: json.dumps({"type": "FeatureCollection", "features": [{"type": "Feature"}]}),
        "ffwai:predictions:current:ensemble": "data",
    }

    def fake_cache_delete(key):
        fake_cache.pop(key, None)

    with patch("harvester.tasks.cache.get", return_value=None), \
         patch("harvester.tasks.cache.delete", side_effect=fake_cache_delete):
        res = archive_old_predictions()
        assert res["status"] == "success"

        incident.refresh_from_db()
        assert incident.is_active is False
        assert incident.end_time is not None

        # Historical PostGIS rows must be preserved permanently!
        assert PredictionPolygon.objects.filter(id=pred.id).exists()

        # Active Redis prediction keys must be purged
        assert CURRENT_RISK_CACHE_KEY not in fake_cache
        assert "ffwai:predictions:current:ensemble" not in fake_cache


@pytest.mark.django_db
def test_archive_old_predictions_partial_containment_refreshes_cache_for_remaining_active():
    """
    Verify that when one incident is contained but other incidents remain active,
    archive_old_predictions refreshes the active Redis prediction cache to exclude
    the contained incident's polygons while retaining remaining active incidents.
    """
    from datetime import timedelta
    from django.utils import timezone
    from django.contrib.gis.geos import Polygon, Point
    from grid.models import BayAreaGrid
    from predictions.models import FireIncident, PredictionPolygon
    from harvester.tasks import archive_old_predictions, CURRENT_RISK_CACHE_KEY

    now = timezone.now()
    twenty_five_hours_ago = now - timedelta(hours=25)
    one_hour_ago = now - timedelta(hours=1)

    poly1 = Polygon(((9, 9), (9, 11), (11, 11), (11, 9), (9, 9)), srid=4326)
    grid1 = BayAreaGrid.objects.create(id=601, geometry=poly1, centroid=Point(10, 10, srid=4326), row=0, col=0)
    poly2 = Polygon(((12, 12), (12, 14), (14, 14), (14, 12), (12, 12)), srid=4326)
    grid2 = BayAreaGrid.objects.create(id=602, geometry=poly2, centroid=Point(13, 13, srid=4326), row=1, col=1)

    inc_contained = FireIncident.objects.create(
        name="Contained Fire",
        start_time=twenty_five_hours_ago,
        is_active=True,
    )
    PredictionPolygon.objects.create(
        grid=grid1,
        fire_incident=inc_contained,
        timestamp=twenty_five_hours_ago,
        source_model="ensemble",
        fire_probability=0.85,
        lead_time_hours=1,
    )

    inc_active = FireIncident.objects.create(
        name="Active Fire",
        start_time=one_hour_ago,
        is_active=True,
    )
    pred_active = PredictionPolygon.objects.create(
        grid=grid2,
        fire_incident=inc_active,
        timestamp=one_hour_ago,
        source_model="ensemble",
        fire_probability=0.92,
        lead_time_hours=1,
    )

    fake_cache = {}

    def fake_cache_set(key, val, timeout=None):
        fake_cache[key] = val

    with patch("harvester.tasks.cache.get", return_value=None), \
         patch("harvester.tasks.cache.set", side_effect=fake_cache_set):
        res = archive_old_predictions()
        assert res["status"] == "success"
        assert res["contained_incidents"] == 1
        assert res["remaining_active"] == 1

        inc_contained.refresh_from_db()
        assert inc_contained.is_active is False
        inc_active.refresh_from_db()
        assert inc_active.is_active is True

        # Cache should have been updated to only include the active incident
        assert CURRENT_RISK_CACHE_KEY in fake_cache
        cached_fc = json.loads(fake_cache[CURRENT_RISK_CACHE_KEY])
        assert len(cached_fc["features"]) == 1
        assert cached_fc["features"][0]["properties"]["grid_id"] == 602


def test_bay_area_bbox_includes_sacramento_delta_and_solano():
    """
    Verify that BAY_AREA_BBOX northern latitude extends to at least 38.50
    so northern Solano County and Sacramento Delta (Courtland, Rio Vista, Fairfield)
    hotspots are not excluded from telemetry pins.
    """
    from harvester.firms_client import BAY_AREA_BBOX

    min_lon, min_lat, max_lon, max_lat = BAY_AREA_BBOX
    assert max_lat >= 38.50, f"Expected max_lat >= 38.50, got {max_lat}"
    assert min_lat <= 36.90
    assert min_lon <= -122.90
    assert max_lon >= -121.50


@pytest.mark.django_db
def test_trigger_active_inference_dispatches_unet_and_pinn_tasks():
    """
    Verify that trigger_active_inference dispatches individual inference tasks for both
    U-Net and PINN (PIML) for each detected fire cluster.
    """
    from harvester.tasks import trigger_active_inference
    from harvester.firms_client import FireCluster

    cluster = FireCluster(
        cluster_id=1,
        centroid_lat=37.5,
        centroid_lon=-122.0,
        count=1,
        bbox=[-122.28, 37.27, -121.72, 37.73],
        points=[{"latitude": 37.5, "longitude": -122.0, "confidence": "high"}]
    )

    with patch("harvester.tasks.fetch_bay_area_hotspots", return_value=[cluster]), \
         patch("harvester.tasks.chord") as mock_chord:
        mock_chord_instance = MagicMock()
        mock_chord.return_value = mock_chord_instance

        result = trigger_active_inference.apply()

        assert result.result["status"] == "success"
        assert result.result["fires_detected"] == 1

        mock_chord.assert_called_once()
        header_tasks = mock_chord.call_args[0][0]
        # Must dispatch 2 tasks per cluster: one for U-Net, one for PINN/PIML
        assert len(header_tasks) == 2
        models = [t.args[1] if len(t.args) > 1 else t.kwargs.get("model_type") for t in header_tasks]
        assert "unet" in models
        assert "pinn" in models


def test_aggregate_active_predictions_populates_unet_and_pinn_caches():
    """
    Verify that aggregate_active_predictions aggregates features per model
    and caches them into ffwai:predictions:current:unet, ffwai:predictions:current:pinn,
    and ffwai:predictions:current.
    """
    from harvester.tasks import aggregate_active_predictions

    mock_results = [
        {
            "type": "FeatureCollection",
            "metadata": {"source_model": "unet"},
            "features": [{"type": "Feature", "properties": {"grid_id": 101, "source_model": "unet"}}],
        },
        {
            "type": "FeatureCollection",
            "metadata": {"source_model": "pinn"},
            "features": [{"type": "Feature", "properties": {"grid_id": 201, "source_model": "pinn"}}],
        },
    ]

    cached_entries = {}

    def mock_set(key, val, timeout=None):
        cached_entries[key] = json.loads(val) if isinstance(val, str) else val

    with patch("harvester.tasks.cache.set", side_effect=mock_set):
        res = aggregate_active_predictions(mock_results)
        assert res["status"] == "success"

        assert "ffwai:predictions:current:unet" in cached_entries
        assert "ffwai:predictions:current:pinn" in cached_entries
        assert "ffwai:predictions:current" in cached_entries

        assert len(cached_entries["ffwai:predictions:current:unet"]["features"]) == 1
        assert cached_entries["ffwai:predictions:current:unet"]["features"][0]["properties"]["grid_id"] == 101

        assert len(cached_entries["ffwai:predictions:current:pinn"]["features"]) == 1
        assert cached_entries["ffwai:predictions:current:pinn"]["features"][0]["properties"]["grid_id"] == 201




