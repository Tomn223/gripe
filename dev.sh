#!/usr/bin/env bash
# Gripe dev runner: sets up (first run) and starts the FastAPI backend + Vite frontend.
#   ./dev.sh            # foreground, Ctrl-C stops both
#   ./dev.sh --bg       # background, logs in logs/, PIDs in .dev-pids
#   ./dev.sh --stop     # stop background servers
set -euo pipefail
cd "$(dirname "$0")"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

if [[ "${1:-}" == "--stop" ]]; then
  [[ -f .dev-pids ]] && while read -r pid; do kill -- "-$pid" 2>/dev/null || kill "$pid" 2>/dev/null || true; done < .dev-pids
  rm -f .dev-pids; echo "stopped"; exit 0
fi

# Pick a Python (Windows Git Bash often has `python` or `py`, not a working `python3`).
PY=""
for c in python3 python "py -3"; do
  if $c -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' >/dev/null 2>&1; then PY="$c"; break; fi
done
[[ -n "$PY" ]] || { echo "Python 3.10+ not found (tried python3, python, py -3)"; exit 1; }
# venv layout: bin/ on macOS/Linux, Scripts/ on Windows
VBIN=bin; [[ -d backend/.venv/Scripts ]] && VBIN=Scripts
if [[ ! -e backend/.venv/$VBIN/uvicorn && ! -e backend/.venv/$VBIN/uvicorn.exe ]]; then
  echo "› creating backend venv"; [[ -d backend/.venv ]] || $PY -m venv backend/.venv
  VBIN=bin; [[ -d backend/.venv/Scripts ]] && VBIN=Scripts
  backend/.venv/$VBIN/python -m pip install -q -r backend/requirements.txt
fi
if [[ ! -d frontend/node_modules || frontend/package-lock.json -nt frontend/node_modules/.package-lock.json ]]; then
  echo "› installing frontend deps"; (cd frontend && npm install --silent)
fi
[[ -f backend/.env ]] || echo "› no backend/.env (fine: cached topics work offline; set XAI_API_KEY for live topics)"

export VBIN
run_backend() { (cd backend && exec .venv/$VBIN/python -m uvicorn app.main:app --host 0.0.0.0 --port "$BACKEND_PORT"); }
run_frontend() { (cd frontend && GRIPE_BACKEND_URL="http://127.0.0.1:$BACKEND_PORT" GRIPE_FRONTEND_PORT="$FRONTEND_PORT" exec npx vite --port "$FRONTEND_PORT" --strictPort); }

if [[ "${1:-}" == "--bg" ]]; then
  mkdir -p logs
  SETSID=""; command -v setsid >/dev/null && SETSID=setsid
  # each server gets its own process group so --stop can take down the whole tree
  $SETSID bash -c "$(declare -f run_backend); VBIN=$VBIN BACKEND_PORT=$BACKEND_PORT run_backend" > logs/backend.log 2>&1 & echo $! > .dev-pids
  $SETSID bash -c "$(declare -f run_frontend); BACKEND_PORT=$BACKEND_PORT FRONTEND_PORT=$FRONTEND_PORT run_frontend" > logs/frontend.log 2>&1 & echo $! >> .dev-pids
  echo "backend  → http://localhost:$BACKEND_PORT  (logs/backend.log)"
  echo "frontend → http://localhost:$FRONTEND_PORT  (logs/frontend.log)"
  exit 0
fi

trap 'kill 0' EXIT INT TERM
run_backend &
run_frontend &
echo "backend  → http://localhost:$BACKEND_PORT"
echo "frontend → http://localhost:$FRONTEND_PORT"
wait
