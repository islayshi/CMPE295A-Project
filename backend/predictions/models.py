"""
Predictions Models — Fight Fire With AI

Core prediction storage: one row per grid cell per inference run.
This table is the bridge between the ML team's Vertex AI output
and the Django REST API that serves the React frontend.

Design Doc §1.1 Module 2: Database Engine
Design Doc §14: ML Integration Contract (source_model field values)
ML Interface Contract: docs/ml-team-interface-contract.md
"""

from django.db import models
from grid.models import BayAreaGrid


# Risk label choices enforced at the DB level
RISK_LABEL_CHOICES = [
    ("HIGH_RISK", "High Risk (≥ 0.70)"),
    ("MEDIUM_RISK", "Medium Risk (0.40–0.69)"),
    ("LOW_RISK", "Low Risk (< 0.40)"),
]

# Source model choices — must match ML Interface Contract §3.2
SOURCE_MODEL_CHOICES = [
    ("unet", "U-Net (Spatial Segmentation)"),
    ("pinn", "PINN (Physics-Informed Neural Network)"),
    ("rl", "RL Agent (DQN/PPO Progression)"),
    ("ensemble", "Ensemble (Combined Voting)"),
    ("mock", "Mock (MOCK_INFERENCE=True fixture)"),
]


class FireRiskPrediction(models.Model):
    """
    A single fire risk prediction for one grid cell at one timestamp.

    Populated by: harvester.tasks.store_geojson_result()
    Served by: GET /api/predictions/current/ and /api/predictions/history/
    Cached in: Redis key `ffwai:current_risk_map` for fast REST polling.

    ML Output Contract (from docs/ml-team-interface-contract.md):
      properties.fire_probability → fire_probability
      properties.risk_label       → risk_label
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
    timestamp = models.DateTimeField(
        db_index=True,
        help_text="UTC datetime of the inference run that produced this prediction."
    )
    source_model = models.CharField(
        max_length=50,
        choices=SOURCE_MODEL_CHOICES,
        help_text="Which ML model produced this prediction."
    )
    fire_probability = models.FloatField(
        help_text="Fire risk probability for this grid cell. Range: 0.0 (none) to 1.0 (certain)."
    )
    risk_label = models.CharField(
        max_length=20,
        choices=RISK_LABEL_CHOICES,
        help_text="Human-readable risk tier derived from fire_probability."
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When this record was written to the database."
    )

    class Meta:
        verbose_name = "Fire Risk Prediction"
        verbose_name_plural = "Fire Risk Predictions"
        indexes = [
            models.Index(fields=["timestamp"]),
            models.Index(fields=["grid", "timestamp"]),
            models.Index(fields=["source_model", "timestamp"]),
        ]
        ordering = ["-timestamp"]

    def __str__(self):
        return (
            f"Prediction[{self.source_model}] "
            f"grid={self.grid_id} "
            f"p={self.fire_probability:.2f} "
            f"label={self.risk_label} "
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
