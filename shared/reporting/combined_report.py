"""Aggregate Promptfoo, DeepEval, RAGAS, and IFEval results into one report."""

from __future__ import annotations

import csv
import json
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from shared.reporting.eval_agenda import (
    FRAMEWORK_METRICS,
    TASK_AGENDA,
    get_dataset_info,
    portfolio_datasets,
)
from shared.reporting.score_format import format_rate_pct, format_score, round_score

from shared.reporting.performance_report import build_performance_report
from shared.reporting.run_paths import (
    LEGACY_TEMP_TAG,
    model_label,
    parse_deepeval_path,
    parse_promptfoo_path,
    parse_ragas_path,
)


def _find_promptfoo_outputs() -> list[Path]:
    d = RESULTS / "promptfoo"
    if not d.exists():
        return []
    files = sorted(d.rglob("output.json")) + sorted(d.rglob("compare.json"))
    ifeval = sorted((d / "ifeval").glob("*.json")) if (d / "ifeval").exists() else []
    return files + ifeval


def _resolve_result_path(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "results"
MISSING = "—"


def _model_from_promptfoo_path(path: Path) -> str:
    return parse_promptfoo_path(_resolve_result_path(path))[0]


def _meta_from_promptfoo_path(path: Path) -> tuple[str, str | None, str | None]:
    return parse_promptfoo_path(_resolve_result_path(path))


def _dataset_from_result_path(path: Path, framework: str) -> str | None:
    full = _resolve_result_path(path)
    if framework == "promptfoo":
        return parse_promptfoo_path(full)[2]
    if framework == "deepeval":
        return parse_deepeval_path(full)[2]
    return None


def _summarize_promptfoo(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    results = data.get("results", {})
    providers = []
    for p in results.get("prompts", []):
        m = p.get("metrics", {})
        total = (
            m.get("testPassCount", 0)
            + m.get("testFailCount", 0)
            + m.get("testErrorCount", 0)
        )
        passed = m.get("testPassCount", 0)
        providers.append(
            {
                "provider": p.get("provider") or p.get("label", "?"),
                "pass": passed,
                "fail": m.get("testFailCount", 0),
                "error": m.get("testErrorCount", 0),
                "total": total,
                "pass_rate": round_score(passed / total) if total else None,
                "score": round_score(m.get("score")) if m.get("score") is not None else None,
            }
        )
    return {
        "path": str(path.relative_to(ROOT)),
        "eval_id": data.get("evalId"),
        "timestamp": results.get("timestamp"),
        "providers": providers,
        "track": "ifeval" if path.parent.name == "ifeval" else "qa",
        "model": _meta_from_promptfoo_path(path)[0],
        "temp_tag": _meta_from_promptfoo_path(path)[1] or LEGACY_TEMP_TAG,
        "dataset": _meta_from_promptfoo_path(path)[2],
    }


def _summarize_deepeval(path: Path) -> dict:
    full = _resolve_result_path(path)
    model, temp_tag, dataset = parse_deepeval_path(full)
    tree = ET.parse(full)
    for suite in tree.getroot().iter("testsuite"):
        tests = int(suite.get("tests", 0))
        failures = int(suite.get("failures", 0))
        errors = int(suite.get("errors", 0))
        passed = tests - failures - errors
        return {
            "path": str(full.relative_to(ROOT)),
            "model": model,
            "temp_tag": temp_tag or LEGACY_TEMP_TAG,
            "dataset": dataset,
            "tests": tests,
            "passed": passed,
            "failures": failures,
            "errors": errors,
            "pass_rate": round_score(passed / tests) if tests else None,
            "time_s": float(suite.get("time", 0) or 0),
        }
    return {
        "path": str(path.relative_to(ROOT)),
        "model": model,
        "temp_tag": temp_tag or LEGACY_TEMP_TAG,
        "dataset": dataset,
        "tests": 0,
        "passed": 0,
    }


def _format_promptfoo_cell(data: dict | None) -> str:
    if not data:
        return MISSING
    total = data.get("total") or 0
    if not total:
        return MISSING
    passed = data.get("pass", 0)
    err = data.get("error", 0)
    rate = format_rate_pct(data.get("pass_rate"))
    text = f"{passed}/{total} ({rate})"
    if err:
        text += f", {err} err"
    return text


def _format_deepeval_cell(data: dict | None) -> str:
    if not data or not data.get("tests"):
        return MISSING
    passed = data.get("passed", 0)
    total = data["tests"]
    rate = format_rate_pct(data.get("pass_rate"))
    return f"{passed}/{total} ({rate})"


def _format_ragas_cell(data: dict | None) -> str:
    if not data:
        return MISSING
    avgs = data.get("averages") or {}
    if not avgs:
        return MISSING
    parts = []
    if "faithfulness" in avgs:
        parts.append(f"F={format_score(avgs['faithfulness'])}")
    if "answer_relevancy" in avgs:
        parts.append(f"R={format_score(avgs['answer_relevancy'])}")
    return " · ".join(parts) if parts else MISSING


def _report_scope(comparison: dict, default_dataset_id: str) -> dict:
    tracks = [t["dataset"] for t in comparison.get("tracks") or []]
    if len(tracks) > 1:
        return {"mode": "portfolio", "tracks": tracks, "track_count": len(tracks)}
    if tracks:
        return {"mode": "single", "tracks": tracks}
    return {"mode": "single", "tracks": [default_dataset_id]}


def build_comparison(report: dict) -> dict:
    """Side-by-side matrix: portfolio tracks × model runs (model + temperature)."""
    pf_index: dict[tuple[str, str, str], dict] = {}
    de_index: dict[tuple[str, str, str], dict] = {}
    rg_index: dict[tuple[str, str, str], dict] = {}
    run_labels: dict[tuple[str, str], str] = {}

    def run_key(model: str, temp: str | None) -> tuple[str, str]:
        tag = temp or LEGACY_TEMP_TAG
        run_labels.setdefault((model, tag), model_label(model, tag.removeprefix("t")))
        return model, tag

    for run in report["runs"]["promptfoo"]:
        path = Path(run["path"])
        model, temp, dataset = parse_promptfoo_path(_resolve_result_path(path))
        if model == "compare" or not dataset or not run.get("providers"):
            continue
        pf_index[run_key(model, temp) + (dataset,)] = run["providers"][0]

    for run in report["runs"]["deepeval"]:
        model, temp, dataset = run.get("model"), run.get("temp_tag"), run.get("dataset")
        if model and dataset:
            de_index[run_key(model, temp) + (dataset,)] = run

    for run in report["runs"]["ragas"]:
        model, temp, dataset = run.get("model"), run.get("temp_tag"), run.get("config")
        if model and dataset:
            rg_index[run_key(model, temp) + (dataset,)] = run

    runs = sorted(run_labels.keys(), key=lambda x: (x[0], x[1]))
    run_columns = [run_labels[r] for r in runs]
    datasets_found = {d for *_, d in pf_index} | {d for *_, d in de_index} | {d for *_, d in rg_index}
    portfolio = portfolio_datasets()
    track_order = [d for d in portfolio if d in datasets_found]
    track_order += sorted(datasets_found - set(track_order))

    tracks = []
    for dataset in track_order:
        models_data: dict[str, dict] = {}
        for run_id, label in zip(runs, run_columns):
            models_data[label] = {
                "promptfoo": pf_index.get(run_id + (dataset,)),
                "deepeval": de_index.get(run_id + (dataset,)),
                "ragas": rg_index.get(run_id + (dataset,)),
                "model": run_id[0],
                "temp_tag": run_id[1],
            }
        tracks.append({"dataset": dataset, "models": models_data})

    return {"models": run_columns, "runs": [{"model": m, "temp_tag": t} for m, t in runs], "tracks": tracks}


def _comparison_markdown_table(
    tracks: list[dict],
    models: list[str],
    metric: str,
    formatter,
    title: str,
) -> list[str]:
    if not tracks or not models:
        return []

    lines = [f"### {title}", "", "| Track | " + " | ".join(models) + " |", "|-------|" + "|".join(["--------"] * len(models)) + "|"]
    for track in tracks:
        cells = [track["dataset"]]
        for model in models:
            cells.append(formatter(track["models"].get(model, {}).get(metric)))
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")
    return lines


def _summarize_ragas(path: Path) -> dict:
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    model, temp_tag, config = parse_ragas_path(_resolve_result_path(path))
    avgs: dict[str, float] = {}
    for key in ("faithfulness", "answer_relevancy"):
        vals = []
        for row in rows:
            try:
                vals.append(float(row[key]))
            except (KeyError, ValueError):
                pass
        if vals:
            avgs[key] = round_score(sum(vals) / len(vals))
    return {
        "path": str(path.relative_to(ROOT)),
        "model": model,
        "temp_tag": temp_tag or LEGACY_TEMP_TAG,
        "config": config,
        "samples": len(rows),
        "averages": avgs,
    }


def build_combined_report(dataset: str | None = None) -> dict:
    dataset_id = dataset or os.getenv("EVAL_DATASET", "sciq")
    ds = get_dataset_info(dataset_id)

    promptfoo_runs = []
    for f in _find_promptfoo_outputs():
        try:
            promptfoo_runs.append(_summarize_promptfoo(f))
        except (json.JSONDecodeError, OSError):
            continue

    deepeval_runs = []
    de_dir = RESULTS / "deepeval"
    if de_dir.exists():
        for f in sorted(de_dir.rglob("junit.xml")):
            try:
                deepeval_runs.append(_summarize_deepeval(f))
            except ET.ParseError:
                continue

    ragas_runs = []
    rg_dir = RESULTS / "ragas"
    if rg_dir.exists():
        for f in sorted(rg_dir.rglob("*_scores.csv")):
            try:
                ragas_runs.append(_summarize_ragas(f))
            except OSError:
                continue

    # Per-model rollup
    models: dict[str, dict] = {}

    def ensure_model(name: str) -> dict:
        if name not in models:
            models[name] = {
                "promptfoo_qa": None,
                "promptfoo_ifeval": None,
                "promptfoo_by_dataset": {},
                "deepeval": None,
                "deepeval_by_dataset": {},
                "ragas": [],
            }
        return models[name]

    for run in promptfoo_runs:
        path = Path(run["path"])
        model = _model_from_promptfoo_path(path)
        if model == "compare":
            ensure_model("compare")["promptfoo_qa"] = run
            continue
        key = "promptfoo_ifeval" if run["track"] == "ifeval" else "promptfoo_qa"
        bucket = ensure_model(model)
        if key == "promptfoo_qa":
            bucket.setdefault("promptfoo_by_dataset", {})[
                _dataset_from_result_path(path, "promptfoo") or "unknown"
            ] = run
        bucket[key] = run

    for run in deepeval_runs:
        bucket = ensure_model(run["model"])
        bucket["deepeval"] = run
        if run.get("dataset"):
            bucket.setdefault("deepeval_by_dataset", {})[run["dataset"]] = run

    for run in ragas_runs:
        ensure_model(run["model"])["ragas"].append(run)

    report_body = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset": {
            "id": ds.id,
            "name": ds.name,
            "topic": ds.topic,
            "hf_id": ds.hf_id,
            "description": ds.description,
            "task_prompt": ds.task_prompt,
        },
        "agenda": TASK_AGENDA,
        "frameworks": [
            {
                "framework": f.framework,
                "metric": f.metric,
                "description": f.description,
                "interpretation": f.interpretation,
            }
            for f in FRAMEWORK_METRICS
        ],
        "runs": {
            "promptfoo": promptfoo_runs,
            "deepeval": deepeval_runs,
            "ragas": ragas_runs,
        },
        "models": models,
    }
    report_body["comparison"] = build_comparison(report_body)
    report_body["scope"] = _report_scope(report_body["comparison"], dataset_id)
    return report_body


def report_to_markdown(report: dict) -> str:
    ds = report["dataset"]
    lines = [
        "# LLM Eval Lab — Combined Report",
        "",
        f"**Generated:** {report['generated_at']}",
        "",
        "## Task",
        "",
        report["agenda"]["goal"],
        "",
        "### Pipeline",
        "",
    ]
    for step in report["agenda"]["pipeline"]:
        lines.append(f"- {step}")

    lines.extend(
        [
            "",
            "## Eval scope",
            "",
        ]
    )
    scope = report.get("scope") or {}
    if scope.get("mode") == "portfolio":
        lines.append(f"- **Mode:** Portfolio ({scope.get('track_count', len(scope.get('tracks', [])))} tracks)")
        lines.append(f"- **Tracks:** {', '.join(scope.get('tracks', []))}")
        lines.append(
            "- **Default dataset tag:** "
            f"{ds['name']} (`{ds['id']}`) — metadata anchor only; comparison table spans all tracks."
        )
    else:
        lines.extend(
            [
                f"- **Name:** {ds['name']} (`{ds['id']}`)",
                f"- **Topic:** {ds['topic']}",
                f"- **Source:** [{ds['hf_id']}](https://huggingface.co/datasets/{ds['hf_id']})",
                f"- **Description:** {ds['description']}",
            ]
        )

    lines.extend(
        [
            "",
            "## Metrics by framework",
            "",
            "| Framework | Metric | What it measures |",
            "|-----------|--------|------------------|",
        ]
    )
    for fw in report["frameworks"]:
        lines.append(f"| {fw['framework']} | {fw['metric']} | {fw['description']} |")

    comparison = report.get("comparison") or {}
    models = comparison.get("models") or []
    tracks = comparison.get("tracks") or []

    if models and tracks:
        lines.extend(["", "## Side-by-side comparison", ""])
        lines.extend(
            _comparison_markdown_table(
                tracks, models, "promptfoo", _format_promptfoo_cell, "Promptfoo (pass rate)"
            )
        )
        lines.extend(
            _comparison_markdown_table(
                tracks, models, "deepeval", _format_deepeval_cell, "DeepEval (judge pass rate)"
            )
        )
        lines.extend(
            _comparison_markdown_table(
                tracks, models, "ragas", _format_ragas_cell, "RAGAS (faithfulness · relevancy)"
            )
        )
    else:
        lines.extend(["", "## Results by model", ""])
        for model, data in sorted(report["models"].items()):
            lines.append(f"### {model}")
            lines.append("")
            pf = data.get("promptfoo_qa")
            if pf and pf.get("providers"):
                for p in pf["providers"]:
                    rate = format_rate_pct(p.get("pass_rate"))
                    lines.append(
                        f"- **Promptfoo (QA):** {p['pass']}/{p['total']} pass ({rate}) — `{p['provider']}`"
                    )
            pfi = data.get("promptfoo_ifeval")
            if pfi and pfi.get("providers"):
                for p in pfi["providers"]:
                    rate = format_rate_pct(p.get("pass_rate"))
                    lines.append(f"- **IFEval:** {p['pass']}/{p['total']} pass ({rate})")
            de = data.get("deepeval")
            if de and de.get("tests"):
                rate = format_rate_pct(de.get("pass_rate"))
                lines.append(f"- **DeepEval:** {de['passed']}/{de['tests']} pass ({rate})")
            for rg in data.get("ragas") or []:
                avgs = rg.get("averages") or {}
                parts = ", ".join(f"{k}={format_score(v)}" for k, v in avgs.items())
                lines.append(f"- **RAGAS ({rg['config']}):** n={rg['samples']} — {parts}")
            lines.append("")

    return "\n".join(lines)


def export_report(out_dir: Path | None = None, dataset: str | None = None) -> dict[str, Path]:
    report = build_combined_report(dataset)
    report["performance"] = build_performance_report()
    out = out_dir or (RESULTS / "report")
    out.mkdir(parents=True, exist_ok=True)

    json_path = out / "combined_report.json"
    md_path = out / "combined_report.md"
    perf_path = out / "performance.json"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(report_to_markdown(report), encoding="utf-8")
    perf_path.write_text(
        json.dumps(report["performance"], indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return {"json": json_path, "markdown": md_path, "performance": perf_path, "report": report}
