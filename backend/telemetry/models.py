"""
Telemetry Models — Fight Fire With AI

Static spatial data for emergency POIs (shelters, alert zones).
Wind and NWS alert data is ephemeral and stored in Redis cache,
not in the database. Only persistent spatial data lives here.

Design Doc §8: GET /api/telemetry/shelters/ and /api/telemetry/alerts/
FR-E04: Environmental telemetry (wind, alerts, vulnerability)
FR-E05: Emergency POIs from FEMA/CalOES
"""

from django.contrib.gis.db import models


class EmergencyShelter(models.Model):
    """
    FEMA/CalOES emergency evacuation shelter location.

    Loaded once via: `python manage.py load_shelters`
    Served by: GET /api/telemetry/shelters/
    Rendered by: Custom Mapbox HTML markers on the React map.

    FR-E05: Emergency POI display requirement.
    """
    name = models.CharField(max_length=255, help_text="Official shelter name.")
    location = models.PointField(srid=4326, help_text="Shelter GPS coordinates (WGS84).")
    address = models.TextField(blank=True, help_text="Full street address.")
    county = models.CharField(max_length=100, blank=True, help_text="Bay Area county name.")
    capacity = models.IntegerField(
        null=True,
        blank=True,
        help_text="Maximum shelter capacity (persons). Null if unknown."
    )
    source = models.CharField(
        max_length=50,
        default="FEMA",
        help_text="Data source (FEMA or CalOES)."
    )

    class Meta:
        verbose_name = "Emergency Shelter"
        verbose_name_plural = "Emergency Shelters"
        indexes = [models.Index(fields=["county"])]

    def __str__(self):
        return f"{self.name} ({self.county})"
