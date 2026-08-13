#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# start.sh — HyderabadUrbanReality multi-service launcher
#
# NOTE: On Render, deploy each service SEPARATELY:
#   • Web Service  → Root Dir: backend-dotnet  Start: dotnet run
#   • Static Site  → Root Dir: frontend        Build: npm run build
#   • (optional)   → Root Dir: backend         Start: python app.py
#
# This script is for self-hosted / Docker single-container use.
# ─────────────────────────────────────────────────────────────
set -euo pipefail

PIDS=()

# ── Cleanup on exit ──────────────────────────────────────────
cleanup() {
  echo "==> Stopping all services..."
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  wait
}
trap cleanup SIGINT SIGTERM EXIT

# ── Python Flask backend — LOCAL DEV ONLY, skip on Render ───
# Flask is a scraper utility, not needed in production.
# Set ENABLE_FLASK=true explicitly to run it.
if [ "${ENABLE_FLASK:-false}" = "true" ] && [ -f "backend/app.py" ]; then
  python_cmd=python3
  command -v python3 >/dev/null 2>&1 || python_cmd=python
  echo "==> Starting Python Flask backend..."
  (cd backend && "$python_cmd" -m pip install -r requirements.txt -q && "$python_cmd" app.py) &
  PIDS+=($!)
  echo "    Flask started (PID ${PIDS[-1]})"
else
  echo "==> Skipping Python Flask backend (set ENABLE_FLASK=true to enable)"
fi

# ── .NET backend ─────────────────────────────────────────────
if [ -d "backend-dotnet" ]; then
  if ! command -v dotnet >/dev/null 2>&1; then
    echo "ERROR: dotnet not found — skipping .NET backend"
  else
    echo "==> Starting .NET backend..."
    (cd backend-dotnet && dotnet run --launch-profile http) &
    PIDS+=($!)
    echo "    .NET started (PID ${PIDS[-1]})"
  fi
fi

# ── Angular dev server (only for local dev, not production) ──
if [ "${SERVE_FRONTEND:-false}" = "true" ] && [ -d "frontend" ]; then
  if ! command -v npm >/dev/null 2>&1; then
    echo "ERROR: npm not found — skipping Angular frontend"
  else
    echo "==> Starting Angular frontend..."
    (cd frontend && [ ! -d node_modules ] && npm install; npm start) &
    PIDS+=($!)
    echo "    Angular started (PID ${PIDS[-1]})"
  fi
fi

if [ ${#PIDS[@]} -eq 0 ]; then
  echo "ERROR: No services started. Check that backend/ and backend-dotnet/ exist."
  exit 1
fi

echo ""
echo "==> All services running. PIDs: ${PIDS[*]}"
echo "    Press Ctrl+C to stop."
echo ""

# ── Wait for any service to exit ─────────────────────────────
wait -n 2>/dev/null || wait "${PIDS[0]}"
echo "==> A service exited. Shutting down remaining services."
exit 1
