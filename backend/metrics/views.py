"""
Metrics Views — Fight Fire With AI

Serves model performance evaluation data for the Performance Dashboard.
Data is written to predictions.ModelPerformanceMetric by the ML team
or by the harvester after each inference run.

Design Doc §8: GET /api/metrics/
FR-E10: Model Performance Dashboard.
"""

import logging
from rest_framework.decorators import api_view
from rest_framework.response import Response
from predictions.models import ModelPerformanceMetric

logger = logging.getLogger(__name__)


@api_view(["GET"])
def model_metrics(request):
    """
    GET /api/metrics/

    Returns performance metrics for all model runs, ordered by most recent.
    Displayed on the frontend Model Performance Dashboard panel.

    Query params:
      model (optional): Filter by model name (unet | pinn | rl | ensemble)
      limit (optional): Number of records to return (default: 20)

    Response:
      {
        "count": 3,
        "metrics": [
          {
            "model_name": "ensemble",
            "run_date": "2026-09-15T06:00:00Z",
            "accuracy": 0.92,
            "precision": 0.89,
            "recall": 0.94,
            "f1_score": 0.915,
            "auc_roc": 0.97,
            "notes": "CZU Lightning Complex validation"
          }
        ]
      }

    FR-E10: Model Performance Dashboard requirement.
    """
    queryset = ModelPerformanceMetric.objects.all().order_by("-run_date")

    model_filter = request.query_params.get("model")
    if model_filter:
        queryset = queryset.filter(model_name=model_filter)

    limit = int(request.query_params.get("limit", 20))
    queryset = queryset[:limit]

    metrics_list = [
        {
            "model_name": m.model_name,
            "run_date": m.run_date.isoformat(),
            "accuracy": m.accuracy,
            "precision": m.precision,
            "recall": m.recall,
            "f1_score": m.f1_score,
            "auc_roc": m.auc_roc,
            "notes": m.notes,
        }
        for m in queryset
    ]

    return Response({"count": len(metrics_list), "metrics": metrics_list})
