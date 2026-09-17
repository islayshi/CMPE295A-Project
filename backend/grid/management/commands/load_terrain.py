"""
Management Command: load_terrain

Loads static terrain data (elevation, slope, aspect, hillshade) for
every BayAreaGrid cell from the USGS 3DEP Digital Elevation Model.

Run AFTER `generate_grid` — requires BayAreaGrid cells to exist.

Usage:
    python manage.py load_terrain                   # Load from USGS DEM (requires GEE auth)
    python manage.py load_terrain --mock            # Populate with placeholder values for dev
    python manage.py load_terrain --mock --clear    # Clear existing and reload mock data

Design Doc Reference:
    §1.1 Module 2 (Database Engine): TerrainFeature static data
    ML Interface Contract §1.1: Elevation/slope/aspect/hillshade provided to ML team

Research Reference:
    Malik et al. (Atmosphere 2021, Table 1): Terrain features are among the
    most predictive fire risk features — elevation, slope, aspect, hillshade
    all sourced from USGS DEM. Slope and aspect directly influence fire spread speed.
"""

import logging
import random
import time

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from grid.models import BayAreaGrid, TerrainFeature

logger = logging.getLogger(__name__)

BATCH_SIZE = 500


class Command(BaseCommand):
    help = (
        "Load USGS DEM terrain features (elevation, slope, aspect, hillshade) "
        "into TerrainFeature for every BayAreaGrid cell. "
        "Requires generate_grid to have been run first."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--mock",
            action="store_true",
            help=(
                "Populate TerrainFeature with plausible mock values for local development. "
                "Bay Area elevation range: 0–1300m. Slope: 0–45°. "
                "USE IN DEV ONLY — real USGS data required for production."
            ),
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete all existing TerrainFeature rows before loading.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=BATCH_SIZE,
            help=f"Bulk insert batch size (default: {BATCH_SIZE}).",
        )

    def handle(self, *args, **options):
        use_mock = options["mock"]
        clear = options["clear"]
        batch_size = options["batch_size"]

        grid_count = BayAreaGrid.objects.count()
        if grid_count == 0:
            raise CommandError(
                "No BayAreaGrid cells found. "
                "Run `python manage.py generate_grid` first."
            )

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"\n{'=' * 60}\n"
                f"  Fight Fire With AI — Terrain Loader\n"
                f"{'=' * 60}"
            )
        )
        self.stdout.write(f"  Grid cells found : {grid_count:,}")
        self.stdout.write(f"  Mode             : {'MOCK (dev only)' if use_mock else 'USGS DEM (production)'}\n")

        existing = TerrainFeature.objects.count()
        if existing > 0 and not clear:
            raise CommandError(
                f"TerrainFeature already has {existing:,} rows. "
                f"Use --clear to replace, or skip if already loaded."
            )

        if clear and existing > 0:
            self.stdout.write(self.style.WARNING(f"  Clearing {existing:,} existing TerrainFeature rows..."))
            TerrainFeature.objects.all().delete()
            self.stdout.write(self.style.SUCCESS("  Cleared.\n"))

        if use_mock:
            self._load_mock_terrain(batch_size, grid_count)
        else:
            self._load_real_terrain()

    def _load_mock_terrain(self, batch_size: int, grid_count: int):
        """
        Populate TerrainFeature with plausible mock values.

        Mock values are seeded from grid cell lat/lon to produce spatially
        coherent variation (higher elevation east of the Bay, steeper slopes
        in the Santa Cruz and Diablo ranges).

        IMPORTANT: Replace with real USGS DEM data before any ML training.
        """
        self.stdout.write("  Generating mock terrain data...")
        start_time = time.monotonic()
        batch = []
        written = 0

        grids = BayAreaGrid.objects.only("id", "centroid", "row", "col").iterator(chunk_size=1000)
        for grid in grids:
            lon = grid.centroid.x
            lat = grid.centroid.y

            # Synthetic elevation: higher in the east (Diablo Range) and south (Santa Cruz Mtns)
            # Bay floor is ~0m; ridgelines up to ~1,200m
            base_elev = max(0.0, (lon + 122.0) * -400 + (lat - 37.5) * -200 + random.gauss(0, 50))
            elevation = max(0.0, min(1300.0, base_elev))

            # Slope increases with elevation (rough heuristic)
            slope = max(0.0, min(45.0, elevation * 0.03 + random.gauss(0, 3)))

            # Aspect: random 0–360° (compass direction of downhill slope)
            aspect = random.uniform(0.0, 360.0)

            # Hillshade: derived from slope and aspect assuming SW sun angle (typical afternoon CA)
            # Simplified: cells with south/southwest-facing slopes get higher hillshade
            import math
            hillshade = max(0.0, min(255.0,
                255 * max(0, math.cos(math.radians(slope)) *
                          math.cos(math.radians(30)) +  # sun altitude 30°
                          math.sin(math.radians(slope)) *
                          math.sin(math.radians(30)) *
                          math.cos(math.radians(aspect - 225)))  # sun azimuth 225° (SW)
            ))

            batch.append(
                TerrainFeature(
                    grid=grid,
                    elevation=round(elevation, 2),
                    slope=round(slope, 2),
                    aspect=round(aspect, 2),
                    hillshade=round(hillshade, 2),
                    powerline_dist_km=None,  # Deferred per ML team decision
                )
            )

            if len(batch) >= batch_size:
                with transaction.atomic():
                    TerrainFeature.objects.bulk_create(batch, ignore_conflicts=True)
                written += len(batch)
                batch = []
                elapsed = time.monotonic() - start_time
                pct = (written / grid_count) * 100
                self.stdout.write(
                    f"  Progress: {written:>6,} / {grid_count:,} ({pct:.1f}%) — {elapsed:.1f}s",
                    ending="\r",
                )

        if batch:
            with transaction.atomic():
                TerrainFeature.objects.bulk_create(batch, ignore_conflicts=True)
            written += len(batch)

        elapsed = time.monotonic() - start_time
        self.stdout.write("\n")
        self.stdout.write(
            self.style.SUCCESS(
                f"  ✓ Mock terrain loaded!\n"
                f"    Rows written  : {written:,}\n"
                f"    Time elapsed  : {elapsed:.2f} seconds\n"
            )
        )
        self.stdout.write(
            self.style.WARNING(
                "  ⚠  MOCK DATA — Replace with real USGS DEM before ML training.\n"
            )
        )

    def _load_real_terrain(self):
        """
        PLACEHOLDER — Production Implementation (Week 2).

        Load terrain from the USGS 3DEP 10m DEM via Google Earth Engine.

        Steps:
          1. Authenticate GEE: ee.Initialize(credentials=service_account_creds)
          2. Load DEM: ee.Image('USGS/3DEP/10m')
          3. Derive slope: ee.Terrain.slope(dem)
          4. Derive aspect: ee.Terrain.aspect(dem)
          5. Derive hillshade: ee.Terrain.hillshade(dem)
          6. Sample at each BayAreaGrid centroid
          7. Export to GCS → parse CSV → bulk insert TerrainFeature

        References:
          GEE dataset: https://developers.google.com/earth-engine/datasets/catalog/USGS_3DEP_10m
          Malik et al. (2021): Table 1 — terrain feature set
        """
        raise CommandError(
            "Real USGS DEM loading is not yet implemented.\n"
            "Use --mock for local development.\n"
            "Production implementation is scheduled for Week 2."
        )
