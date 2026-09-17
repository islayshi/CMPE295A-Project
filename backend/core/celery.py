"""
Celery Application — Fight Fire With AI

Configures the Celery worker and Beat scheduler.
The broker is Redis (Memorystore in GCP, docker-compose in local dev).

Design Doc §1.1 Module 1: Celery daily cron orchestrator
Architecture Guide: Celery is the async task coordinator
ADR-003: Daily inference cadence decision

Usage (local dev — run from backend/ directory):
  # Start worker:
  celery -A core worker --loglevel=info

  # Start Beat scheduler (in a separate terminal):
  celery -A core beat --loglevel=info
"""

import os
from celery import Celery

# Tell Django which settings module to use
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

app = Celery("fightfirewai")

# Load Celery config from Django settings (CELERY_* keys)
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks in all INSTALLED_APPS
# Celery will find harvester/tasks.py automatically
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Diagnostic task for verifying Celery worker connectivity."""
    print(f"[debug_task] Request: {self.request!r}")
