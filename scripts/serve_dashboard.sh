#!/usr/bin/env bash
# Build and serve live dashboard (FastAPI + HTMX) on :3100
# Default bind is localhost only (safe for published scripts).
# Remote browser over SSH:  ssh -L 3100:127.0.0.1:3100 user@host
# Or opt-in LAN bind:       DASHBOARD_HOST=0.0.0.0 make dashboard-serve
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PORT="${DASHBOARD_PORT:-3100}"
HOST="${DASHBOARD_HOST:-127.0.0.1}"
PROMPTFOO_PORT="${PROMPTFOO_VIEW_PORT:-15500}"
START_PROMPTFOO="${START_PROMPTFOO:-1}"

.venv/bin/python scripts/build_dashboard.py

if [[ "$START_PROMPTFOO" == "1" ]] && command -v promptfoo >/dev/null 2>&1; then
  if ! ss -tln 2>/dev/null | grep -q ":${PROMPTFOO_PORT} "; then
    echo "Starting promptfoo view on :${PROMPTFOO_PORT} ..."
    mkdir -p results/logs
    (cd eval/promptfoo && promptfoo view -p "$PROMPTFOO_PORT" -n >>../../results/logs/promptfoo-view.log 2>&1 &)
    sleep 2
  fi
fi

port_is_listening() {
  local p=$1
  # Only treat IPv4 wildcard/localhost as occupied — an SSH -L on [::1] must not steal the port.
  ss -tln 2>/dev/null | grep -E "127\\.0\\.0\\.1:${p}\\s|0\\.0\\.0\\.0:${p}\\s|\\*:${p}\\s" >/dev/null
}

port_is_our_dashboard() {
  local p=$1
  curl -sf "http://127.0.0.1:${p}/api/run-status" >/dev/null 2>&1
}

if port_is_listening "$PORT"; then
  if port_is_our_dashboard "$PORT"; then
    echo "Dashboard already running on :${PORT}"
    echo "Open http://127.0.0.1:${PORT}/"
    if [[ "$HOST" != "127.0.0.1" && "$HOST" != "localhost" ]]; then
      echo "(Process may still be bound to a previous host; restart to apply DASHBOARD_HOST=${HOST})"
    fi
    exit 0
  fi
  echo "[WARN] Port ${PORT} is in use — trying next ports ..."
  for try in $(seq "$PORT" $((PORT + 20))); do
    if ! port_is_listening "$try"; then
      PORT=$try
      break
    fi
  done
fi

echo ""
echo "Live dashboard:  http://127.0.0.1:${PORT}/"
echo "  JSON exports:  http://127.0.0.1:${PORT}/exports/combined_report.json"
echo "  Promptfoo UI:  http://127.0.0.1:${PROMPTFOO_PORT}/"
echo "  Run status:    http://127.0.0.1:${PORT}/api/run-status"
echo "  Bind:          ${HOST}:${PORT}"
if [[ "$HOST" == "127.0.0.1" || "$HOST" == "localhost" ]]; then
  echo "  Remote access: ssh -L ${PORT}:127.0.0.1:${PORT} <user>@<host>"
  echo "                 or DASHBOARD_HOST=0.0.0.0 make dashboard-serve  # LAN (opt-in)"
fi
echo ""

RELOAD_FLAG=""
if [[ "${DASHBOARD_RELOAD:-0}" == "1" ]]; then
  RELOAD_FLAG="--reload"
fi

exec .venv/bin/uvicorn scripts.dashboard_api:app --host "$HOST" --port "$PORT" $RELOAD_FLAG
