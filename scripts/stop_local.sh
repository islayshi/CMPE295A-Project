#!/bin/bash
# scripts/stop_local.sh — Fight Fire With AI
# Shuts down local development services and Docker containers.

cd "$(dirname "$0")/.."
PROJECT_ROOT=$(pwd)

echo "Stopping Fight Fire With AI development services..."

# Kill processes by port
for PORT in 8000 8001 5173; do
    PID=$(lsof -ti tcp:$PORT)
    if [ -n "$PID" ]; then
        echo "Stopping process on port $PORT (PID $PID)..."
        kill -9 $PID 2>/dev/null || true
    fi
done

# Kill Celery processes
pkill -f "celery -A core" 2>/dev/null || true

echo "Stopping Docker containers..."
docker compose down

echo "All services stopped."
