#!/usr/bin/env bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
cd "$DIR"

echo "========================================================"
echo " Starting NEXUS Development Environment"
echo "========================================================"

# Activate virtual environment if present
if [ -d ".venv" ]; then
  source .venv/bin/activate
fi

# Ensure migrations are applied
echo "--> Checking database migrations..."
alembic -c infra/database/alembic.ini upgrade head

# Function to kill all child processes on exit
cleanup() {
  echo ""
  echo "--> Shutting down NEXUS services..."
  kill $(jobs -p) 2>/dev/null || true
  exit 0
}
trap cleanup SIGINT SIGTERM EXIT

echo "--> Launching FastAPI Core Backend on port 8000..."
uvicorn services.api.nexus_api.main:app --host 0.0.0.0 --port 8000 &

echo "--> Launching Next.js Web Dashboard on port 3000..."
npm run --workspace=@nexus/dashboard dev &

echo "--> Launching Ambient Overlay Shell on port 5173..."
npm run --workspace=@nexus/ambient dev &

echo "========================================================"
echo " NEXUS is LIVE:"
echo " - Web Dashboard:  http://localhost:3000"
echo " - Core API & Docs: http://localhost:8000/docs"
echo " - Health Status:  http://localhost:8000/health"
echo " - Ambient Shell:  http://localhost:5173"
echo "========================================================"

wait
