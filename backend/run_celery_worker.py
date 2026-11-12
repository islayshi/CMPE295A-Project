"""
Celery Worker Runner with Cloud Run Health Server — Fight Fire With AI
======================================================================
Cloud Run requires all container instances to bind and listen on $PORT
for health and startup probes, even when operating as background worker pools.

This runner starts an unprivileged HTTP health check server on $PORT in a
daemon thread, then launches the Celery worker process.
"""

import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


class CloudRunWorkerHealthHandler(BaseHTTPRequestHandler):
    """Responds with 200 OK to Cloud Run startup and liveness probes."""

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"celery-worker healthy\n")

    def log_message(self, format, *args):
        # Silence access logs to prevent spamming Cloud Logging
        pass


def start_health_server(port: int):
    server = HTTPServer(("0.0.0.0", port), CloudRunWorkerHealthHandler)
    server.serve_forever()


def main():
    port = int(os.environ.get("PORT", "8080"))
    
    # Start health server daemon thread before launching Celery
    health_thread = threading.Thread(target=start_health_server, args=(port,), daemon=True)
    health_thread.start()

    concurrency = os.environ.get("CELERY_CONCURRENCY", "2")
    log_level = os.environ.get("CELERY_LOG_LEVEL", "info")

    celery_cmd = [
        sys.executable,
        "-m",
        "celery",
        "-A",
        "core",
        "worker",
        "-l",
        log_level,
        f"--concurrency={concurrency}",
    ]

    # Run Celery and forward exit code
    exit_code = subprocess.call(celery_cmd)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
