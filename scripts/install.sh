#!/bin/bash
# scripts/install.sh
set -e

cd "$(dirname "$0")/.."

echo "Creating virtual environment..."
python3 -m venv .venv
source .venv/bin/activate

echo "Installing backend dependencies..."
cd backend
pip install -r requirements.txt

echo "Installing ML adapter dependencies..."
cd ../ml_adapter
pip install -r requirements.txt

echo "Installing frontend dependencies..."
cd ../frontend
npm install

echo "Installation complete!"
