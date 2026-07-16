#!/usr/bin/env bash
# One command: start model servers → run all evals → build & serve dashboard.
#
# Usage:
#   ./scripts/run_lab.sh
#   ./scripts/run_lab.sh --model bonsai
#   EVAL_DATASET=sciq PROMPTFOO_LIMIT=30 DEEPEVAL_LIMIT=30 RAGAS_LIMIT=30 ./scripts/run_lab.sh --model bonsai
#   MODEL=gemma ./scripts/run_lab.sh
#
# Opens:
#   http://127.0.0.1:3100/index.html     — home (framework buttons)
#   http://127.0.0.1:15500/              — promptfoo full interactive UI

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

EVAL_EXIT=0
PORTFOLIO=0
LAB_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --portfolio) PORTFOLIO=1; shift ;;
    *) LAB_ARGS+=("$1"); shift ;;
  esac
done

echo "╔══════════════════════════════════════════════════╗"
echo "║  LLM Eval Lab — servers + evals + dashboard      ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# 1–2: servers + evals
if [[ "$PORTFOLIO" -eq 1 ]]; then
  if ! bash "$ROOT/scripts/run_portfolio_evals.sh" "${LAB_ARGS[@]}"; then
    EVAL_EXIT=$?
    echo ""
    echo "[WARN] Portfolio eval failed (exit $EVAL_EXIT). Dashboard will still start."
  fi
elif ! bash "$ROOT/scripts/run_all_evals.sh" "${LAB_ARGS[@]}"; then
  EVAL_EXIT=$?
  echo ""
  echo "[WARN] Some eval steps failed (exit $EVAL_EXIT). Dashboard will still start."
fi

# 3: build dashboard + serve (blocks until Ctrl+C)
echo ""
echo "Starting dashboard server ..."
bash "$ROOT/scripts/serve_dashboard.sh"
