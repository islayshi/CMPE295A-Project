import pytest
from django.urls import reverse
from django.contrib.gis.geos import Point, Polygon
from rest_framework.test import APIClient
from grid.models import BayAreaGrid
from telemetry.models import EmergencyShelter
from routing.engine import compute_astar_route, _reset_cache
from predictions.models import FireRiskPrediction
from django.utils import timezone

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def grid_5x5():
    """Seeds a 5x5 grid (25 cells) centered roughly around a test origin."""
    # Let's say center is at lat=37.0, lon=-122.0
    # Grid steps of roughly 0.01 degrees (~1km)
    cells = []
    base_lon, base_lat = -122.0, 37.0
    id_counter = 1
    for row in range(5):
        for col in range(5):
            lon = base_lon + (col * 0.01)
            lat = base_lat + (row * 0.01)
            # Create a simple square polygon
            poly = Polygon(((lon, lat), (lon+0.01, lat), (lon+0.01, lat+0.01), (lon, lat+0.01), (lon, lat)))
            centroid = Point(lon + 0.005, lat + 0.005, srid=4326)
            cells.append(BayAreaGrid(
                id=id_counter,
                row=row,
                col=col,
                geometry=poly,
                centroid=centroid
            ))
            id_counter += 1
    BayAreaGrid.objects.bulk_create(cells)
    _reset_cache()
    return cells

@pytest.mark.django_db
def test_astar_finds_path_on_clear_grid(grid_5x5):
    """A* should find a path from (0,0) to (4,4) with no obstacles."""
    origin = Point(-122.0 + 0.005, 37.0 + 0.005, srid=4326) # Bottom-left (row 0, col 0)
    dest = Point(-122.0 + 0.045, 37.0 + 0.045, srid=4326)   # Top-right (row 4, col 4)
    
    path = compute_astar_route(origin, dest, set())
    assert path is not None
    assert len(path) > 1 # Should have multiple points
    
    # Path should start near origin and end near dest
    # Actually, path will be a list of Points (centroids)
    assert path[0].distance(origin) < 0.01
    assert path[-1].distance(dest) < 0.01

@pytest.mark.django_db
def test_astar_avoids_blocked_cells(grid_5x5):
    """A* should route around a wall of blocked cells."""
    origin = Point(-122.0 + 0.005, 37.0 + 0.005, srid=4326) # row 0, col 0
    dest = Point(-122.0 + 0.045, 37.0 + 0.045, srid=4326)   # row 4, col 4
    
    # Block row 2, cols 0, 1, 2, 3 (leaving col 4 open)
    # The IDs depend on our insertion order. row 2 starts at id 11 (2*5 + 1)
    blocked_ids = {
        BayAreaGrid.objects.get(row=2, col=0).id,
        BayAreaGrid.objects.get(row=2, col=1).id,
        BayAreaGrid.objects.get(row=2, col=2).id,
        BayAreaGrid.objects.get(row=2, col=3).id,
    }
    
    path = compute_astar_route(origin, dest, blocked_ids)
    assert path is not None
    
    # Verify no points in the path belong to the blocked cells
    for point in path:
        cell = BayAreaGrid.objects.get(centroid=point)
        assert cell.id not in blocked_ids

@pytest.mark.django_db
def test_astar_returns_none_when_no_path(grid_5x5):
    """A* should return None if the destination is unreachable."""
    origin = Point(-122.0 + 0.005, 37.0 + 0.005, srid=4326) # row 0, col 0
    dest = Point(-122.0 + 0.045, 37.0 + 0.045, srid=4326)   # row 4, col 4
    
    # Block the entire row 2, completely severing the grid
    blocked_ids = set(BayAreaGrid.objects.filter(row=2).values_list('id', flat=True))
    
    path = compute_astar_route(origin, dest, blocked_ids)
    assert path is None

@pytest.mark.django_db
def test_evacuate_endpoint_returns_geojson_linestring(api_client, grid_5x5):
    """Integration: the endpoint should use A* and return a valid GeoJSON Route."""
    # 1. Create a shelter at (4,4)
    shelter = EmergencyShelter.objects.create(
        name="Safe Haven",
        location=Point(-122.0 + 0.045, 37.0 + 0.045, srid=4326)
    )
    
    # 2. Call the endpoint from (0,0)
    url = reverse("routing-evacuate")
    payload = {"origin": {"lat": 37.005, "lon": -121.995}} # -122.0 + 0.005
    
    response = api_client.post(url, payload, format='json')
    assert response.status_code == 200
    
    data = response.json()
    assert data["type"] == "Feature"
    assert data["geometry"]["type"] == "LineString"
    assert len(data["geometry"]["coordinates"]) > 1
    assert data["properties"]["destination_shelter"] == shelter.name

@pytest.mark.django_db
def test_evacuate_endpoint_returns_404_when_all_shelters_blocked(api_client, grid_5x5):
    """If A* fails to find any route to any shelter, return 404."""
    EmergencyShelter.objects.create(
        name="Blocked Haven",
        location=Point(-122.0 + 0.045, 37.0 + 0.045, srid=4326)
    )
    
    # Block row 2 completely via FireRiskPrediction
    now = timezone.now()
    blocked_cells = BayAreaGrid.objects.filter(row=2)
    predictions = []
    for cell in blocked_cells:
        predictions.append(FireRiskPrediction(
            timestamp=now,
            source_model='unet',
            grid=cell,
                        fire_probability=0.9,
            risk_label='HIGH_RISK'
        ))
    FireRiskPrediction.objects.bulk_create(predictions)
    
    url = reverse("routing-evacuate")
    payload = {"origin": {"lat": 37.005, "lon": -121.995}}
    
    response = api_client.post(url, payload, format='json')
    assert response.status_code == 404
    assert "No safe evacuation route could be found" in response.json()["error"]
