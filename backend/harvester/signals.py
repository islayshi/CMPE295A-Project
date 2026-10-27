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
    )
except ImportError:
    from backend.harvester.tasks import (
        fetch_wind_data,
        fetch_airnow_aqi,
        trigger_active_inference,
    )

logger = logging.getLogger(__name__)


@worker_ready.connect
def on_worker_ready(sender, **kwargs):
    """
    Automated Celery Startup Warmup:
    Dispatches wind data, AQI data, and active inference scout tasks immediately
    on Celery worker startup to self-heal and pre-warm Redis and PostGIS without seed_cache.py.
    """
    logger.info('{"event": "worker_ready", "action": "triggering_startup_warmup"}')
    fetch_wind_data.delay()
    fetch_airnow_aqi.delay()
    trigger_active_inference.delay()
