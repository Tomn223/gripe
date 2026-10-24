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
  [[ -f .dev-pids ]] && while read -r pid; do kill "$pid" 2>/dev/null || true; done < .dev-pids
  rm -f .dev-pids; echo "stopped"; exit 0
fi

if [[ ! -x backend/.venv/bin/uvicorn ]]; then
  echo "› creating backend venv"; python3 -m venv backend/.venv
  backend/.venv/bin/pip install -q -r backend/requirements.txt
fi
if [[ ! -d frontend/node_modules ]]; then
  echo "› installing frontend deps"; (cd frontend && npm install --silent)
fi
[[ -f backend/.env ]] || echo "› no backend/.env (fine: cached topics work offline; set XAI_API_KEY for live topics)"

run_backend() { (cd backend && exec .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port "$BACKEND_PORT"); }
run_frontend() { (cd frontend && GRIPE_BACKEND_URL="http://127.0.0.1:$BACKEND_PORT" GRIPE_FRONTEND_PORT="$FRONTEND_PORT" exec npx vite --port "$FRONTEND_PORT" --strictPort); }

if [[ "${1:-}" == "--bg" ]]; then
  mkdir -p logs
  run_backend > logs/backend.log 2>&1 & echo $! > .dev-pids
  run_frontend > logs/frontend.log 2>&1 & echo $! >> .dev-pids
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
