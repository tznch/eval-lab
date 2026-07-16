"""Parse eval outputs and stratify pass/fail by complexity and data dimensions."""

from __future__ import annotations

import csv
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from shared.adapters.dataset_loader import load_samples_from_jsonl
from shared.datasets.registry import portfolio_dataset_ids, samples_path
from shared.reporting.complexity import add_outcome, empty_stratum, finalize_strata
from shared.reporting.score_format import round_score
from shared.schemas.eval_sample import EvalSample

from shared.reporting.result_paths import RESULTS, deepeval_junit, promptfoo_output, ragas_scores

# Thresholds (best practice: report RAG failures on faithfulness separately)
RAGAS_FAITHFULNESS_PASS = 0.5
RAGAS_RELEVANCY_PASS = 0.5
DEEPEVAL_PASS = 0.3


def _sample_index(dataset: str) -> dict[str, EvalSample]:
    path = samples_path(dataset)
    if not path.exists():
        return {}
    samples = load_samples_from_jsonl(path)
    return {s.id: s for s in samples}


def _failure_mode(framework: str, *, faithfulness: float | None = None) -> str:
    if framework == "ragas" and faithfulness is not None and faithfulness < RAGAS_FAITHFULNESS_PASS:
        return "grounding"  # answer not faithful to context
    if framework == "promptfoo":
        return "format_or_content"  # assert / keyword mismatch
    if framework == "deepeval":
        return "judge_quality"  # LLM judge rejected answer
    return "other"


def _record_outcome(
    table: dict[str, dict],
    sample: EvalSample | None,
    passed: bool,
) -> None:
    if sample is None:
        key = "unknown"
        for dim_name in ("complexity", "context_bucket", "category"):
            dim = table.setdefault(dim_name, {})
            add_outcome(dim.setdefault(key, empty_stratum().copy()), passed)
        return

    for dim_name, key in (
        ("complexity", sample.complexity or "unknown"),
        ("context_bucket", sample.context_bucket or "unknown"),
        ("category", sample.category or "uncategorized"),
    ):
        dim = table.setdefault(dim_name, {})
        add_outcome(dim.setdefault(key, empty_stratum().copy()), passed)


def parse_promptfoo(path: Path, index: dict[str, EvalSample]) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    outcomes = []
    for row in data.get("results", {}).get("results", []):
        tc = row.get("testCase") or {}
        sid = tc.get("description") or tc.get("vars", {}).get("sample_id", "")
        passed = bool((row.get("gradingResult") or {}).get("pass"))
        sample = index.get(sid)
        outcomes.append(
            {
                "sample_id": sid,
                "framework": "promptfoo",
                "passed": passed,
                "complexity": sample.complexity if sample else None,
                "context_bucket": sample.context_bucket if sample else None,
                "category": sample.category if sample else None,
                "failure_mode": None if passed else _failure_mode("promptfoo"),
            }
        )
    return outcomes


def parse_deepeval(path: Path, index: dict[str, EvalSample]) -> list[dict]:
    outcomes = []
    tree = ET.parse(path)
    for case in tree.getroot().iter("testcase"):
        name = case.get("name", "")
        m = re.search(r"\[(.+?)\]$", name)
        sid = m.group(1) if m else name
        passed = case.find("failure") is None and case.find("error") is None
        sample = index.get(sid)
        outcomes.append(
            {
                "sample_id": sid,
                "framework": "deepeval",
                "passed": passed,
                "complexity": sample.complexity if sample else None,
                "context_bucket": sample.context_bucket if sample else None,
                "category": sample.category if sample else None,
                "failure_mode": None if passed else _failure_mode("deepeval"),
            }
        )
    return outcomes


def parse_ragas(path: Path, index: dict[str, EvalSample], dataset: str) -> list[dict]:
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    outcomes = []
    # Prefer sample_id column; fallback to row order + samples file
    ordered_ids = list(index.keys())
    for i, row in enumerate(rows):
        sid = row.get("sample_id") or (ordered_ids[i] if i < len(ordered_ids) else f"row_{i}")
        sample = index.get(sid)
        try:
            faith = round_score(float(row.get("faithfulness", 0))) or 0.0
            rel = round_score(float(row.get("answer_relevancy", 0))) or 0.0
        except (TypeError, ValueError):
            faith, rel = 0.0, 0.0
        passed = faith >= RAGAS_FAITHFULNESS_PASS and rel >= RAGAS_RELEVANCY_PASS
        outcomes.append(
            {
                "sample_id": sid,
                "framework": "ragas",
                "passed": passed,
                "faithfulness": faith,
                "answer_relevancy": rel,
                "complexity": sample.complexity if sample else None,
                "context_bucket": sample.context_bucket if sample else None,
                "category": sample.category if sample else None,
                "failure_mode": None
                if passed
                else _failure_mode("ragas", faithfulness=faith),
            }
        )
    return outcomes


def build_stratified_report(
    dataset: str,
    model: str,
) -> dict:
    index = _sample_index(dataset)
    tables: dict[str, dict] = {
        "by_framework": {},
        "complexity": {},
        "context_bucket": {},
        "category": {},
        "failure_modes": {},
    }
    per_sample: dict[str, dict] = {}

    def merge_outcomes(outcomes: list[dict]) -> None:
        for o in outcomes:
            fw = o["framework"]
            fw_table = tables["by_framework"].setdefault(fw, empty_stratum().copy())
            add_outcome(fw_table, o["passed"])
            sample = index.get(o["sample_id"])
            _record_outcome(tables, sample, o["passed"])
            if not o["passed"]:
                mode = o.get("failure_mode") or "other"
                fm = tables["failure_modes"]
                add_outcome(fm.setdefault(mode, empty_stratum().copy()), False)
            entry = per_sample.setdefault(
                o["sample_id"],
                {"sample_id": o["sample_id"], "frameworks": {}},
            )
            if sample:
                entry.update(
                    {
                        "complexity": sample.complexity,
                        "context_bucket": sample.context_bucket,
                        "category": sample.category,
                        "task_type": sample.task_type,
                    }
                )
            entry["frameworks"][fw] = {
                "passed": o["passed"],
                "failure_mode": o.get("failure_mode"),
            }

    pf = promptfoo_output(model, dataset)
    if pf.exists():
        merge_outcomes(parse_promptfoo(pf, index))

    de = deepeval_junit(model, dataset)
    if de.exists():
        merge_outcomes(parse_deepeval(de, index))

    rg = ragas_scores(model, dataset)
    if rg.exists():
        merge_outcomes(parse_ragas(rg, index, dataset))

    return {
        "dataset": dataset,
        "model": model,
        "sample_count": len(index),
        "by_framework": finalize_strata(tables["by_framework"]),
        "by_complexity": finalize_strata(tables["complexity"]),
        "by_context_bucket": finalize_strata(tables["context_bucket"]),
        "by_category": finalize_strata(tables["category"]),
        "failure_modes": finalize_strata(tables.get("failure_modes", {})),
        "failed_samples": [
            v
            for v in per_sample.values()
            if any(not fw.get("passed", True) for fw in v.get("frameworks", {}).values())
        ],
    }


def _discover_models() -> list[str]:
    models: set[str] = set()
    pf_dir = RESULTS / "promptfoo"
    if pf_dir.exists():
        for p in pf_dir.rglob("output.json"):
            rel = p.relative_to(pf_dir)
            if len(rel.parts) >= 2 and rel.parts[0] != "ifeval":
                models.add(rel.parts[0])
    de_dir = RESULTS / "deepeval"
    if de_dir.exists():
        for p in de_dir.rglob("junit.xml"):
            rel = p.relative_to(de_dir)
            if rel.parts:
                models.add(rel.parts[0])
    rg_dir = RESULTS / "ragas"
    if rg_dir.exists():
        for p in rg_dir.iterdir():
            if p.is_dir():
                models.add(p.name)
    return sorted(models)


def build_portfolio_failure_report(models: list[str] | None = None) -> dict:
    datasets = portfolio_dataset_ids()
    if models is None:
        models = _discover_models()
    tracks = []
    for ds in datasets:
        for model in models:
            rep = build_stratified_report(ds, model)
            if rep["by_framework"]:
                tracks.append(rep)
    return {
        "models": models,
        "datasets": datasets,
        "tracks": tracks,
        "methodology": {
            "complexity_tiers": "easy / medium / hard from context length, answer length, question heuristics",
            "context_buckets": "short <300 chars, medium 300–799, long ≥800",
            "failure_modes": {
                "grounding": "RAGAS faithfulness below threshold — answer not supported by context",
                "judge_quality": "DeepEval judge score below threshold",
                "format_or_content": "Promptfoo assert failed — keyword/format mismatch",
            },
            "ragas_pass_rule": f"faithfulness≥{RAGAS_FAITHFULNESS_PASS} and answer_relevancy≥{RAGAS_RELEVANCY_PASS}",
        },
    }


def export_failure_analysis(out_dir: Path | None = None) -> Path:
    out = out_dir or (RESULTS / "analysis")
    out.mkdir(parents=True, exist_ok=True)
    report = build_portfolio_failure_report()
    path = out / "failure_stratification.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
