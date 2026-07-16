"""Parse datasets/{id}/dataset.yaml into a typed manifest."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass(frozen=True)
class SourceSpec:
    type: str  # csv | jsonl | samples | legacy
    path: str = "raw/*"
    mapping: dict[str, str] = field(default_factory=dict)
    legacy: str = ""  # key for built-in preparer when type=legacy
    sampling: str = "sequential"  # sequential | stratified


@dataclass(frozen=True)
class EvalSpec:
    prompt: str = "qa"  # qa | faq | intent
    portfolio: bool = False


@dataclass(frozen=True)
class LimitsSpec:
    default: int = 50


@dataclass(frozen=True)
class DatasetManifest:
    id: str
    name: str
    task_type: str
    topic: str
    description: str
    hf_id: str
    task_prompt: str
    root: Path
    source: SourceSpec
    eval: EvalSpec
    limits: LimitsSpec

    @property
    def samples_path(self) -> Path:
        return self.root / "samples.jsonl"

    @property
    def uses_intent_prompt(self) -> bool:
        return self.eval.prompt == "intent" or self.task_type == "intent"


def load_manifest(path: Path) -> DatasetManifest:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    root = path.parent
    source_raw = data.get("source") or {}
    eval_raw = data.get("eval") or {}
    limits_raw = data.get("limits") or {}

    dataset_id = str(data.get("id") or root.name)
    return DatasetManifest(
        id=dataset_id,
        name=str(data.get("name") or dataset_id),
        task_type=str(data.get("task_type") or "extractive_qa"),
        topic=str(data.get("topic") or "Custom"),
        description=str(data.get("description") or ""),
        hf_id=str(data.get("hf_id") or "—"),
        task_prompt=str(data.get("task_prompt") or "Answer from provided context."),
        root=root,
        source=SourceSpec(
            type=str(source_raw.get("type") or "csv"),
            path=str(source_raw.get("path") or "raw/*"),
            mapping={str(k): str(v) for k, v in (source_raw.get("mapping") or {}).items()},
            legacy=str(source_raw.get("legacy") or source_raw.get("prepare") or ""),
            sampling=str(source_raw.get("sampling") or "sequential"),
        ),
        eval=EvalSpec(
            prompt=str(eval_raw.get("prompt") or "qa"),
            portfolio=bool(eval_raw.get("portfolio", False)),
        ),
        limits=LimitsSpec(default=int(limits_raw.get("default") or 50)),
    )
