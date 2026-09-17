"""
Predictions Serializers — Fight Fire With AI

Converts FireRiskPrediction DB rows into GeoJSON Feature objects
conforming to the ML Interface Contract output spec.

ML Interface Contract §3.1: Each Feature must have:
  geometry.type       = "Polygon"
  geometry.coordinates = [[lon, lat], ...]
  properties.grid_id
  properties.fire_probability
  properties.risk_label
  properties.source_model
"""

from rest_framework import serializers
from .models import FireRiskPrediction


class FireRiskPredictionGeoJSONSerializer(serializers.ModelSerializer):
    """Serializes a FireRiskPrediction to a GeoJSON Feature object."""

    type = serializers.SerializerMethodField()
    geometry = serializers.SerializerMethodField()
    properties = serializers.SerializerMethodField()

    class Meta:
        model = FireRiskPrediction
        fields = ["type", "geometry", "properties"]

    def get_type(self, obj):
        return "Feature"

    def get_geometry(self, obj):
        """Returns the grid cell polygon as GeoJSON geometry."""
        return {
            "type": "Polygon",
            "coordinates": list(obj.grid.geometry.coords),
        }

    def get_properties(self, obj):
        return {
            "grid_id": obj.grid_id,
            "fire_probability": obj.fire_probability,
            "risk_label": obj.risk_label,
            "source_model": obj.source_model,
            "timestamp": obj.timestamp.isoformat(),
        }
