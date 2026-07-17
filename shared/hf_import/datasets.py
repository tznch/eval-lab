"""Import HuggingFace datasets into the local dataset registry."""

from __future__ import annotations

import json
from itertools import islice
from pathlib import Path

import yaml
from datasets import load_dataset

from shared.datasets.prepare import prepare_dataset
from shared.datasets.registry import discover_datasets
from shared.hf_auth import get_hf_token
from shared.hf_import.ids import default_dataset_id_from_hf, sanitize_local_id

ROOT = Path(__file__).resolve().parents[2]
DATASETS_ROOT = ROOT / "datasets"


def load_hf_rows(*, hf_id: str, split: str, limit: int) -> list[dict]:
    """Load at most ``limit`` rows from a HuggingFace dataset split."""
    dataset = load_dataset(
        hf_id,
        split=split,
        token=get_hf_token(),
        streaming=True,
    )
    return [dict(row) for row in islice(dataset, limit)]


def clear_dataset_cache() -> None:
    """Clear the registry after adding a dataset manifest."""
    discover_datasets.cache_clear()


def import_hf_dataset(
    *,
    hf_id: str,
    split: str,
    local_id: str | None,
    mapping: dict[str, str],
    limit: int = 200,
) -> dict:
    """Import an HF split, write its manifest, and prepare evaluation samples."""
    dataset_id = sanitize_local_id(
        local_id if local_id is not None else default_dataset_id_from_hf(hf_id)
    )
    rows = load_hf_rows(hf_id=hf_id, split=split, limit=limit)
    if not rows:
        raise ValueError(f"HuggingFace dataset {hf_id!r} split {split!r} returned no rows")

    required = ("question", "ground_truth")
    missing_mapping = [key for key in required if not mapping.get(key)]
    if missing_mapping:
        raise ValueError(f"Missing required mapping keys: {', '.join(missing_mapping)}")

    selected_mapping = {
        key: value
        for key in ("question", "ground_truth", "context")
        if (value := mapping.get(key))
    }
    available = set(rows[0])
    missing_columns = sorted(set(selected_mapping.values()) - available)
    if missing_columns:
        raise ValueError(
            f"Mapped columns not found: {', '.join(missing_columns)}. "
            f"Available columns: {', '.join(sorted(available))}"
        )

    dataset_root = DATASETS_ROOT / dataset_id
    raw_path = dataset_root / "raw" / "rows.jsonl"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    with raw_path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")

    manifest = {
        "id": dataset_id,
        "name": dataset_id,
        "task_type": "extractive_qa",
        "topic": "HuggingFace import",
        "description": f"Imported from {hf_id} ({split})",
        "hf_id": hf_id,
        "task_prompt": "Answer from provided context.",
        "source": {
            "type": "jsonl",
            "path": "raw/rows.jsonl",
            "mapping": selected_mapping,
        },
        "eval": {"prompt": "qa", "portfolio": False},
        "limits": {"default": limit},
    }
    (dataset_root / "dataset.yaml").write_text(
        yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    samples_path = prepare_dataset(dataset_id, limit=limit)
    clear_dataset_cache()
    return {
        "dataset_id": dataset_id,
        "samples_path": str(samples_path),
        "rows": len(rows),
    }
