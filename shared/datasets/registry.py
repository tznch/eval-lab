"""Auto-discover datasets from datasets/*/dataset.yaml."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from shared.datasets.manifest import DatasetManifest, load_manifest

ROOT = Path(__file__).resolve().parents[2]
DATASETS_ROOT = ROOT / "datasets"

# Legacy processed paths (pre-registry datasets)
LEGACY_SAMPLES: dict[str, Path] = {
    "feta": ROOT / "data/processed/uda-qa/feta/samples.jsonl",
    "nq": ROOT / "data/processed/uda-qa/nq/samples.jsonl",
    "paper_text": ROOT / "data/processed/uda-qa/paper_text/samples.jsonl",
    "paper_tab": ROOT / "data/processed/uda-qa/paper_tab/samples.jsonl",
    "fin": ROOT / "data/processed/uda-qa/fin/samples.jsonl",
    "sciq": ROOT / "data/processed/sciq/samples.jsonl",
    "financial_qa": ROOT / "data/processed/financial_qa/samples.jsonl",
    "ecommerce_faq": ROOT / "data/processed/ecommerce_faq/samples.jsonl",
    "bitext_intent": ROOT / "data/processed/bitext_intent/samples.jsonl",
}


def datasets_root() -> Path:
    return DATASETS_ROOT


@lru_cache(maxsize=1)
def discover_datasets() -> dict[str, DatasetManifest]:
    manifests: dict[str, DatasetManifest] = {}
    if not DATASETS_ROOT.exists():
        return manifests
    for entry in sorted(DATASETS_ROOT.iterdir()):
        if not entry.is_dir() or entry.name.startswith("_"):
            continue
        manifest_path = entry / "dataset.yaml"
        if manifest_path.exists():
            manifest = load_manifest(manifest_path)
            manifests[manifest.id] = manifest
    return manifests


def get_dataset(dataset_id: str) -> DatasetManifest | None:
    return discover_datasets().get(dataset_id)


def list_dataset_ids() -> list[str]:
    ids = set(discover_datasets())
    ids.update(LEGACY_SAMPLES)
    return sorted(ids)


def portfolio_dataset_ids() -> list[str]:
    from_registry = [m.id for m in discover_datasets().values() if m.eval.portfolio]
    legacy_portfolio = ["financial_qa", "ecommerce_faq", "bitext_intent"]
    merged: list[str] = []
    for ds_id in from_registry + legacy_portfolio:
        if ds_id not in merged:
            merged.append(ds_id)
    return merged or ["sciq"]


def samples_path(dataset_id: str) -> Path:
    manifest = get_dataset(dataset_id)
    if manifest:
        registry_path = manifest.samples_path
        if registry_path.exists():
            return registry_path
        legacy = LEGACY_SAMPLES.get(dataset_id)
        if legacy and legacy.exists():
            return legacy
        return registry_path
    if dataset_id in LEGACY_SAMPLES:
        return LEGACY_SAMPLES[dataset_id]
    return DATASETS_ROOT / dataset_id / "samples.jsonl"


def resolve_source_files(manifest: DatasetManifest) -> list[Path]:
    raw = manifest.source.path
    if raw.startswith("/"):
        p = Path(raw)
        return [p] if p.is_file() else sorted(p.parent.glob(p.name))
    base = manifest.root
    candidate = base / raw
    if candidate.is_file():
        return [candidate]
    if any(ch in raw for ch in "*?[]"):
        return sorted(base.glob(raw))
    # path relative to repo root (e.g. ../../file.csv)
    repo_candidate = (base / raw).resolve()
    if repo_candidate.is_file():
        return [repo_candidate]
    return sorted(base.glob(raw))
