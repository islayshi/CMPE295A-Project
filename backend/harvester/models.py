"""
Harvester Models — Fight Fire With AI

The harvester app is primarily task-based (Celery). It does not
own significant Django models. Pipeline state is tracked via
Celery task results (Redis) rather than the database.

If a HarvestRun audit log is needed in future, add it here.
"""

from django.db import models


class HarvestRun(models.Model):
    """
    Optional audit log for each Celery harvest + inference cycle.
    Tracks success/failure for observability (NFR-O01).
    """
    run_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=[("success", "Success"), ("partial", "Partial"), ("failed", "Failed")],
        default="success",
    )
    ml_adapter_response_code = models.IntegerField(null=True, blank=True)
    predictions_written = models.IntegerField(default=0)
    error_message = models.TextField(blank=True)
    duration_seconds = models.FloatField(null=True, blank=True)

    class Meta:
        verbose_name = "Harvest Run"
        verbose_name_plural = "Harvest Runs"
        ordering = ["-run_at"]

    def __str__(self):
        return f"HarvestRun[{self.status}] @ {self.run_at}"
