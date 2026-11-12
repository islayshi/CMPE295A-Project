"""
Tests for Cloud Run Celery worker runner health check server.
"""

from io import BytesIO
from unittest.mock import MagicMock
from run_celery_worker import CloudRunWorkerHealthHandler


def test_celery_worker_health_handler():
    """Verify that CloudRunWorkerHealthHandler responds with 200 OK and text payload."""
    handler = CloudRunWorkerHealthHandler.__new__(CloudRunWorkerHealthHandler)
    handler.wfile = BytesIO()
    handler.send_response = MagicMock()
    handler.send_header = MagicMock()
    handler.end_headers = MagicMock()

    handler.do_GET()

    handler.send_response.assert_called_once_with(200)
    handler.send_header.assert_called_once_with("Content-Type", "text/plain")
    handler.end_headers.assert_called_once()
    assert b"celery-worker healthy" in handler.wfile.getvalue()
