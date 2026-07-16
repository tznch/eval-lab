#!/usr/bin/env bash
# Stop local llama-server instances (one model at a time — frees RAM for the next).
set -euo pipefail

PORTS=(8080 8081 8082)
stopped=0

for port in "${PORTS[@]}"; do
  if ss -tln 2>/dev/null | grep -q ":${port} "; then
    echo "Stopping listener on :${port} ..."
    if command -v fuser >/dev/null 2>&1; then
      fuser -k "${port}/tcp" 2>/dev/null || true
    fi
    stopped=1
  fi
done

# Fallback: any stray llama-server not bound to our ports yet
if pgrep -x llama-server >/dev/null 2>&1; then
  echo "Stopping remaining llama-server processes ..."
  pkill -x llama-server 2>/dev/null || true
  stopped=1
fi

sleep 2

if [[ "$stopped" -eq 1 ]]; then
  echo "Model servers stopped."
else
  echo "No model servers running."
fi
