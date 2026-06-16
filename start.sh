#!/usr/bin/env bash
# MyGameShelf — one-command launcher for Linux/macOS (and the deploy host).
# Starts the FastAPI backend and the Next.js frontend together; Ctrl+C stops both.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$root"

venv_py="$root/.venv/bin/python"

# 1. Backend venv + deps
if [ ! -x "$venv_py" ]; then
  echo "[setup] Creating Python venv (.venv)..."
  python3 -m venv .venv
  "$venv_py" -m pip install --upgrade pip -q
  echo "[setup] Installing backend dependencies..."
  "$venv_py" -m pip install -r requirements.txt
fi

# 2. .env sanity
if [ ! -f .env ]; then
  echo "[warn] No .env found. Copy .env.example to .env and fill it in."
elif ! grep -qE '^SUPABASE_JWT_SECRET=.+' .env; then
  echo "[warn] SUPABASE_JWT_SECRET is empty in .env — login/data calls will 500 until set."
fi

# 3. Frontend deps
if [ ! -d web/node_modules ]; then
  echo "[setup] Installing frontend dependencies..."
  (cd web && npm install)
fi

# 4. Launch both, kill both on exit
reload="--reload"
[ "${1:-}" = "--no-reload" ] && reload=""

pids=()
cleanup() {
  echo
  echo "[stop] Shutting down backend + frontend..."
  for pid in "${pids[@]}"; do kill "$pid" 2>/dev/null || true; done
}
trap cleanup EXIT INT TERM

echo "[run] FastAPI  -> http://localhost:8000"
"$venv_py" -m uvicorn api.main:app --port 8000 $reload &
pids+=($!)

echo "[run] Sync worker (Steam job queue)"
"$venv_py" worker.py &
pids+=($!)

echo "[run] Next.js  -> http://localhost:3000"
(cd web && npm run dev) &
pids+=($!)

echo
echo "All running. Open http://localhost:3000  —  press Ctrl+C to stop everything."
wait
