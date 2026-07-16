#!/usr/bin/env bash
# Full eval pipeline: prepare data + run Promptfoo, DeepEval, RAGAS for each target model.
#
# Usage:
#   ./scripts/run_all_evals.sh                  # gemma + bonsai, default limits
#   ./scripts/run_all_evals.sh --model gemma    # single model
#   ./scripts/run_all_evals.sh --models gemma,bonsai
#   ./scripts/run_all_evals.sh --skip-setup     # skip venv/npm install
#   PROMPTFOO_LIMIT=10 DEEPEVAL_LIMIT=3 RAGAS_LIMIT=5 ./scripts/run_all_evals.sh
#
# Env overrides:
#   PROMPTFOO_LIMIT   (default: 20)
#   DEEPEVAL_LIMIT    (default: 5)
#   RAGAS_LIMIT       (default: 10)
#   EVAL_DATASET      (default: sciq) — feta|nq|sciq for promptfoo+deepeval
#   RAGAS_CONFIG      (default: EVAL_DATASET) — dataset for RAGAS
#   MODEL / MODELS    (default: gemma,bonsai) — comma-separated

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Read selected keys from .env without sourcing secrets into the shell parser
_env_get() {
  local key=$1
  [[ -f "$ROOT/.env" ]] || return 0
  local line
  line="$(grep -E "^${key}=" "$ROOT/.env" | tail -1 || true)"
  [[ -n "$line" ]] || return 0
  printf '%s' "${line#*=}" | tr -d '"' | tr -d "'"
}

VENV="${ROOT}/.venv/bin/python"
PROMPTFOO_LIMIT="${PROMPTFOO_LIMIT:-20}"
DEEPEVAL_LIMIT="${DEEPEVAL_LIMIT:-5}"
RAGAS_LIMIT="${RAGAS_LIMIT:-10}"
EVAL_DATASET="${EVAL_DATASET:-$(_env_get EVAL_DATASET)}"
EVAL_DATASET="${EVAL_DATASET:-sciq}"
RAGAS_CONFIG="${RAGAS_CONFIG:-$EVAL_DATASET}"
SKIP_SETUP=0
MODELS_CSV="${MODELS:-${MODEL:-gemma,bonsai}}"

# Propagate HF token aliases for child Python processes
if [[ -z "${HF_TOKEN:-}" ]]; then
  HF_TOKEN="$(_env_get HF_TOKEN)"
  [[ -n "$HF_TOKEN" ]] || HF_TOKEN="$(_env_get HF_FULL_ACCESS)"
  export HF_TOKEN
fi
[[ -n "${HF_TOKEN:-}" ]] && export HUGGING_FACE_HUB_TOKEN="$HF_TOKEN"

declare -a FAILED=()
declare -a MODELS=()

log()  { printf '\n[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }
warn() { printf '[WARN] %s\n' "$*" >&2; }

status_start() {
  local framework=$1
  "$VENV" -c "
from shared.reporting.run_status import start_step
start_step('${EVAL_DATASET}', '${framework}')
" 2>/dev/null || true
}

status_done() {
  local framework=$1 ok=$2 artifact=$3
  "$VENV" -c "
from shared.reporting.run_status import complete_step
complete_step('${EVAL_DATASET}', '${framework}', ok=${ok}, artifact='${artifact}')
" 2>/dev/null || true
}

usage() {
  sed -n '2,12p' "$0"
  exit 0
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-setup) SKIP_SETUP=1 ;;
    --model|--models|-m) MODELS_CSV="$2"; shift ;;
    -h|--help)    usage ;;
    *)            echo "Unknown option: $1"; usage ;;
  esac
  shift
done

IFS=',' read -ra MODELS <<< "$MODELS_CSV"

# --- model registry ---
model_port() {
  case "$1" in
    gemma)  echo 8080 ;;
    bonsai) echo 8081 ;;
    qwen27) echo 8082 ;;
    *) echo "Unknown model: $1" >&2; exit 1 ;;
  esac
}
model_url() {
  case "$1" in
    gemma)  echo "http://127.0.0.1:8080/v1" ;;
    bonsai) echo "http://127.0.0.1:8081/v1" ;;
    qwen27) echo "http://127.0.0.1:8082/v1" ;;
  esac
}
model_name() {
  case "$1" in
    gemma)  echo "gemma-4-26b-a4b" ;;
    bonsai) echo "bonsai-27b-q1" ;;
    qwen27) echo "qwen3.6-27b-iq2" ;;
  esac
}
model_temp() {
  case "$1" in
    gemma)  echo "0.2" ;;
    bonsai) echo "0.7" ;;
    qwen27) echo "0.2" ;;
  esac
}
model_start_script() {
  case "$1" in
    gemma)  echo "models/start-server.sh" ;;
    bonsai) echo "models/start-bonsai-server.sh" ;;
    qwen27) echo "models/start-qwen27-server.sh" ;;
  esac
}

wait_for_server() {
  local port=$1
  local tries="${2:-120}"
  for ((i=1; i<=tries; i++)); do
    if curl -sf "http://127.0.0.1:${port}/v1/models" >/dev/null 2>&1; then
      return 0
    fi
    sleep 5
  done
  return 1
}

ensure_server() {
  local model=$1
  local port
  port="$(model_port "$model")"
  if ss -tln 2>/dev/null | grep -q ":${port} "; then
    log "Server :${port} (${model}) already running"
    return 0
  fi
  log "Starting ${model} server on :${port} ..."
  bash "$(model_start_script "$model")" >"results/logs/${model}-server.log" 2>&1 &
  if ! wait_for_server "$port"; then
    echo "Server failed to start on :${port}. See results/logs/${model}-server.log" >&2
    exit 1
  fi
  log "${model} server ready on :${port}"
}

prepare_all() {
  log "=== PREPARE ==="

  if [[ "$SKIP_SETUP" -eq 0 ]]; then
    log "Python deps ..."
    if command -v uv >/dev/null 2>&1; then
      uv venv .venv 2>/dev/null || true
      uv pip install -e ".[dev]" --python .venv/bin/python
    else
      python3 -m venv .venv 2>/dev/null || true
      .venv/bin/pip install -e ".[dev]"
    fi
    if ! command -v promptfoo >/dev/null 2>&1; then
      log "Installing promptfoo ..."
      npm install -g promptfoo || warn "promptfoo install failed — install manually"
    fi
  fi

  if [[ "$EVAL_DATASET" == "sciq" ]]; then
    log "Download SciQ (allenai/sciq) ..."
    "$VENV" scripts/download_sciq.py --split validation --limit 200
  elif [[ "$EVAL_DATASET" == "financial_qa" || "$EVAL_DATASET" == "ecommerce_faq" || "$EVAL_DATASET" == "bitext_intent" ]]; then
    log "Download real-world track (${EVAL_DATASET}) ..."
    "$VENV" scripts/download_realworld.py "$EVAL_DATASET"
  elif [[ "$EVAL_DATASET" != "bitext_retail" ]]; then
    log "Download UDA-QA (${EVAL_DATASET}) ..."
    "$VENV" scripts/download_uda_qa.py --config "$EVAL_DATASET" 2>/dev/null || true
    if [[ "$EVAL_DATASET" != "nq" && "$RAGAS_CONFIG" == "nq" ]]; then
      "$VENV" scripts/download_uda_qa.py --config nq 2>/dev/null || true
    fi
  fi

  log "Prepare ${EVAL_DATASET} samples ..."
  "$VENV" scripts/dataset_cli.py prepare --dataset "$EVAL_DATASET" --limit "${PREPARE_LIMIT:-50}" 2>/dev/null \
    || "$VENV" scripts/prepare_samples.py --config "$EVAL_DATASET" --limit "${PREPARE_LIMIT:-50}"

  if [[ "$RAGAS_CONFIG" != "$EVAL_DATASET" && "$RAGAS_CONFIG" != "bitext_retail" ]]; then
    "$VENV" scripts/prepare_samples.py --config "$RAGAS_CONFIG" --limit 50 2>/dev/null || true
  fi

  log "Download target model weights (if missing) ..."
  need_bonsai=0
  need_qwen=0
  for m in "${MODELS[@]}"; do
    [[ "$m" == "bonsai" ]] && need_bonsai=1
    [[ "$m" == "qwen27" ]] && need_qwen=1
  done
  if [[ "$need_bonsai" -eq 1 && ! -f data/models/bonsai-27b-q1/Bonsai-27B-Q1_0.gguf ]]; then
    "$VENV" scripts/download_bonsai.py
  elif [[ "$need_bonsai" -eq 1 ]]; then
    log "Bonsai model already cached"
  fi
  if [[ "$need_qwen" -eq 1 && ! -f data/models/qwen3.6-27b-iq2/Qwen3.6-27B-UD-IQ2_XXS.gguf ]]; then
    "$VENV" scripts/download_qwen27.py
  elif [[ "$need_qwen" -eq 1 ]]; then
    log "Qwen3.6-27B IQ2_XXS already cached"
  fi

  log "Smoke test judge ..."
  "$VENV" scripts/smoke_judge.py

  mkdir -p results/{promptfoo,deepeval,ragas,logs}
}

export_model_env() {
  local model=$1
  export EVAL_MODEL_ID="$model"
  export EVAL_DATASET
  export TARGET_MODEL_BASE_URL="$(model_url "$model")"
  export TARGET_MODEL_NAME="$(model_name "$model")"
  export TARGET_TEMPERATURE="${TARGET_TEMPERATURE:-$(model_temp "$model")}"
  local tag="t${TARGET_TEMPERATURE}"
  export PROMPTFOO_OUTPUT="${ROOT}/results/promptfoo/${model}/${tag}/${EVAL_DATASET}/output.json"
  export DEEPEVAL_OUTPUT="${ROOT}/results/deepeval/${model}/${tag}/${EVAL_DATASET}/junit.xml"
  export RAGAS_OUTPUT_TAG="${tag}"
}

run_promptfoo() {
  local model=$1
  log "  [promptfoo] ${model} (${PROMPTFOO_LIMIT} tests) ..."
  export_model_env "$model"
  status_start "promptfoo"
  if "$VENV" scripts/run_promptfoo_eval.py >>"results/logs/${model}-promptfoo.log" 2>&1; then
    log "  [promptfoo] ${model} → ${PROMPTFOO_OUTPUT}"
    status_done "promptfoo" true "${PROMPTFOO_OUTPUT}"
  else
    warn "  [promptfoo] ${model} finished with failures (see results/logs/${model}-promptfoo.log)"
    FAILED+=("${model}/promptfoo")
    status_done "promptfoo" false "${PROMPTFOO_OUTPUT}"
  fi
}

run_deepeval() {
  local model=$1
  log "  [deepeval] ${model} (${DEEPEVAL_LIMIT} tests) ..."
  export_model_env "$model"
  export DEEPEVAL_LIMIT
  status_start "deepeval"
  local de_out="${DEEPEVAL_OUTPUT:-results/deepeval/${model}/t${TARGET_TEMPERATURE}/${EVAL_DATASET}/junit.xml}"
  if "$VENV" scripts/run_deepeval.py >>"results/logs/${model}-deepeval.log" 2>&1; then
    log "  [deepeval] ${model} → ${de_out}"
    status_done "deepeval" true "${de_out}"
  else
    warn "  [deepeval] ${model} had test failures (see results/logs/${model}-deepeval.log)"
    FAILED+=("${model}/deepeval")
    status_done "deepeval" false "${de_out}"
  fi
}

run_ragas() {
  local model=$1
  log "  [ragas] ${model} (${RAGAS_CONFIG}, limit=${RAGAS_LIMIT}) ..."
  export_model_env "$model"
  local rg_out="results/ragas/${model}/${RAGAS_OUTPUT_TAG:-t${TARGET_TEMPERATURE}}/${RAGAS_CONFIG}_scores.csv"
  status_start "ragas"
  if "$VENV" eval/ragas/run.py --config "$RAGAS_CONFIG" --limit "$RAGAS_LIMIT" --model-id "$model" \
    >>"results/logs/${model}-ragas.log" 2>&1; then
    log "  [ragas] ${model} → ${rg_out}"
    status_done "ragas" true "${rg_out}"
  else
    warn "  [ragas] ${model} failed (see results/logs/${model}-ragas.log)"
    FAILED+=("${model}/ragas")
    status_done "ragas" false "${rg_out}"
  fi
}

run_model_evals() {
  local model=$1
  log "=== EVAL: ${model} ==="
  run_promptfoo "$model"
  run_deepeval "$model"
  run_ragas "$model"
}

print_summary() {
  log "=== SUMMARY ==="
  "$VENV" scripts/build_dashboard.py
  printf 'Models: %s\n' "${MODELS[*]}"
  printf 'Dataset: %s\n' "$EVAL_DATASET"
  printf 'Limits: promptfoo=%s deepeval=%s ragas=%s/%s\n' \
    "$PROMPTFOO_LIMIT" "$DEEPEVAL_LIMIT" "$RAGAS_CONFIG" "$RAGAS_LIMIT"
  echo
  echo "Results:"
  for model in "${MODELS[@]}"; do
    echo "  ${model}:"
    echo "    promptfoo → results/promptfoo/${model}/${EVAL_DATASET}/output.json"
    echo "    deepeval  → results/deepeval/${model}/${EVAL_DATASET}/junit.xml"
    echo "    ragas     → results/ragas/${model}/${RAGAS_CONFIG}_scores.csv"
    echo "    logs      → results/logs/${model}-*.log"
  done
  echo
  echo "Dashboard:  http://127.0.0.1:3100/index.html"
  echo "Report:     http://127.0.0.1:3100/report.html"
  echo "Failures:   http://127.0.0.1:3100/failures.html"
  echo "Export:     results/report/combined_report.json"
  if [[ ${#FAILED[@]} -gt 0 ]]; then
    echo
    warn "Some steps reported failures:"
    printf '  - %s\n' "${FAILED[@]}"
    exit 1
  fi
  log "All evals completed."
}

# --- main ---
prepare_all

log "=== START SERVERS ==="
if [[ ${#MODELS[@]} -gt 1 ]]; then
  warn "Multiple models requested — starting servers in parallel (ensure enough RAM)."
  warn "For 27B models use one at a time: make stop-servers && make portfolio-qwen27"
fi
for model in "${MODELS[@]}"; do
  ensure_server "$model"
done

for model in "${MODELS[@]}"; do
  run_model_evals "$model"
done

print_summary
