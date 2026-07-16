"""Generic prepare: raw CSV/JSONL → datasets/{id}/samples.jsonl."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from shared.datasets.manifest import DatasetManifest
from shared.datasets.registry import discover_datasets, get_dataset, resolve_source_files
from shared.reporting.complexity import annotate_sample
from shared.schemas.eval_sample import EvalSample

ROOT = Path(__file__).resolve().parents[2]


def _run_legacy_prepare(config: str, limit: int) -> Path:
    import importlib.util

    path = ROOT / "scripts" / "prepare_samples.py"
    spec = importlib.util.spec_from_file_location("prepare_samples", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.prepare_legacy(config, limit)


def _field(row: dict, mapping: dict[str, str], target: str, default: str = "") -> str:
    col = mapping.get(target, target)
    val = row.get(col, default)
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return default
    return str(val).strip()


def _rows_from_csv(path: Path) -> list[dict]:
    df = pd.read_csv(path)
    return df.to_dict(orient="records")


def _rows_from_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def stratified_sample_rows(
    rows: list[dict],
    limit: int,
    ground_truth_key: str,
    *,
    question_key: str | None = None,
) -> list[dict]:
    """Round-robin pick across ground-truth buckets for diverse intent coverage."""
    from collections import defaultdict

    buckets: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        gt = str(row.get(ground_truth_key) or "").strip()
        if not gt:
            continue
        if question_key:
            q = str(row.get(question_key) or "").strip()
            if not q:
                continue
        buckets[gt].append(row)

    if not buckets:
        return []

    intents = sorted(buckets)
    picked: list[dict] = []
    idx = 0
    guard = 0
    while len(picked) < limit and intents and guard < limit * max(len(buckets), 1) * 3:
        guard += 1
        intent = intents[idx % len(intents)]
        bucket = buckets[intent]
        if bucket:
            picked.append(bucket.pop(0))
        idx += 1
        intents = [i for i in intents if buckets[i]]
    return picked


def _build_samples(manifest: DatasetManifest, rows: list[dict], limit: int) -> list[EvalSample]:
    mapping = manifest.source.mapping
    samples: list[EvalSample] = []
    for i, row in enumerate(rows):
        if len(samples) >= limit:
            break
        question = _field(row, mapping, "question")
        ground_truth = _field(row, mapping, "ground_truth")
        if not question or not ground_truth:
            continue
        sample_id = _field(row, mapping, "id") or f"{manifest.id}_{i}"
        context = _field(row, mapping, "context")
        category = _field(row, mapping, "category")
        doc_name = _field(row, mapping, "doc_name") or category
        source = _field(row, mapping, "source") or f"datasets/{manifest.id}"
        samples.append(
            EvalSample(
                id=sample_id,
                question=question,
                ground_truth=ground_truth,
                context=context,
                doc_name=doc_name,
                source=source,
                category=category,
                task_type=manifest.task_type,
            )
        )
    return [annotate_sample(s) for s in samples]


def _write_samples(manifest: DatasetManifest, samples: list[EvalSample]) -> Path:
    out = manifest.samples_path
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for s in samples:
            f.write(s.model_dump_json() + "\n")
    return out


def _prepare_legacy(manifest: DatasetManifest, limit: int) -> Path:
    from scripts import prepare_samples as legacy_prepare

    key = manifest.source.legacy or manifest.id
    return legacy_prepare.prepare(key, limit)


def prepare_dataset(dataset_id: str, limit: int | None = None) -> Path:
    manifest = get_dataset(dataset_id)
    if manifest is None:
        raise ValueError(
            f"Unknown dataset {dataset_id!r}. "
            f"Known: {', '.join(discover_datasets()) or '(none — add datasets/{id}/dataset.yaml)'}"
        )

    n = limit if limit is not None else manifest.limits.default
    stype = manifest.source.type

    if stype == "legacy":
        key = manifest.source.legacy or dataset_id
        return _run_legacy_prepare(key, n)

    if stype == "samples":
        files = resolve_source_files(manifest)
        if not files:
            raise FileNotFoundError(f"No samples file for {dataset_id} at {manifest.source.path}")
        rows = _rows_from_jsonl(files[0])
        samples = []
        for i, row in enumerate(rows[:n]):
            samples.append(EvalSample.model_validate(row))
        samples = [annotate_sample(s) for s in samples]
        return _write_samples(manifest, samples)

    files = resolve_source_files(manifest)
    if not files:
        raise FileNotFoundError(
            f"No source files for {dataset_id}. "
            f"Expected {manifest.source.path} under {manifest.root}"
        )

    rows: list[dict] = []
    for fp in files:
        if stype == "csv" or fp.suffix.lower() == ".csv":
            rows.extend(_rows_from_csv(fp))
        else:
            rows.extend(_rows_from_jsonl(fp))

    if manifest.source.sampling == "stratified":
        mapping = manifest.source.mapping
        gt_col = mapping.get("ground_truth", "ground_truth")
        q_col = mapping.get("question", "question")
        rows = stratified_sample_rows(rows, n, gt_col, question_key=q_col)
        samples = _build_samples(manifest, rows, len(rows))
    else:
        samples = _build_samples(manifest, rows, n)
    if not samples:
        raise ValueError(f"No valid samples produced for {dataset_id} (check mapping in dataset.yaml)")

    path = _write_samples(manifest, samples)
    tiers = {t: sum(1 for s in samples if s.complexity == t) for t in ("easy", "medium", "hard")}
    print(f"Wrote {len(samples)} samples to {path} · complexity {tiers}")
    return path
