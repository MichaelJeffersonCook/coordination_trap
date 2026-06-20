#!/usr/bin/env bash
# One-command local start for the AI-Native Product OS prototype.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "Creating virtualenv..."
  python3 -m venv .venv
  ./.venv/bin/pip install -q --upgrade pip
  ./.venv/bin/pip install -q -r requirements.txt
fi

# Seed the Work Graph if the DB doesn't exist yet (the app also auto-seeds).
if [ ! -f "workgraph.db" ]; then
  echo "Seeding Work Graph..."
  ./.venv/bin/python -m app.seed
fi

echo "Starting on http://localhost:8000 ..."
exec ./.venv/bin/uvicorn app.main:app --reload --port 8000
