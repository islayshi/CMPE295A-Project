#!/bin/bash
# scripts/run_local.sh

cd "$(dirname "$0")/.."
PROJECT_ROOT=$(pwd)

echo "Starting Docker containers..."
docker compose up -d

echo "Opening 5 Terminal windows..."

# Ensure Terminal is running before trying to open scripts in it
open -a Terminal
sleep 1

# Terminal 1: Django Backend
osascript -e "tell application \"Terminal\" to do script \"cd '$PROJECT_ROOT' && source .venv/bin/activate && cd backend && python manage.py runserver\""

# Terminal 2: Celery Worker
osascript -e "tell application \"Terminal\" to do script \"cd '$PROJECT_ROOT' && source .venv/bin/activate && cd backend && celery -A core worker -l info --pool=solo\""

# Terminal 3: Vite Frontend
osascript -e "tell application \"Terminal\" to do script \"cd '$PROJECT_ROOT' && cd frontend && npm run dev\""

# Terminal 4: FastAPI ML Adapter
osascript -e "tell application \"Terminal\" to do script \"cd '$PROJECT_ROOT' && source .venv/bin/activate && cd ml_adapter && uvicorn main:app --reload --port 8001\""

# Terminal 5: Celery Beat
osascript -e "tell application \"Terminal\" to do script \"cd '$PROJECT_ROOT' && source .venv/bin/activate && cd backend && celery -A core beat -l info\""

echo "Done!"
