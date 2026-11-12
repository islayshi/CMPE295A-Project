from django.apps import apps
from django.core.management import call_command, CommandError, get_commands
from django.db.migrations.loader import MigrationLoader
import pytest
from grid import models
from grid.models import BayAreaGrid, VegetationIndex


def test_terrain_feature_model_is_removed():
    """Verify TerrainFeature model is removed from grid.models and apps registry."""
    assert not hasattr(models, "TerrainFeature")
    with pytest.raises(LookupError):
        apps.get_model("grid", "TerrainFeature")


def test_load_terrain_command_is_removed():
    """Verify load_terrain management command is deleted and not discoverable."""
    commands = get_commands()
    assert "load_terrain" not in commands
    assert "generate_grid" in commands


def test_load_terrain_call_command_raises():
    """Verify calling load_terrain via call_command raises CommandError."""
    with pytest.raises(CommandError, match="Unknown command: 'load_terrain'"):
        call_command("load_terrain")


def test_bay_area_grid_reverse_relation_removed():
    """Verify BayAreaGrid no longer has a 'terrain' reverse relation or field."""
    assert not hasattr(BayAreaGrid, "terrain")
    field_names = [f.name for f in BayAreaGrid._meta.get_fields()]
    assert "terrain" not in field_names
    assert "terrainfeature" not in field_names


def test_remaining_grid_models_intact():
    """Verify BayAreaGrid and VegetationIndex remain available and configured."""
    assert hasattr(models, "BayAreaGrid")
    assert hasattr(models, "VegetationIndex")
    assert apps.get_model("grid", "BayAreaGrid") is BayAreaGrid
    assert apps.get_model("grid", "VegetationIndex") is VegetationIndex


def test_delete_terrainfeature_migration_registered():
    """Verify 0002_delete_terrainfeature migration is valid in the migration graph."""
    loader = MigrationLoader(connection=None, load=False)
    loader.build_graph()
    assert ("grid", "0002_delete_terrainfeature") in loader.graph.nodes
    migration = loader.get_migration("grid", "0002_delete_terrainfeature")
    assert any(
        op.__class__.__name__ == "DeleteModel" and getattr(op, "name", None) == "TerrainFeature"
        for op in migration.operations
    )


@pytest.mark.django_db
def test_generate_grid_idempotent_when_cells_exist():
    """Verify generate_grid skips generation gracefully without CommandError when cells exist."""
    from django.contrib.gis.geos import Polygon, Point
    from io import StringIO

    cell = Polygon((
        (-122.22, 37.05), (-122.2143, 37.05),
        (-122.2143, 37.0545), (-122.22, 37.0545),
        (-122.22, 37.05),
    ), srid=4326)
    BayAreaGrid.objects.create(
        id=99999,
        geometry=cell,
        centroid=Point(-122.215, 37.055, srid=4326),
        row=0,
        col=0,
    )

    out = StringIO()
    call_command("generate_grid", stdout=out)
    output = out.getvalue()
    assert "already contains" in output or "already populated" in output
    assert "skipping generation" in output.lower()


