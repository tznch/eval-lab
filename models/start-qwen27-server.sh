#!/usr/bin/env bash
# Qwen3.6-27B UD-IQ2_XXS — whitepaper conventional 2-bit baseline on :8082
set -euo pipefail

LLAMA_SERVER="${LLAMA_SERVER:-$HOME/.unsloth/llama.cpp/llama-server}"
THREADS="${LLAMA_THREADS:-$(nproc)}"
PORT="${QWEN_PORT:-8082}"
MODEL_PATH="${QWEN_MODEL_PATH:-data/models/qwen3.6-27b-iq2/Qwen3.6-27B-UD-IQ2_XXS.gguf}"

if [[ ! -x "$LLAMA_SERVER" ]]; then
  echo "Error: llama-server not found at $LLAMA_SERVER"
  exit 1
fi

if [[ ! -f "$MODEL_PATH" ]]; then
  echo "Error: model not found at $MODEL_PATH"
  echo "Run: python scripts/download_qwen27.py"
  exit 1
fi

echo "Starting Qwen3.6-27B UD-IQ2_XXS (whitepaper comparable)"
echo "  binary: $LLAMA_SERVER"
echo "  model:  $MODEL_PATH"
echo "  port:   $PORT"

exec "$LLAMA_SERVER" \
  -m "$MODEL_PATH" \
  -t "$THREADS" \
  --port "$PORT" \
  --host 127.0.0.1 \
  --reasoning off
