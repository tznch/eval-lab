"""Load and update project .env files (secrets stay in .env, never in profiles)."""

from __future__ import annotations

import os
import re
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"

# Keys the Overview UI may set. Values never appear in GET responses — only masked hints.
MANAGED_SECRET_KEYS = (
    "HF_TOKEN",
    "OPENROUTER_API_KEY",
)


def load_project_env() -> None:
    load_dotenv(ROOT / ".env")
    overlay = ROOT / ".env.profile"
    if overlay.is_file():
        load_dotenv(overlay, override=True)


def _validate_env_value(key: str, value: str) -> None:
    if "\r" in value or "\n" in value:
        raise ValueError(f"{key} must not contain newline characters")


def _format_env_value(value: str) -> str:
    if any(char in value for char in " #=\"'"):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


def mask_secret(value: str | None) -> str | None:
    if not value:
        return None
    text = value.strip()
    if len(text) <= 8:
        return "••••••••"
    return f"{text[:4]}…{text[-4:]}"


def secret_status(env: dict[str, str] | None = None) -> dict[str, dict]:
    e = env if env is not None else dict(os.environ)
    # Prefer HF_TOKEN; accept aliases for status display
    hf = (e.get("HF_TOKEN") or e.get("HF_FULL_ACCESS") or e.get("HUGGING_FACE_HUB_TOKEN") or "").strip()
    or_key = (e.get("OPENROUTER_API_KEY") or "").strip()
    return {
        "hf_token": {
            "configured": bool(hf),
            "hint": mask_secret(hf),
        },
        "openrouter_api_key": {
            "configured": bool(or_key),
            "hint": mask_secret(or_key),
        },
    }


_KEY_LINE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=")


def upsert_env_file(path: Path, updates: dict[str, str]) -> None:
    """Set or replace keys in a dotenv file. Empty string removes the key."""
    for key, value in updates.items():
        _validate_env_value(key, value)

    existing: list[str] = []
    if path.is_file():
        existing = path.read_text(encoding="utf-8").splitlines()

    seen: set[str] = set()
    out: list[str] = []
    for line in existing:
        m = _KEY_LINE.match(line)
        if not m:
            out.append(line)
            continue
        key = m.group(1)
        if key not in updates:
            out.append(line)
            continue
        seen.add(key)
        value = updates[key]
        if value == "":
            continue  # drop line
        out.append(f"{key}={_format_env_value(value)}")

    for key, value in updates.items():
        if key in seen or value == "":
            continue
        out.append(f"{key}={_format_env_value(value)}")

    path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(out)
    if text and not text.endswith("\n"):
        text += "\n"
    path.write_text(text, encoding="utf-8")


def save_managed_secrets(
    *,
    hf_token: str | None = None,
    openrouter_api_key: str | None = None,
    path: Path | None = None,
) -> dict[str, dict]:
    """
    Persist secrets to .env and update process env.
    None = leave unchanged; empty string = clear.
    """
    updates: dict[str, str] = {}
    if hf_token is not None:
        updates["HF_TOKEN"] = hf_token.strip()
    if openrouter_api_key is not None:
        updates["OPENROUTER_API_KEY"] = openrouter_api_key.strip()

    if updates:
        target = path or ENV_PATH
        upsert_env_file(target, updates)
        for key, value in updates.items():
            if value:
                os.environ[key] = value
            else:
                os.environ.pop(key, None)
        # Keep HF aliases in sync when HF_TOKEN is set/cleared
        if "HF_TOKEN" in updates:
            if updates["HF_TOKEN"]:
                os.environ["HUGGING_FACE_HUB_TOKEN"] = updates["HF_TOKEN"]
            else:
                os.environ.pop("HUGGING_FACE_HUB_TOKEN", None)

    load_project_env()
    return secret_status()
