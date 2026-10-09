"""
Predictions Serializers — Fight Fire With AI

Converts PredictionPolygon DB rows into GeoJSON Feature objects
conforming to the ML Interface Contract output spec.

ML Interface Contract §3.1: Each Feature must have:
  geometry.type       = "Polygon"
  geometry.coordinates = [[lon, lat], ...]
  properties.grid_id
  properties.fire_probability
  properties.source_model
"""

from rest_framework import serializers
from .models import PredictionPolygon


class PredictionPolygonGeoJSONSerializer(serializers.ModelSerializer):
    """Serializes a PredictionPolygon to a GeoJSON Feature object."""

    type = serializers.SerializerMethodField()
    geometry = serializers.SerializerMethodField()
    properties = serializers.SerializerMethodField()

    class Meta:
        model = PredictionPolygon
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
        props = {
            "grid_id": obj.grid_id,
            "fire_probability": obj.fire_probability,
            "source_model": obj.source_model,
            "timestamp": obj.timestamp.isoformat(),
            "lead_time_hours": obj.lead_time_hours,
            "horizon_hours": obj.lead_time_hours,
        }
        if obj.target_timestamp:
            props["target_timestamp"] = obj.target_timestamp.isoformat()
        if obj.ml_metrics:
            props.update(obj.ml_metrics)
        return props
