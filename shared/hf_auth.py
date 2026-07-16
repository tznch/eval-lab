"""Resolve HuggingFace token from .env (HF_TOKEN or HF_FULL_ACCESS)."""

from __future__ import annotations

import os

from dotenv import load_dotenv


def get_hf_token() -> str | None:
    """Return a non-empty HF token, or None if unset."""
    load_dotenv()
    for key in ("HF_TOKEN", "HF_FULL_ACCESS", "HUGGING_FACE_HUB_TOKEN"):
        value = (os.getenv(key) or "").strip()
        if value:
            # Ensure libraries that only read HF_TOKEN see it
            os.environ.setdefault("HF_TOKEN", value)
            os.environ.setdefault("HUGGING_FACE_HUB_TOKEN", value)
            return value
    return None
