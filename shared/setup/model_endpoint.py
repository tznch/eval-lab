"""Resolve OpenAI-compatible endpoint for a model id from environment."""

from __future__ import annotations

import os
import re
from pathlib import Path

from shared.profiles.registry import MODEL_REGISTRY

# Bundled example defaults (last resort when env unset)
_BUNDLED_DEFAULTS: dict[str, tuple[str, str]] = {
    "gemma": ("http://127.0.0.1:8080/v1", "gemma-4-26b-a4b"),
    "bonsai": ("http://127.0.0.1:8081/v1", "bonsai-27b-q1"),
    "qwen27": ("http://127.0.0.1:8082/v1", "qwen3.6-27b-iq2"),
}


def _env_key(model_id: str, suffix: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]", "_", model_id).upper()
    return f"{normalized}_{suffix}"


def resolve_model_endpoint(model_id: str, env: dict[str, str] | None = None) -> tuple[str | None, str | None]:
    """Return (base_url, model_name) or (None, None) if not configured."""
    e = env if env is not None else os.environ
    model = model_id.strip()
    if not model:
        return None, None

    # Per-model overrides are most specific (e.g. BONSAI_BASE_URL).
    per_base = (e.get(_env_key(model, "BASE_URL")) or "").strip()
    per_name = (e.get(_env_key(model, "MODEL_NAME")) or "").strip()
    if per_base and per_name:
        return per_base, per_name

    configured_models = [
        m.strip() for m in (e.get("MODEL") or e.get("MODELS") or "").split(",") if m.strip()
    ]
    if model in configured_models or not configured_models:
        base = (e.get("TARGET_MODEL_BASE_URL") or "").strip()
        name = (e.get("TARGET_MODEL_NAME") or "").strip()
        if base and name:
            return base, name

    if model in _BUNDLED_DEFAULTS:
        return _BUNDLED_DEFAULTS[model]

    return None, None


def model_weights_path(model_id: str) -> Path | None:
    spec = MODEL_REGISTRY.get(model_id)
    if not spec:
        return None
    hint = spec.get("gguf_hint")
    filename = spec.get("filename")
    if not hint or not filename:
        return None
    root = Path(__file__).resolve().parents[2]
    return root / hint / filename
