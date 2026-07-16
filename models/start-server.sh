#!/usr/bin/env bash
# Start a local target via llama-server (OpenAI-compatible API).
# Set LLAMA_SERVER and LLAMA_HF_MODEL (or rely on defaults below).
set -euo pipefail

LLAMA_SERVER="${LLAMA_SERVER:-$HOME/.unsloth/llama.cpp/llama-server}"
THREADS="${LLAMA_THREADS:-$(nproc)}"
PORT="${LLAMA_PORT:-8080}"
# Override with your HF GGUF repo:quant, e.g. org/Model-GGUF:Q4_K_M
MODEL="${LLAMA_HF_MODEL:-unsloth/gemma-4-26B-A4B-it-GGUF:UD-Q4_K_XL}"

if [[ ! -x "$LLAMA_SERVER" ]]; then
  echo "Error: llama-server not found at $LLAMA_SERVER"
  echo "Set LLAMA_SERVER to your llama-server binary, or install one."
  exit 1
fi

echo "Starting llama-server"
echo "  binary:  $LLAMA_SERVER"
echo "  model:   $MODEL"
echo "  threads: $THREADS"
echo "  port:    $PORT"

exec "$LLAMA_SERVER" \
  -hf "$MODEL" \
  --spec-type draft-mtp --spec-draft-n-max 2 \
  -t "$THREADS" \
  --port "$PORT" \
  --host 127.0.0.1 \
  --reasoning off
