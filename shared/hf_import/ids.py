"""Sanitize local model/dataset ids from HuggingFace repo paths."""

from __future__ import annotations

import re


def sanitize_local_id(raw: str, *, fallback: str = "import") -> str:
    s = raw.lower()
    s = re.sub(r"[^a-z0-9_-]", "-", s)
    s = s.strip("-_")
    s = s.lstrip("_")
    if not s:
        return fallback
    if s == "_template":
        return "template"
    return s


def default_model_id_from_repo(repo_id: str) -> str:
    name = repo_id.rsplit("/", 1)[-1]
    return sanitize_local_id(name)


def default_dataset_id_from_hf(hf_id: str) -> str:
    name = hf_id.rsplit("/", 1)[-1]
    return sanitize_local_id(name)
