#!/bin/bash
# scripts/run_local.sh — Fight Fire With AI
# Starts the full local development environment with Docker ML services,
# Celery worker, Celery beat, FastAPI ML Adapter, Django backend, and React UI.

set -e

cd "$(dirname "$0")/.."
PROJECT_ROOT=$(pwd)

echo "1. Starting Docker containers (PostgreSQL/PostGIS, Redis, U-Net, PINN)..."
docker compose up -d

echo "2. Waiting for database and Redis..."
sleep 2

echo "3. Warming up Redis cache & PostGIS with live telemetry and fire predictions..."
./.venv/bin/python scripts/seed_cache.py || true

echo "4. Opening 5 Terminal windows for local services..."

# Ensure Terminal is running on macOS
open -a Terminal
sleep 1

# Terminal 1: Django Backend (port 8000)
osascript -e "tell application \"Terminal\" to do script \"cd '$PROJECT_ROOT' && source .venv/bin/activate && cd backend && python manage.py runserver 8000\""

# Terminal 2: Celery Worker (Active Scout & Harvesters)
osascript -e "tell application \"Terminal\" to do script \"cd '$PROJECT_ROOT' && source .venv/bin/activate && export PYTHONPATH=backend:ml_adapter:ml_services/unet_service && cd backend && celery -A core worker -l info --pool=solo\""

# Terminal 3: Celery Beat (Periodic Scheduler)
osascript -e "tell application \"Terminal\" to do script \"cd '$PROJECT_ROOT' && source .venv/bin/activate && cd backend && celery -A core beat -l info\""

# Terminal 4: FastAPI ML Adapter (port 8001 - live docker dispatch)
osascript -e "tell application \"Terminal\" to do script \"cd '$PROJECT_ROOT' && source .venv/bin/activate && export PYTHONPATH=backend:ml_adapter:ml_services/unet_service && MOCK_INFERENCE=\${MOCK_INFERENCE:-false} uvicorn ml_adapter.main:app --reload --port 8001\""

# Terminal 5: React Frontend (port 5173)
osascript -e "tell application \"Terminal\" to do script \"cd '$PROJECT_ROOT' && cd frontend && npm run dev\""

echo ""
echo "=== Development Environment Started ==="
echo "Django Backend:   http://localhost:8000"
echo "FastAPI Adapter:  http://localhost:8001"
echo "U-Net Service:    http://localhost:8081 (Docker)"
echo "PINN Service:     http://localhost:8082 (Docker)"
echo "React Frontend:   http://localhost:5173"
echo "To shut down all services, run: ./scripts/stop_local.sh"
