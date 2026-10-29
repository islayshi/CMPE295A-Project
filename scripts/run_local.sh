#!/bin/bash
# scripts/run_local.sh — Fight Fire With AI
# Starts the full local development environment with Docker ML services,
# Celery worker, Celery beat, FastAPI ML Adapter, Django backend, and React UI.

set -e

cd "$(dirname "$0")/.."
PROJECT_ROOT=$(pwd)

echo "1. Starting Docker containers (PostgreSQL/PostGIS, Redis, U-Net, PINN)..."
docker compose up -d --build


echo "2. Waiting for PostgreSQL and Redis to become healthy..."
for i in {1..30}; do
    if docker compose exec -T db pg_isready -U "${DB_USER:-ffwai_user}" -d "${DB_NAME:-ffwai_db}" > /dev/null 2>&1 && \
       docker compose exec -T redis redis-cli ping 2>/dev/null | grep -q PONG; then
        echo "   ✔ Database and Redis are online and accepting connections."
        break
    fi
    sleep 1
done

echo "   Running database migrations..."
source .venv/bin/activate
(cd backend && python manage.py migrate --noinput)

echo "3. Opening 5 Terminal windows for local services..."

# Clean up any leftover background celery processes before starting new ones
pkill -9 -f "celery" 2>/dev/null || true

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

echo "4. Waiting for FastAPI ML Adapter (port 8001) to become ready..."
for i in {1..30}; do
    if curl -s http://localhost:8001/health | grep -q '"status":"ok"'; then
        echo "   ✔ FastAPI ML Adapter is online and accepting requests!"
        break
    fi
    sleep 1
done

echo ""
echo "=== Development Environment Started ==="
echo "Django Backend:   http://localhost:8000"
echo "FastAPI Adapter:  http://localhost:8001"
echo "U-Net Service:    http://localhost:8081 (Docker)"
echo "PINN Service:     http://localhost:8082 (Docker)"
echo "React Frontend:   http://localhost:5173"
echo "To shut down all services, run: ./scripts/stop_local.sh"
