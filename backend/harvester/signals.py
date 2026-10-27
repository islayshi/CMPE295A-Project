"""
Harvester Signals — Fight Fire With AI
Handles Celery lifecycle signals such as worker_ready for automated cache and data warmup.
"""
import logging
from celery.signals import worker_ready

try:
    from harvester.tasks import (
        fetch_wind_data,
        fetch_airnow_aqi,
        trigger_active_inference,
        archive_old_predictions,
    )
except ImportError:
    from backend.harvester.tasks import (
        fetch_wind_data,
        fetch_airnow_aqi,
        trigger_active_inference,
        archive_old_predictions,
    )

logger = logging.getLogger(__name__)


@worker_ready.connect
def on_worker_ready(sender, **kwargs):
    """
    Automated Celery Startup Warmup & Containment:
    Dispatches wind data, AQI data, active inference scout tasks, and automated incident containment
    immediately on Celery worker startup to self-heal and pre-warm Redis and PostGIS without manual intervention.
    """
    logger.info('{"event": "worker_ready", "action": "triggering_startup_warmup"}')
    archive_old_predictions.delay()
    fetch_wind_data.delay()
    fetch_airnow_aqi.delay()
    trigger_active_inference.delay()
