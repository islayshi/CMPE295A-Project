"""
Predictions Models — Fight Fire With AI

Core prediction storage: one row per grid cell per inference run.
This table is the bridge between the ML team's Vertex AI output
and the Django REST API that serves the React frontend.

Design Doc §1.1 Module 2: Database Engine
Design Doc §14: ML Integration Contract (source_model field values)
ML Interface Contract: docs/ml-team-interface-contract.md
"""

from django.contrib.gis.db import models
from grid.models import BayAreaGrid


# Source model choices — must match ML Interface Contract §3.2
SOURCE_MODEL_CHOICES = [
    ("unet", "U-Net (Spatial Segmentation)"),
    ("pinn", "PINN (Physics-Informed Neural Network)"),
    ("rl", "RL Agent (DQN/PPO Progression)"),
    ("ensemble", "Ensemble (Combined Voting)"),
    ("mock", "Mock (MOCK_INFERENCE=True fixture)"),
]


class FireIncident(models.Model):
    """
    Tracks the lifecycle of an active fire incident.
    """
    name = models.CharField(max_length=255, blank=True, help_text="Optional name of the fire incident")
    start_time = models.DateTimeField(db_index=True, help_text="When the fire was first detected")
    end_time = models.DateTimeField(null=True, blank=True, help_text="When the fire was contained/extinguished")
    is_active = models.BooleanField(default=True, db_index=True, help_text="Whether the fire is currently active")
    containment_status = models.FloatField(null=True, blank=True, help_text="Containment percentage (0.0 to 100.0)")

    class Meta:
        verbose_name = "Fire Incident"
        verbose_name_plural = "Fire Incidents"
        ordering = ["-start_time"]

    def __str__(self):
        return f"FireIncident {self.name or self.id} (Active: {self.is_active})"


class PredictionPolygon(models.Model):
    """
    A single fire risk prediction for one grid cell at one timestamp.

    Populated by: harvester.tasks.store_geojson_result()
    Served by: GET /api/predictions/current/ and /api/predictions/history/
    Cached in: Redis key `ffwai:current_risk_map` for fast REST polling.

    ML Output Contract (from docs/ml-team-interface-contract.md):
      properties.fire_probability → fire_probability
      properties.source_model     → source_model
      metadata.timestamp          → timestamp

    Research Reference:
      Malik et al. (Atmosphere 2021): fire probability per 1×1 km cell.
      Adhikari et al. (IEEE CCWC 2024): RL step-by-step progression output.
      Malik et al. (IEEE CCWC 2022): ensemble majority voting output.
    """
    grid = models.ForeignKey(
        BayAreaGrid,
        on_delete=models.CASCADE,
        related_name="predictions",
        help_text="The 1×1 km grid cell this prediction is for."
    )
    fire_incident = models.ForeignKey(
        FireIncident,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="predictions",
        help_text="The fire incident this prediction is associated with, if any."
    )
    timestamp = models.DateTimeField(
        db_index=True,
        help_text="UTC datetime of the inference run that produced this prediction."
    )
    lead_time_hours = models.IntegerField(
        default=0,
        help_text="Number of hours into the future this prediction applies to (0 = current state)."
    )
    target_timestamp = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="The exact future timestamp this prediction applies to (timestamp + lead_time_hours)."
    )
    source_model = models.CharField(
        max_length=50,
        choices=SOURCE_MODEL_CHOICES,
        help_text="Which ML model produced this prediction."
    )
    fire_probability = models.FloatField(
        help_text="Fire risk probability for this grid cell. Range: 0.0 (none) to 1.0 (certain)."
    )
    ml_metrics = models.JSONField(
        null=True,
        blank=True,
        help_text="Raw ML output metrics (p_low, w_unet, frp_mw, p_unet, fire_confidence, etc.)"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When this record was written to the database."
    )

    class Meta:
        verbose_name = "Prediction Polygon"
        verbose_name_plural = "Prediction Polygons"
        indexes = [
            models.Index(fields=["timestamp"]),
            models.Index(fields=["target_timestamp"]),
            models.Index(fields=["grid", "timestamp"]),
            models.Index(fields=["grid", "target_timestamp"]),
            models.Index(fields=["source_model", "timestamp"]),
        ]
        ordering = ["-timestamp", "lead_time_hours"]

    def __str__(self):
        return (
            f"Prediction[{self.source_model}] "
            f"grid={self.grid_id} "
            f"p={self.fire_probability:.2f} "
            f"ts={self.timestamp.date()}"
        )


class ModelPerformanceMetric(models.Model):
    """
    Evaluation metrics for a single model inference run.

    Displayed on the Model Performance Dashboard (FR-E10).
    Served by: GET /api/metrics/
    Populated after each inference run or manually by the ML team.

    Research Reference:
      Malik et al. (Atmosphere 2021): 92% accuracy on Combined Random Forest.
      Adhikari et al. (IEEE CCWC 2024): 85.87% accuracy on DQN+MLP.
      Malik et al. (IEEE CCWC 2022): 100% ensemble accuracy via Cellular Automata.
    """
    model_name = models.CharField(
        max_length=50,
        choices=SOURCE_MODEL_CHOICES,
        help_text="Which model these metrics are for."
    )
    run_date = models.DateTimeField(
        auto_now_add=True,
        help_text="When this evaluation was recorded."
    )
    accuracy = models.FloatField(null=True, blank=True, help_text="Overall accuracy (0.0–1.0).")
    precision = models.FloatField(null=True, blank=True, help_text="Precision score (0.0–1.0).")
    recall = models.FloatField(null=True, blank=True, help_text="Recall score (0.0–1.0).")
    f1_score = models.FloatField(null=True, blank=True, help_text="F1 score (harmonic mean of precision/recall).")
    auc_roc = models.FloatField(null=True, blank=True, help_text="Area Under ROC Curve (0.0–1.0).")
    notes = models.TextField(
        blank=True,
        help_text="Optional notes about this run (e.g., 'CZU Lightning Complex validation, Aug 2020')."
    )

    class Meta:
        verbose_name = "Model Performance Metric"
        verbose_name_plural = "Model Performance Metrics"
        ordering = ["-run_date"]

    def __str__(self):
        return f"Metrics[{self.model_name}] acc={self.accuracy} auc={self.auc_roc} @ {self.run_date.date()}"
