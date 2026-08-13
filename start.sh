#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [[ -f ".venv/bin/activate" ]]; then
  source ".venv/bin/activate"
fi

exec uvicorn main:app --host "${HOST:-0.0.0.0}" --port "${PORT:-8000}" ${UVICORN_RELOAD:+--reload}
