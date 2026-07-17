"""List and download GGUF models from HuggingFace."""

from __future__ import annotations

import os
import re
from pathlib import Path

from huggingface_hub import hf_hub_download, list_repo_files

from shared.env_files import upsert_env_file
from shared.hf_auth import get_hf_token
from shared.hf_import.ids import default_model_id_from_repo, sanitize_local_id
from shared.hf_import.ports import find_free_port

ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = ROOT / ".env"


def list_gguf_files(repo_id: str) -> list[str]:
    """Return the repository's GGUF filenames in sorted order."""
    files = list_repo_files(repo_id, token=get_hf_token())
    return sorted(name for name in files if name.lower().endswith(".gguf"))


def download_gguf(
    *,
    repo_id: str,
    filename: str,
    model_id: str | None = None,
) -> dict:
    """Download a GGUF file and configure its local OpenAI-compatible server."""
    resolved_id = sanitize_local_id(
        model_id if model_id is not None else default_model_id_from_repo(repo_id)
    )
    local_dir = ROOT / "data" / "models" / resolved_id
    local_dir.mkdir(parents=True, exist_ok=True)
    path = hf_hub_download(
        repo_id=repo_id,
        filename=filename,
        local_dir=local_dir,
        token=get_hf_token(),
    )

    port = find_free_port()
    base_url = f"http://127.0.0.1:{port}/v1"
    model_name = Path(filename).stem
    env_prefix = re.sub(r"[^A-Za-z0-9]", "_", resolved_id).upper()
    updates = {
        f"{env_prefix}_BASE_URL": base_url,
        f"{env_prefix}_MODEL_PATH": str(path),
        f"{env_prefix}_MODEL_NAME": model_name,
    }
    upsert_env_file(ENV_PATH, updates)
    os.environ.update(updates)

    return {
        "model_id": resolved_id,
        "path": str(path),
        "base_url": base_url,
        "model_name": model_name,
        "port": port,
    }
