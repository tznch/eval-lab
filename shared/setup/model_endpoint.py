"""Resolve OpenAI-compatible endpoint for a model id from environment."""

from __future__ import annotations

import os
import re
from pathlib import Path

from shared.profiles.registry import MODEL_REGISTRY


def _env_key(model_id: str, suffix: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]", "_", model_id).upper()
    return f"{normalized}_{suffix}"


def resolve_model_endpoint(model_id: str, env: dict[str, str] | None = None) -> tuple[str | None, str | None]:
    """Return (base_url, model_name) or (None, None) if not configured."""
    e = env if env is not None else os.environ
    model = model_id.strip()
    if not model:
        return None, None

    # Per-model overrides are most specific (e.g. MY_MODEL_BASE_URL).
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

    return None, None


def model_weights_path(model_id: str) -> Path | None:
    """Legacy registry path lookup (usually unused; prefer {ID}_MODEL_PATH)."""
    spec = MODEL_REGISTRY.get(model_id)
    if not spec:
        return None
    hint = spec.get("gguf_hint")
    filename = spec.get("filename")
    if not hint or not filename:
        return None
    root = Path(__file__).resolve().parents[2]
    return root / hint / filename
