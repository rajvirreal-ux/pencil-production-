#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Activate venv
if [ ! -d ".venv" ]; then
  echo "[ERROR] .venv not found. Run: python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi
source .venv/bin/activate

# Check .env exists
if [ ! -f ".env" ]; then
  echo "[ERROR] .env not found. Copy .env.example to .env and fill in your credentials."
  exit 1
fi

PORT="${APP_PORT:-8000}"
echo "Starting Pencil Production Line HMI on http://localhost:${PORT}"
uvicorn backend.main:app --host 0.0.0.0 --port "${PORT}" --reload
