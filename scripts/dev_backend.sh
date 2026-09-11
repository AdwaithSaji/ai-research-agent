#!/usr/bin/env bash
# Runs the backend API locally with auto-reload.
set -euo pipefail
cd "$(dirname "$0")/../backend"
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi
./.venv/bin/pip install -r requirements.txt -q 2>/dev/null || ./.venv/Scripts/pip install -r requirements.txt -q
./.venv/bin/python -m uvicorn app.main:app --reload --port 8000 2>/dev/null || ./.venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8000
