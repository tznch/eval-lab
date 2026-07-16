#!/usr/bin/env bash
# Build and serve live dashboard (FastAPI + HTMX) on :3100
# Legacy static pages at /legacy/* · Promptfoo UI on :15500
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PORT="${DASHBOARD_PORT:-3100}"
PROMPTFOO_PORT="${PROMPTFOO_VIEW_PORT:-15500}"
START_PROMPTFOO="${START_PROMPTFOO:-1}"

.venv/bin/python scripts/build_dashboard.py

if [[ "$START_PROMPTFOO" == "1" ]] && command -v promptfoo >/dev/null 2>&1; then
  if ! ss -tln 2>/dev/null | grep -q ":${PROMPTFOO_PORT} "; then
    echo "Starting promptfoo view on :${PROMPTFOO_PORT} ..."
    (cd eval/promptfoo && promptfoo view -p "$PROMPTFOO_PORT" -n >>../../results/logs/promptfoo-view.log 2>&1 &)
    sleep 2
  fi
fi

port_is_our_dashboard() {
  local p=$1
  curl -sf "http://127.0.0.1:${p}/api/run-status" >/dev/null 2>&1
}

if ss -tln 2>/dev/null | grep -q ":${PORT} "; then
  if port_is_our_dashboard "$PORT"; then
    echo "Dashboard already running on :${PORT}"
    echo "Open http://127.0.0.1:${PORT}/"
    exit 0
  fi
  echo "[WARN] Port ${PORT} is in use — trying next ports ..."
  for try in $(seq "$PORT" $((PORT + 20))); do
    if ! ss -tln 2>/dev/null | grep -q ":${try} "; then
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
echo ""

RELOAD_FLAG=""
if [[ "${DASHBOARD_RELOAD:-0}" == "1" ]]; then
  RELOAD_FLAG="--reload"
fi

exec .venv/bin/uvicorn scripts.dashboard_api:app --host 127.0.0.1 --port "$PORT" $RELOAD_FLAG
