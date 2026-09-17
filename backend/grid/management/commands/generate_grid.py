"""
Management Command: generate_grid

Generates the static 1×1 km spatial grid covering the 9-county
San Francisco Bay Area and populates the BayAreaGrid table.

This command is a one-time setup step. Run it once after migrations
to create the spatial foundation that all ML predictions, terrain data,
and evacuation routing depend on.

Usage:
    python manage.py generate_grid                  # Full Bay Area grid (~18,000 cells)
    python manage.py generate_grid --dry-run        # Preview cell count without writing
    python manage.py generate_grid --clear          # Delete existing grid and regenerate
    python manage.py generate_grid --bbox "37.2,-122.5,37.7,-121.9"  # Custom bounding box

Design Doc Reference:
    §1.1 Module 2 (Database Engine): BayAreaGrid as spatial foundation
    Implementation Plan v4: generate_grid.py management command

Research Reference:
    Malik et al. (Atmosphere 2021): 1×1 km grid methodology used as
    the spatial unit for all fire risk features and predictions.
    Grid center: lat=37.55, lon=-122.15 (aligned with ML team's U-Net).
"""

import math
import time
import logging

from django.contrib.gis.geos import Point, Polygon
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from grid.models import BayAreaGrid

logger = logging.getLogger(__name__)

# -------------------------------------------------------------------
# Bay Area Spatial Constants
# -------------------------------------------------------------------

# 9-county SF Bay Area bounding box (WGS84 / EPSG:4326)
# Covers: San Francisco, Alameda, Contra Costa, Marin, Napa,
#         San Mateo, Santa Clara, Solano, Sonoma counties.
#
# Verified against: CA State Geoportal + Paper 1 bounding box
BAY_AREA_LAT_MIN = 36.9
BAY_AREA_LAT_MAX = 38.3
BAY_AREA_LON_MIN = -122.9
BAY_AREA_LON_MAX = -121.5

# 1 km in decimal degrees
# Latitude: 1° = 111.32 km  →  1 km = 0.008983°  (constant, independent of longitude)
# Longitude: 1° = 111.32 × cos(lat) km
#   At Bay Area center (~37.6°N): cos(37.6°) = 0.7934
#   1 km ≈ 1 / (111.32 × 0.7934) = 0.01134°
#
# We use a fixed longitude step computed at the grid center latitude
# for a uniform rectilinear grid (matches advisor's paper methodology).
BAY_CENTER_LAT = 37.6
CELL_SIZE_KM = 1.0
CELL_SIZE_LAT_DEG = CELL_SIZE_KM / 111.32                          # ≈ 0.008983°
CELL_SIZE_LON_DEG = CELL_SIZE_KM / (111.32 * math.cos(math.radians(BAY_CENTER_LAT)))  # ≈ 0.01134°

# Bulk insert batch size — prevents memory overrun on 18,000 cells
BATCH_SIZE = 500


class Command(BaseCommand):
    help = (
        "Generate the static 1×1 km BayAreaGrid spatial cells for the "
        "9-county San Francisco Bay Area. One-time setup command."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview the number of cells that would be created without writing to the DB.",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete all existing BayAreaGrid rows before regenerating. USE WITH CAUTION.",
        )
        parser.add_argument(
            "--bbox",
            type=str,
            default=None,
            help=(
                "Custom bounding box as 'lat_min,lon_min,lat_max,lon_max'. "
                "Defaults to full 9-county Bay Area. "
                "Example: --bbox '37.2,-122.5,37.7,-121.9'"
            ),
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=BATCH_SIZE,
            help=f"Bulk insert batch size (default: {BATCH_SIZE}).",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        clear = options["clear"]
        batch_size = options["batch_size"]

        # -------------------------------------------------------
        # Parse bounding box
        # -------------------------------------------------------
        if options["bbox"]:
            try:
                parts = [float(x.strip()) for x in options["bbox"].split(",")]
                if len(parts) != 4:
                    raise ValueError
                lat_min, lon_min, lat_max, lon_max = parts
            except ValueError:
                raise CommandError(
                    "Invalid --bbox format. Expected: 'lat_min,lon_min,lat_max,lon_max'"
                )
        else:
            lat_min = BAY_AREA_LAT_MIN
            lon_min = BAY_AREA_LON_MIN
            lat_max = BAY_AREA_LAT_MAX
            lon_max = BAY_AREA_LON_MAX

        # -------------------------------------------------------
        # Calculate grid dimensions
        # -------------------------------------------------------
        n_rows = math.ceil((lat_max - lat_min) / CELL_SIZE_LAT_DEG)
        n_cols = math.ceil((lon_max - lon_min) / CELL_SIZE_LON_DEG)
        total_cells = n_rows * n_cols

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"\n{'=' * 60}\n"
                f"  Fight Fire With AI — Bay Area Grid Generator\n"
                f"{'=' * 60}"
            )
        )
        self.stdout.write(f"  Bounding box   : lat [{lat_min:.4f}, {lat_max:.4f}]")
        self.stdout.write(f"                   lon [{lon_min:.4f}, {lon_max:.4f}]")
        self.stdout.write(f"  Cell size      : {CELL_SIZE_KM} km × {CELL_SIZE_KM} km")
        self.stdout.write(f"  Cell size (°)  : {CELL_SIZE_LAT_DEG:.6f}° lat × {CELL_SIZE_LON_DEG:.6f}° lon")
        self.stdout.write(f"  Grid dimensions: {n_rows} rows × {n_cols} cols")
        self.stdout.write(
            self.style.SUCCESS(f"  Total cells    : {total_cells:,}")
        )
        self.stdout.write(f"  Bulk batch size: {batch_size}\n")

        if dry_run:
            self.stdout.write(
                self.style.WARNING("  DRY RUN — no data written to database.\n")
            )
            return

        # -------------------------------------------------------
        # Safety check — prevent accidental overwrite
        # -------------------------------------------------------
        existing_count = BayAreaGrid.objects.count()
        if existing_count > 0 and not clear:
            raise CommandError(
                f"\nBayAreaGrid already contains {existing_count:,} cells.\n"
                f"Use --clear to delete existing cells and regenerate,\n"
                f"or use --dry-run to preview without writing."
            )

        if clear and existing_count > 0:
            self.stdout.write(
                self.style.WARNING(f"  Clearing {existing_count:,} existing grid cells...")
            )
            BayAreaGrid.objects.all().delete()
            self.stdout.write(self.style.SUCCESS("  Cleared.\n"))

        # -------------------------------------------------------
        # Generate grid cells and bulk insert
        # -------------------------------------------------------
        self.stdout.write("  Generating grid cells...")
        start_time = time.monotonic()
        cells_created = 0
        batch = []

        for row in range(n_rows):
            for col in range(n_cols):
                # Bottom-left corner of this cell
                sw_lat = lat_min + (row * CELL_SIZE_LAT_DEG)
                sw_lon = lon_min + (col * CELL_SIZE_LON_DEG)

                # Top-right corner
                ne_lat = sw_lat + CELL_SIZE_LAT_DEG
                ne_lon = sw_lon + CELL_SIZE_LON_DEG

                # GeoJSON / PostGIS uses [lon, lat] order
                cell_polygon = Polygon(
                    (
                        (sw_lon, sw_lat),  # SW
                        (ne_lon, sw_lat),  # SE
                        (ne_lon, ne_lat),  # NE
                        (sw_lon, ne_lat),  # NW
                        (sw_lon, sw_lat),  # Close ring back to SW
                    ),
                    srid=4326,
                )

                centroid_lon = (sw_lon + ne_lon) / 2
                centroid_lat = (sw_lat + ne_lat) / 2
                centroid = Point(centroid_lon, centroid_lat, srid=4326)

                batch.append(
                    BayAreaGrid(
                        geometry=cell_polygon,
                        centroid=centroid,
                        row=row,
                        col=col,
                    )
                )

                if len(batch) >= batch_size:
                    with transaction.atomic():
                        BayAreaGrid.objects.bulk_create(batch, ignore_conflicts=True)
                    cells_created += len(batch)
                    batch = []
                    elapsed = time.monotonic() - start_time
                    pct = (cells_created / total_cells) * 100
                    self.stdout.write(
                        f"  Progress: {cells_created:>6,} / {total_cells:,} cells "
                        f"({pct:.1f}%) — {elapsed:.1f}s elapsed",
                        ending="\r",
                    )

        # Flush any remaining cells in the last partial batch
        if batch:
            with transaction.atomic():
                BayAreaGrid.objects.bulk_create(batch, ignore_conflicts=True)
            cells_created += len(batch)

        elapsed = time.monotonic() - start_time
        final_count = BayAreaGrid.objects.count()

        self.stdout.write("\n")
        self.stdout.write(
            self.style.SUCCESS(
                f"  ✓ Grid generation complete!\n"
                f"    Cells written : {cells_created:,}\n"
                f"    DB total      : {final_count:,}\n"
                f"    Time elapsed  : {elapsed:.2f} seconds\n"
            )
        )
        self.stdout.write(
            "  Next steps:\n"
            "    python manage.py load_terrain    # Load USGS DEM terrain data\n"
            "    python manage.py load_shelters   # Load FEMA/CalOES shelter data\n"
            "    python manage.py seed_czu_fire   # Seed CZU demo scenario data\n"
        )

        logger.info(
            '{"event": "generate_grid_complete", "cells_written": %d, '
            '"elapsed_seconds": %.2f}',
            cells_created,
            elapsed,
        )
