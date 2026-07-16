#!/usr/bin/env bash
# Run balanced real-world portfolio: sciq + fintech + ecommerce + support intent
#
# Usage:
#   ./scripts/run_portfolio_evals.sh --model bonsai
#   PORTFOLIO_LIMIT=25 ./scripts/run_portfolio_evals.sh --model bonsai --skip-setup
#
# Env:
#   PORTFOLIO_LIMIT   per-dataset sample count (default: 25)
#   PORTFOLIO_DATASETS  comma list (default: sciq,financial_qa,ecommerce_faq,bitext_intent)

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

VENV="${ROOT}/.venv/bin/python"
MODEL="${MODEL:-bonsai}"
PORTFOLIO_LIMIT="${PORTFOLIO_LIMIT:-25}"
PORTFOLIO_DATASETS="${PORTFOLIO_DATASETS:-$("$VENV" -c "from shared.datasets.registry import portfolio_dataset_ids; print(','.join(portfolio_dataset_ids()))")}"
SKIP_SETUP=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --model|-m) MODEL="$2"; shift 2 ;;
    --skip-setup) SKIP_SETUP=1; shift ;;
    *) echo "Unknown: $1"; exit 1 ;;
  esac
done

log() { printf '\n[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }

log "=== PORTFOLIO PREPARE ==="
if [[ "$SKIP_SETUP" -eq 0 ]]; then
  "$VENV" scripts/download_realworld.py all --limit 500 2>/dev/null || true
  "$VENV" scripts/download_sciq.py --split validation --limit 200 2>/dev/null || true
fi

IFS=',' read -ra DATASETS <<< "$PORTFOLIO_DATASETS"
for ds in "${DATASETS[@]}"; do
  log "Prepare ${ds} (limit=${PORTFOLIO_LIMIT}) ..."
  "$VENV" scripts/prepare_samples.py --config "$ds" --limit "$PORTFOLIO_LIMIT"
done

log "=== PORTFOLIO EVAL (${MODEL}, temp=${TARGET_TEMPERATURE:-auto}) ==="
export MODEL
case "$MODEL" in
  bonsai) _DEFAULT_TEMP="0.7" ;;
  qwen27) _DEFAULT_TEMP="0.2" ;;
  *) _DEFAULT_TEMP="0.2" ;;
esac
export TARGET_TEMPERATURE="${TARGET_TEMPERATURE:-$_DEFAULT_TEMP}"
TEMP_TAG="t${TARGET_TEMPERATURE}"
"$VENV" -c "
from shared.reporting.run_status import init_run
init_run('${MODEL}', '${TEMP_TAG}', '${PORTFOLIO_DATASETS}'.split(','), ['promptfoo','deepeval','ragas'])
" 2>/dev/null || true
for ds in "${DATASETS[@]}"; do
  log "--- Track: ${ds} ---"
  EVAL_DATASET="$ds" PROMPTFOO_LIMIT="$PORTFOLIO_LIMIT" DEEPEVAL_LIMIT="$PORTFOLIO_LIMIT" \
    RAGAS_LIMIT="$PORTFOLIO_LIMIT" RAGAS_CONFIG="$ds" \
    bash scripts/run_all_evals.sh --model "$MODEL" --skip-setup || true
done

log "=== ANALYSIS + DASHBOARD ==="
"$VENV" -c "from shared.reporting.run_status import finish_run; finish_run('complete')" 2>/dev/null || true
"$VENV" -c "from shared.reporting.failure_analysis import export_failure_analysis; print(export_failure_analysis())"
EVAL_DATASET=sciq "$VENV" scripts/build_dashboard.py

log "Portfolio complete. Open http://127.0.0.1:3100/failures.html"