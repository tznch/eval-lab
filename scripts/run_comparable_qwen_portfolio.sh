#!/usr/bin/env bash
# Run portfolio evals on Qwen3.6-27B IQ2_XXS only — same datasets/judge as Bonsai.
# Sequential: stops Bonsai/other servers first (do NOT run two 27B models in parallel).
#
# Usage:
#   ./scripts/run_comparable_qwen_portfolio.sh
#   TARGET_TEMPERATURE=0.2 PORTFOLIO_LIMIT=25 ./scripts/run_comparable_qwen_portfolio.sh --skip-setup
#
# Comparable to (whitepaper):
#   - Qwen3.6-27B IQ2_XXS (~9.4 GB conventional quant) vs Bonsai Q1 (~3.6 GB)
#   - Same base architecture as Bonsai (Qwen3.6-27B representation transform)

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

VENV="${ROOT}/.venv/bin/python"
MODEL=qwen27
PORTFOLIO_LIMIT="${PORTFOLIO_LIMIT:-25}"
TARGET_TEMPERATURE="${TARGET_TEMPERATURE:-0.2}"
SKIP_SETUP=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-setup) SKIP_SETUP=1; shift ;;
    *) echo "Unknown: $1"; exit 1 ;;
  esac
done

log() { printf '\n[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }

log "=== STOP OTHER MODEL SERVERS (sequential eval) ==="
bash scripts/stop_model_servers.sh

log "=== DOWNLOAD QWEN3.6-27B IQ2_XXS (if missing) ==="
if [[ ! -f data/models/qwen3.6-27b-iq2/Qwen3.6-27B-UD-IQ2_XXS.gguf ]]; then
  "$VENV" scripts/download_qwen27.py
else
  log "Qwen IQ2_XXS already cached"
fi

log "=== PORTFOLIO EVAL: ${MODEL} (temp=${TARGET_TEMPERATURE}) ==="
export MODEL TARGET_TEMPERATURE
export PORTFOLIO_DATASETS="${PORTFOLIO_DATASETS:-$("$VENV" -c "from shared.datasets.registry import portfolio_dataset_ids; print(','.join(portfolio_dataset_ids()))")}"

if [[ "$SKIP_SETUP" -eq 0 ]]; then
  "$VENV" scripts/download_realworld.py all --limit 500 2>/dev/null || true
  "$VENV" scripts/download_sciq.py --split validation --limit 200 2>/dev/null || true
fi

IFS=',' read -ra DATASETS <<< "$PORTFOLIO_DATASETS"
for ds in "${DATASETS[@]}"; do
  log "Prepare ${ds} (limit=${PORTFOLIO_LIMIT}) ..."
  "$VENV" scripts/prepare_samples.py --config "$ds" --limit "$PORTFOLIO_LIMIT"
done

for ds in "${DATASETS[@]}"; do
  log "--- Track: ${ds} ---"
  EVAL_DATASET="$ds" PROMPTFOO_LIMIT="$PORTFOLIO_LIMIT" DEEPEVAL_LIMIT="$PORTFOLIO_LIMIT" \
    RAGAS_LIMIT="$PORTFOLIO_LIMIT" RAGAS_CONFIG="$ds" \
    bash scripts/run_all_evals.sh --model "$MODEL" --skip-setup || true
done

log "=== ANALYSIS + DASHBOARD ==="
"$VENV" -c "from shared.reporting.failure_analysis import export_failure_analysis; print(export_failure_analysis())"
EVAL_DATASET=sciq "$VENV" scripts/build_dashboard.py

log "Qwen comparable portfolio complete."
log "Compare: results/promptfoo/{bonsai,qwen27}/ and report.html"
log "External baseline: docs/benchmarks/comparable-baseline.md"
