"""Universal local model server launch (llama-server) from env + registry."""

from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse

from shared.setup.model_endpoint import _env_key, model_weights_path

ROOT = Path(__file__).resolve().parents[2]


def resolve_llama_server(env: dict[str, str] | None = None) -> Path | None:
    e = env if env is not None else os.environ
    raw = (e.get("LLAMA_SERVER") or "").strip()
    if not raw:
        raw = str(Path.home() / ".unsloth/llama.cpp/llama-server")
    path = Path(raw).expanduser()
    return path if path.is_file() else None


def resolve_model_weights_path(model_id: str, env: dict[str, str] | None = None) -> Path | None:
    """GGUF path from {ID}_MODEL_PATH, TARGET_MODEL_PATH, or registry."""
    e = env if env is not None else os.environ
    model = model_id.strip()
    if not model:
        return None

    per_path = (e.get(_env_key(model, "MODEL_PATH")) or "").strip()
    if per_path:
        candidate = Path(per_path).expanduser()
        if not candidate.is_absolute():
            candidate = ROOT / candidate
        if candidate.is_file():
            return candidate

    configured = [m.strip() for m in (e.get("MODEL") or e.get("MODELS") or "").split(",") if m.strip()]
    if model in configured or not configured:
        target_path = (e.get("TARGET_MODEL_PATH") or "").strip()
        if target_path:
            candidate = Path(target_path).expanduser()
            if not candidate.is_absolute():
                candidate = ROOT / candidate
            if candidate.is_file():
                return candidate

    registry_path = model_weights_path(model)
    if registry_path and registry_path.is_file():
        return registry_path

    return None


def port_from_base_url(base_url: str) -> int:
    parsed = urlparse(base_url)
    if parsed.port:
        return parsed.port
    if parsed.scheme == "https":
        return 443
    return 80 if parsed.scheme == "http" else 8080


def can_auto_start_server(model_id: str, env: dict[str, str] | None = None) -> bool:
    e = env if env is not None else os.environ
    return resolve_model_weights_path(model_id, e) is not None and resolve_llama_server(e) is not None


def build_server_command(
    model_id: str,
    base_url: str,
    env: dict[str, str] | None = None,
) -> list[str] | None:
    e = env if env is not None else os.environ
    binary = resolve_llama_server(e)
    weights = resolve_model_weights_path(model_id, e)
    if not binary or not weights:
        return None

    port = port_from_base_url(base_url)
    threads = (e.get("LLAMA_THREADS") or str(os.cpu_count() or 4)).strip()
    cmd = [
        str(binary),
        "-m",
        str(weights),
        "-t",
        threads,
        "--port",
        str(port),
        "--host",
        "127.0.0.1",
        "--reasoning",
        "off",
    ]
    extra = (e.get(_env_key(model_id, "LLAMA_ARGS")) or e.get("LLAMA_ARGS") or "").strip()
    if extra:
        cmd.extend(shlex.split(extra))
    return cmd


def start_model_server(
    model_id: str,
    base_url: str,
    *,
    log_path: Path,
    env: dict[str, str] | None = None,
) -> subprocess.Popen[bytes]:
    cmd = build_server_command(model_id, base_url, env)
    if not cmd:
        raise RuntimeError(
            f"Cannot auto-start {model_id!r}: set {_env_key(model_id, 'MODEL_PATH')} "
            f"or download registry weights, and LLAMA_SERVER in .env"
        )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = log_path.open("ab")
    return subprocess.Popen(
        cmd,
        cwd=ROOT,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )


def find_legacy_start_script(model_id: str) -> Path | None:
    """Optional bash helpers under models/ — fallback only."""
    specific = ROOT / "models" / f"start-{model_id}-server.sh"
    if specific.is_file():
        return specific
    generic = ROOT / "models" / "start-server.sh"
    if model_id == "gemma" and generic.is_file():
        return generic
    return None
