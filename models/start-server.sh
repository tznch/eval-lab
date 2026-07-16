#!/usr/bin/env bash
# Start Gemma via unsloth's llama-server (CPU, OpenAI-compatible API on :8080)
set -euo pipefail

LLAMA_SERVER="${LLAMA_SERVER:-$HOME/.unsloth/llama.cpp/llama-server}"
THREADS="${LLAMA_THREADS:-$(nproc)}"
PORT="${LLAMA_PORT:-8080}"
# Default: already cached on this minipc (17 GB Q4). Override with LLAMA_HF_MODEL env.
MODEL="${LLAMA_HF_MODEL:-unsloth/gemma-4-26B-A4B-it-GGUF:UD-Q4_K_XL}"

if [[ ! -x "$LLAMA_SERVER" ]]; then
  echo "Error: llama-server not found at $LLAMA_SERVER"
  echo "Install Unsloth: curl -fsSL https://unsloth.ai/install.sh | sh"
  exit 1
fi

echo "Starting llama-server via Unsloth"
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
