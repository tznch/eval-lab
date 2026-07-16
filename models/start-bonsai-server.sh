#!/usr/bin/env bash
# Start Bonsai-27B Q1_0 via unsloth llama-server on :8081
set -euo pipefail

LLAMA_SERVER="${LLAMA_SERVER:-$HOME/.unsloth/llama.cpp/llama-server}"
THREADS="${LLAMA_THREADS:-$(nproc)}"
PORT="${LLAMA_PORT:-8081}"
MODEL_PATH="${BONSAI_MODEL_PATH:-data/models/bonsai-27b-q1/Bonsai-27B-Q1_0.gguf}"

if [[ ! -x "$LLAMA_SERVER" ]]; then
  echo "Error: llama-server not found at $LLAMA_SERVER"
  exit 1
fi

if [[ ! -f "$MODEL_PATH" ]]; then
  echo "Error: model not found at $MODEL_PATH"
  echo "Run: python scripts/download_bonsai.py"
  exit 1
fi

echo "Starting Bonsai-27B Q1_0"
echo "  binary: $LLAMA_SERVER"
echo "  model:  $MODEL_PATH"
echo "  port:   $PORT"

exec "$LLAMA_SERVER" \
  -m "$MODEL_PATH" \
  -t "$THREADS" \
  --port "$PORT" \
  --host 127.0.0.1 \
  --reasoning off
