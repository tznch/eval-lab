#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
VENV_PY="${ROOT}/.venv/bin/python"

echo "==> Upgrading Python package (editable + deps)"
uv pip install -U -e ".[dev]" --python "$VENV_PY"

echo "==> Upgrading Promptfoo (npm global)"
npm install -g promptfoo@latest || true

echo "==> Versions"
"$VENV_PY" - <<'PY'
import importlib.metadata as m
for name in ("ragas", "deepeval", "datasets", "huggingface_hub"):
    try:
        print(f"{name}=={m.version(name)}")
    except m.PackageNotFoundError:
        print(f"{name}=(not installed)")
PY
command -v promptfoo >/dev/null && promptfoo --version || echo "promptfoo=(not found on PATH)"
echo "Note: tools-update moves to latest releases and may change eval scores. Record versions with shared profiles for comparison."
