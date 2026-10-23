"""
Unit tests for NASA FIRMS satellite data fetching, refinery filtering, and clustering.
"""
import io
import pytest
from unittest.mock import patch, MagicMock

try:
    from harvester.firms_client import (
        is_near_refinery,
        filter_hotspots,
        cluster_hotspots,
        parse_firms_csv,
        fetch_bay_area_hotspots,
        FireCluster,
        REFINERY_ZONES,
    )
except ImportError:
    from backend.harvester.firms_client import (
        is_near_refinery,
        filter_hotspots,
        cluster_hotspots,
        parse_firms_csv,
        fetch_bay_area_hotspots,
        FireCluster,
        REFINERY_ZONES,
    )

SAMPLE_VIIRS_CSV = """latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,instrument,confidence,version,bright_ti5,frp,daynight
37.5000,-122.1000,340.5,0.4,0.4,2026-10-23,1930,N,VIIRS,nominal,2.0NRT,295.2,15.4,D
37.5050,-122.1050,335.2,0.4,0.4,2026-10-23,1930,N,VIIRS,high,2.0NRT,293.1,12.0,D
37.9358,-122.3858,360.0,0.4,0.4,2026-10-23,1930,N,VIIRS,high,2.0NRT,310.0,45.0,D
37.8000,-122.2000,310.0,0.4,0.4,2026-10-23,1930,N,VIIRS,low,2.0NRT,285.0,2.1,D
36.0000,-120.0000,330.0,0.4,0.4,2026-10-23,1930,N,VIIRS,nominal,2.0NRT,290.0,8.0,D
"""


def test_is_near_refinery():
    # Direct hit on Richmond refinery
    assert is_near_refinery(37.9358, -122.3858) is True
    # 500m away from Richmond refinery
    assert is_near_refinery(37.9380, -122.3870) is True
    # San Jose foothills (far from any refinery)
    assert is_near_refinery(37.3382, -121.8863) is False


def test_parse_firms_csv_and_filtering():
    rows = parse_firms_csv(SAMPLE_VIIRS_CSV)
    assert len(rows) == 5

    filtered = filter_hotspots(rows)
    # Row 1: Valid (37.5, -122.1, nominal) -> Kept
    # Row 2: Valid (37.505, -122.105, high) -> Kept
    # Row 3: Richmond refinery (37.9358, -122.3858) -> Excluded by refinery mask
    # Row 4: Low confidence -> Excluded
    # Row 5: Outside Bay Area bounding box -> Excluded
    assert len(filtered) == 2
    assert filtered[0]["latitude"] == 37.5
    assert filtered[1]["latitude"] == 37.505


def test_cluster_hotspots_groups_nearby_points():
    points = [
        {"latitude": 37.5000, "longitude": -122.1000, "confidence": "nominal"},
        {"latitude": 37.5050, "longitude": -122.1050, "confidence": "high"},
        {"latitude": 38.1000, "longitude": -122.5000, "confidence": "nominal"},  # ~75 km away
    ]
    clusters = cluster_hotspots(points, radius_km=3.0, buffer_km=25.0)
    assert len(clusters) == 2

    c1 = next(c for c in clusters if c.count == 2)
    assert round(c1.centroid_lat, 2) == 37.50
    assert round(c1.centroid_lon, 2) == -122.10
    # Bounding box should be buffered by +25km (~0.23 lat, ~0.28 lon)
    assert c1.bbox[0] < -122.10
    assert c1.bbox[2] > -122.10
    assert c1.bbox[1] < 37.50
    assert c1.bbox[3] > 37.50

    c2 = next(c for c in clusters if c.count == 1)
    assert round(c2.centroid_lat, 2) == 38.10


@patch("backend.harvester.firms_client.requests.get")
def test_fetch_bay_area_hotspots_with_map_key(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = SAMPLE_VIIRS_CSV
    mock_get.return_value = mock_resp

    clusters = fetch_bay_area_hotspots(firms_map_key="TEST_KEY")
    assert len(clusters) == 1
    assert clusters[0].count == 2
    mock_get.assert_called_once()
    assert "api/area/csv/TEST_KEY" in mock_get.call_args[0][0]


@patch("backend.harvester.firms_client.requests.get")
def test_fetch_bay_area_hotspots_keyless_fallback(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = SAMPLE_VIIRS_CSV
    mock_get.return_value = mock_resp

    clusters = fetch_bay_area_hotspots(firms_map_key="")
    assert len(clusters) == 1
    mock_get.assert_called_once()
    assert "SUOMI_VIIRS_C2" in mock_get.call_args[0][0]
