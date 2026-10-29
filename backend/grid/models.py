"""
Grid Models — Fight Fire With AI

Defines the static 1×1 km spatial grid covering the 9-county
San Francisco Bay Area. This grid is the foundational spatial
unit for all ML predictions and vegetation indices.

Design Doc §1.1 Module 2: Database Engine
Implementation Plan v4: BayAreaGrid + VegetationIndex models

Research References:
  - Malik et al. (Atmosphere 2021): 1×1 km grid, 63 cells,
    NDVI/EVI/NDWI from Landsat 8 via GEE.
  - Adhikari et al. (IEEE CCWC 2024): grid-based RL environment.
"""

from django.contrib.gis.db import models


class BayAreaGrid(models.Model):
    """
    A single 1×1 km grid cell covering the SF Bay Area.

    Generated once via the `generate_grid.py` management command.
    18,000 cells total across the 9-county region at 1×1 km resolution.
    Bounding box: center lat=37.55, lon=-122.15 (aligned with ML team's U-Net).

    All ML predictions and vegetation indices
    reference this table via ForeignKey.
    """
    geometry = models.PolygonField(
        srid=4326,
        help_text="1×1 km grid cell polygon in WGS84 (EPSG:4326)."
    )
    centroid = models.PointField(
        srid=4326,
        help_text="Pre-computed centroid for fast spatial lookups."
    )
    row = models.IntegerField(help_text="Grid row index (0-based, south to north).")
    col = models.IntegerField(help_text="Grid column index (0-based, west to east).")

    class Meta:
        verbose_name = "Bay Area Grid Cell"
        verbose_name_plural = "Bay Area Grid Cells"
        unique_together = [("row", "col")]
        indexes = [
            models.Index(fields=["row", "col"]),
        ]

    def __str__(self):
        return f"Grid[{self.row},{self.col}] id={self.pk}"

class VegetationIndex(models.Model):
    """
    Periodic vegetation indices per grid cell from Google Earth Engine.

    Data source: Landsat 8/9 (GEE collection: LANDSAT/LC09/C02/T1_L2)
    Updated: approximately every 8-16 days (Landsat revisit cycle).
    Fetched by Celery task: harvester.tasks.fetch_vegetation_indices

    Research Reference (all three advisor papers):
      NDVI/EVI/NDWI are critical training features used across
      Malik et al. (2021), Adhikari et al. (2024), Malik et al. (2022).

    NOTE FOR ML TEAM: This table is your primary vegetation data source.
    Query via: VegetationIndex.objects.filter(grid=cell, date=latest_date)
    """
    grid = models.ForeignKey(
        BayAreaGrid,
        on_delete=models.CASCADE,
        related_name="vegetation_indices",
        help_text="The grid cell this vegetation data belongs to."
    )
    date = models.DateField(
        db_index=True,
        help_text="Date this vegetation measurement was captured."
    )
    ndvi = models.FloatField(
        help_text=(
            "Normalized Difference Vegetation Index (-1 to 1). "
            "High values indicate dense green vegetation."
        )
    )
    evi = models.FloatField(
        null=True,
        blank=True,
        help_text="Enhanced Vegetation Index. More sensitive than NDVI in dense canopy."
    )
    ndwi = models.FloatField(
        null=True,
        blank=True,
        help_text="Normalized Difference Water Index. Proxy for fuel moisture content."
    )

    class Meta:
        verbose_name = "Vegetation Index"
        verbose_name_plural = "Vegetation Indices"
        unique_together = [("grid", "date")]
        indexes = [
            models.Index(fields=["date"]),
            models.Index(fields=["grid", "date"]),
        ]

    def __str__(self):
        return f"VegIndex[{self.date}] grid={self.grid_id} NDVI={self.ndvi:.3f}"
