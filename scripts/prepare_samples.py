#!/usr/bin/env python3
"""Convert UDA-QA / SciQ raw data to unified JSONL samples."""

import argparse
import json
from pathlib import Path

import pandas as pd

from shared.adapters.dataset_loader import save_samples
from shared.reporting.complexity import annotate_sample
from shared.schemas.eval_sample import EvalSample

RAW_DIR = Path("data/raw/uda-qa")
SCIQ_RAW = Path("data/raw/sciq")
REALWORLD_RAW = Path("data/raw")
EXTENDED_FILES = {
    "feta": RAW_DIR / "extended_qa_info" / "feta_qa.json",
    "nq": RAW_DIR / "extended_qa_info" / "nq_qa.json",
}


def _answer_from_row(row: pd.Series, config: str) -> str:
    if config == "nq":
        short = row.get("short_answer", "")
        long = row.get("long_answer", "")
        return str(short or long or "")
    if config in ("paper_text", "paper_tab", "fin"):
        parts = [str(row.get(f"answer_{i}", "") or "") for i in range(1, 4)]
        parts = [p for p in parts if p]
        return "; ".join(parts) if parts else ""
    return str(row.get("answer", "") or "")


def _format_evidence(evidence: object) -> str:
    if evidence is None:
        return ""
    if isinstance(evidence, str):
        return evidence.strip()
    if isinstance(evidence, dict):
        if "table_array" in evidence and evidence["table_array"]:
            rows = evidence["table_array"]
            return "\n".join(" | ".join(str(cell) for cell in row) for row in rows)
        if "text" in evidence:
            return str(evidence["text"]).strip()
        if "paragraphs" in evidence:
            return "\n\n".join(str(p) for p in evidence["paragraphs"])
        return json.dumps(evidence, ensure_ascii=False)
    if isinstance(evidence, list):
        return "\n".join(str(item) for item in evidence)
    return str(evidence)


def _load_extended_index(config: str) -> dict[str, dict]:
    path = EXTENDED_FILES.get(config)
    if not path or not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    index: dict[str, dict] = {}
    for items in data.values():
        if not isinstance(items, list):
            continue
        for item in items:
            q_uid = str(item.get("q_uid", ""))
            if q_uid:
                index[q_uid] = item
    return index


def _context_from_row(row: pd.Series, extended: dict[str, dict]) -> str:
    q_uid = str(row.get("q_uid", ""))
    extended_item = extended.get(q_uid)
    if extended_item:
        evidence_text = _format_evidence(extended_item.get("evidence"))
        doc_url = extended_item.get("doc_url") or row.get("doc_url")
        if evidence_text:
            header = f"Document: {doc_url}" if doc_url else "Document evidence:"
            return f"{header}\n\n{evidence_text}"
    doc_url = row.get("doc_url")
    if pd.notna(doc_url):
        return f"Source: {doc_url}"
    return ""


def _finalize(samples: list[EvalSample], config: str) -> Path:
    annotated = [annotate_sample(s) for s in samples]
    path = save_samples(annotated, config)
    tiers = {t: sum(1 for s in annotated if s.complexity == t) for t in ("easy", "medium", "hard")}
    print(f"Wrote {len(annotated)} samples to {path} · complexity {tiers}")
    return path


def prepare_uda(config: str, limit: int) -> Path:
    parquet_glob = list((RAW_DIR / config).glob("*.parquet"))
    if not parquet_glob:
        raise FileNotFoundError(
            f"No parquet in {RAW_DIR / config}. "
            f"Run: python scripts/download_uda_qa.py --config {config}"
        )
    extended = _load_extended_index(config)
    if not extended and config in EXTENDED_FILES:
        print(
            f"Warning: no extended_qa_info for {config}. "
            f"Run: python scripts/download_uda_qa.py --config {config} --extended"
        )

    df = pd.read_parquet(parquet_glob[0])
    samples: list[EvalSample] = []
    for idx, row in df.head(limit).iterrows():
        q_uid = str(row.get("q_uid", idx))
        doc_name = str(row.get("doc_name", ""))
        samples.append(
            EvalSample(
                id=f"{config}_{q_uid[:12]}",
                question=str(row["question"]),
                ground_truth=_answer_from_row(row, config),
                context=_context_from_row(row, extended),
                doc_name=doc_name,
                source=f"uda-qa/{config}",
                task_type="extractive_qa",
            )
        )
    return _finalize(samples, config)


def prepare_sciq(limit: int, split: str = "validation") -> Path:
    raw = SCIQ_RAW / f"{split}.jsonl"
    if not raw.exists():
        raise FileNotFoundError(
            f"No SciQ raw at {raw}. Run: python scripts/download_sciq.py --split {split}"
        )
    samples: list[EvalSample] = []
    with raw.open(encoding="utf-8") as f:
        for i, line in enumerate(f):
            if len(samples) >= limit:
                break
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            support = str(row.get("support") or "").strip()
            answer = str(row.get("correct_answer") or "").strip()
            question = str(row.get("question") or "").strip()
            if not question or not answer or len(support) < 40:
                continue  # skip empty-support rows (weak for RAGAS)
            samples.append(
                EvalSample(
                    id=f"sciq_{i}",
                    question=question,
                    ground_truth=answer,
                    context=support,
                    doc_name="sciq-support",
                    source="hf/sciq",
                    category="science",
                    task_type="extractive_qa",
                )
            )
    return _finalize(samples, "sciq")


def prepare_financial_qa(limit: int) -> Path:
    raw = REALWORLD_RAW / "financial_qa" / "train.jsonl"
    if not raw.exists():
        raise FileNotFoundError(f"Missing {raw}. Run: python scripts/download_realworld.py financial_qa")
    samples: list[EvalSample] = []
    with raw.open(encoding="utf-8") as f:
        for i, line in enumerate(f):
            if len(samples) >= limit:
                break
            row = json.loads(line)
            ctx = str(row.get("context") or "").strip()
            ans = str(row.get("answer") or "").strip()
            q = str(row.get("question") or "").strip()
            if not q or not ans or len(ctx) < 50:
                continue
            samples.append(
                EvalSample(
                    id=f"finqa_{i}",
                    question=q,
                    ground_truth=ans,
                    context=ctx,
                    doc_name=str(row.get("ticker") or row.get("filing") or ""),
                    source="hf/financial-qa-10k",
                    category=str(row.get("ticker") or "finance"),
                    task_type="extractive_qa",
                    metadata={"filing": row.get("filing"), "ticker": row.get("ticker")},
                )
            )
    return _finalize(samples, "financial_qa")


def prepare_ecommerce_faq(limit: int) -> Path:
    raw = REALWORLD_RAW / "ecommerce_faq" / "train.jsonl"
    if not raw.exists():
        raise FileNotFoundError(f"Missing {raw}. Run: python scripts/download_realworld.py ecommerce_faq")
    samples: list[EvalSample] = []
    with raw.open(encoding="utf-8") as f:
        for i, line in enumerate(f):
            if len(samples) >= limit:
                break
            row = json.loads(line)
            q = str(row.get("question") or "").strip()
            ans = str(row.get("answer") or "").strip()
            cat = str(row.get("category") or "General").strip()
            if not q or not ans:
                continue
            context = f"E-commerce FAQ — Category: {cat}\n\nPolicy:\n{ans}"
            samples.append(
                EvalSample(
                    id=f"faq_{i}",
                    question=q,
                    ground_truth=ans,
                    context=context,
                    doc_name=cat,
                    source="hf/ecommerce-faq",
                    category=cat,
                    task_type="faq",
                )
            )
    return _finalize(samples, "ecommerce_faq")


def prepare_bitext_intent(limit: int) -> Path:
    from shared.datasets.prepare import stratified_sample_rows

    raw = REALWORLD_RAW / "bitext_intent" / "train.jsonl"
    if not raw.exists():
        raise FileNotFoundError(f"Missing {raw}. Run: python scripts/download_realworld.py bitext_intent")
    rows: list[dict] = []
    with raw.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    picked = stratified_sample_rows(rows, limit, "intent", question_key="instruction")
    samples: list[EvalSample] = []
    for i, row in enumerate(picked):
        instruction = str(row.get("instruction") or "").strip()
        intent = str(row.get("intent") or "").strip()
        category = str(row.get("category") or "").strip()
        if not instruction or not intent:
            continue
        samples.append(
            EvalSample(
                id=f"bitext_{i}",
                question=instruction,
                ground_truth=intent,
                context=f"Support category: {category}" if category else "",
                doc_name=category,
                source="hf/bitext-support",
                category=category or "SUPPORT",
                task_type="intent",
                metadata={"intent": intent, "flags": row.get("flags")},
            )
        )
    return _finalize(samples, "bitext_intent")


def prepare(config: str, limit: int) -> Path:
    from shared.datasets.registry import get_dataset
    from shared.datasets.prepare import prepare_dataset

    manifest = get_dataset(config)
    if manifest is not None and manifest.source.type != "legacy":
        return prepare_dataset(config, limit)
    return prepare_legacy(config, limit)


def prepare_legacy(config: str, limit: int) -> Path:
    if config == "sciq":
        return prepare_sciq(limit)
    if config == "financial_qa":
        return prepare_financial_qa(limit)
    if config == "ecommerce_faq":
        return prepare_ecommerce_faq(limit)
    if config == "bitext_intent":
        return prepare_bitext_intent(limit)
    return prepare_uda(config, limit)


def main() -> None:
    from shared.datasets.registry import list_dataset_ids

    parser = argparse.ArgumentParser(description="Prepare JSONL eval samples")
    parser.add_argument("--config", default="feta", help="Dataset id (see: make datasets-list)")
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()
    prepare(args.config, args.limit)


if __name__ == "__main__":
    main()
