"""View models for HTMX dashboard partials."""

from __future__ import annotations

import csv
import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path

from shared.reporting.combined_report import (
    _format_deepeval_cell,
    _format_promptfoo_cell,
    _format_ragas_cell,
    build_combined_report,
)
from shared.reporting.dashboard_catalog import build_dashboard_catalog
from shared.reporting.dashboard_filters import FilterState
from shared.reporting.eval_agenda import FRAMEWORK_GUIDES, get_dataset_info
from shared.reporting.failure_analysis import build_portfolio_failure_report
from shared.reporting.performance_report import build_performance_report
from shared.reporting.run_paths import model_label, parse_deepeval_path, parse_promptfoo_path, parse_ragas_path
from shared.reporting.score_format import format_rate_pct, format_score

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "results"


def promptfoo_ui_url() -> str:
    port = os.getenv("PROMPTFOO_VIEW_PORT", "15500")
    return f"http://127.0.0.1:{port}/"


def framework_guide(framework_id: str) -> dict:
    g = FRAMEWORK_GUIDES[framework_id]
    return {
        "id": g.id,
        "title": g.title,
        "tagline": g.tagline,
        "what_it_does": g.what_it_does,
        "how_to_read": list(g.how_to_read),
        "caveats": list(g.caveats),
    }


def load_catalog() -> dict:
    path = RESULTS / "report" / "combined_report.json"
    if path.exists():
        report = json.loads(path.read_text(encoding="utf-8"))
    else:
        report = build_combined_report()
    return build_dashboard_catalog(report)


def _parse_junit(path: Path) -> dict | None:
    try:
        tree = ET.parse(path)
    except (ET.ParseError, OSError):
        return None
    for suite in tree.getroot().iter("testsuite"):
        return {
            "tests": int(suite.get("tests", 0)),
            "failures": int(suite.get("failures", 0)),
            "errors": int(suite.get("errors", 0)),
            "time": suite.get("time", "0"),
        }
    return None


def build_deepeval_groups(filters: FilterState) -> list[dict]:
    de_dir = RESULTS / "deepeval"
    if not de_dir.exists():
        return []

    grouped: dict[tuple[str, str], dict] = {}
    for path in sorted(de_dir.rglob("junit.xml")):
        model, temp_tag, dataset = parse_deepeval_path(path)
        if not model or not temp_tag or not dataset:
            continue
        if not filters.matches_run(model, temp_tag):
            continue
        if not filters.matches_dataset(dataset):
            continue
        if not filters.includes_framework("deepeval"):
            continue

        suite = _parse_junit(path)
        if not suite:
            continue

        key = (model, temp_tag)
        group = grouped.setdefault(
            key,
            {
                "model": model,
                "temp_tag": temp_tag,
                "label": model_label(model, temp_tag.removeprefix("t")),
                "tracks": [],
                "passed_total": 0,
                "tests_total": 0,
            },
        )
        passed = suite["tests"] - suite["failures"] - suite["errors"]
        group["tracks"].append(
            {
                "dataset": dataset,
                "passed": passed,
                "tests": suite["tests"],
                "failures": suite["failures"],
                "errors": suite["errors"],
                "time": suite["time"],
                "path": str(path.relative_to(ROOT)),
            }
        )
        group["passed_total"] += passed
        group["tests_total"] += suite["tests"]

    groups = list(grouped.values())
    for g in groups:
        g["tracks"] = sorted(g["tracks"], key=lambda t: t["dataset"])
        g["pass_rate"] = format_rate_pct(g["passed_total"] / g["tests_total"]) if g["tests_total"] else "—"
        g["track_count"] = len(g["tracks"])
    return sorted(groups, key=lambda g: (g["model"], g["temp_tag"]))


def _temp_from_tag(temp_tag: str) -> float:
    return float(temp_tag.removeprefix("t"))


def _framework_track_row(fw_key: str, dataset: str, raw: dict | None) -> dict:
    formatted = {
        "promptfoo": _format_promptfoo_cell,
        "deepeval": _format_deepeval_cell,
        "ragas": _format_ragas_cell,
    }[fw_key](raw)
    cell = _report_cell(fw_key, raw, formatted)
    row = {
        "dataset": dataset,
        "missing": cell["missing"],
        "value": cell["value"],
        "rate": cell.get("rate"),
        "level": cell.get("level", "missing"),
    }
    if fw_key in ("promptfoo", "deepeval"):
        if raw:
            total = int(raw.get("total") or 0)
            passed = int(raw.get("pass") or 0)
            fail = int(raw["fail"]) if raw.get("fail") is not None else max(total - passed, 0)
            row.update({"pass": passed, "fail": fail, "total": total})
        else:
            row.update({"pass": None, "fail": None, "total": None})
    return row


def build_report_view(filters: FilterState, catalog: dict) -> dict:
    comparison = catalog.get("comparison") or {}
    runs_meta = comparison.get("runs") or []
    all_tracks = comparison.get("tracks") or []
    tracks = [t for t in all_tracks if filters.matches_dataset(t["dataset"])]

    runs = []
    for meta in runs_meta:
        model = meta["model"]
        temp_tag = meta["temp_tag"]
        if not filters.matches_run(model, temp_tag):
            continue
        label = model_label(model, temp_tag.removeprefix("t"))
        frameworks = {}
        for fw in ("promptfoo", "deepeval", "ragas"):
            rows = []
            for track in tracks:
                raw = (track.get("models") or {}).get(label, {}).get(fw)
                # Framework filter: still emit rows, but mark missing if fw filtered out
                if not filters.includes_framework(fw):
                    raw = None
                rows.append(_framework_track_row(fw, track["dataset"], raw))
            frameworks[fw] = rows
        runs.append(
            {
                "model": model,
                "temp_tag": temp_tag,
                "temperature": _temp_from_tag(temp_tag),
                "label": f"{model} · t={temp_tag.removeprefix('t')}",
                "frameworks": frameworks,
            }
        )

    runs.sort(key=lambda r: (r["model"], r["temperature"]))
    return {
        "runs": runs,
        "scope": catalog.get("scope") or {},
        "track_count": len({t["dataset"] for t in tracks}),
        "generated_at": catalog.get("generated_at"),
    }


def _report_cell(fw_key: str, data: dict | None, formatted: str) -> dict:
    cell = {"value": formatted, "missing": formatted == "—"}
    if not data:
        cell["level"] = "missing"
        return cell
    if fw_key in ("promptfoo", "deepeval"):
        rate = data.get("pass_rate")
        if rate is not None:
            pct = float(rate) * 100 if float(rate) <= 1 else float(rate)
            cell["rate"] = round(pct, 1)
            cell["level"] = "low" if pct < 60 else ("mid" if pct < 85 else "good")
        else:
            cell["level"] = "missing"
    elif fw_key == "ragas":
        faith = (data.get("averages") or {}).get("faithfulness")
        if faith is not None:
            cell["rate"] = round(float(faith) * 100, 1)
            cell["level"] = "low" if faith < 0.5 else ("mid" if faith < 0.75 else "good")
        else:
            cell["level"] = "missing"
    else:
        cell["level"] = "missing"
    return cell


def build_overview_view(catalog: dict, filters: FilterState) -> dict:
    report_path = RESULTS / "report" / "combined_report.json"
    runs = {"promptfoo": 0, "deepeval": 0, "ragas": 0}
    if report_path.exists():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        for fw in runs:
            runs[fw] = len(report.get("runs", {}).get(fw, []))
    from shared.setup.readiness import has_env_profile

    return {
        "runs": runs,
        "catalog": catalog,
        "filters": filters,
        "setup": {"has_profile": has_env_profile()},
    }


def _summarize_promptfoo_file(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    results = data.get("results", {})
    rows = []
    for p in results.get("prompts", []):
        m = p.get("metrics", {})
        total = m.get("testPassCount", 0) + m.get("testFailCount", 0) + m.get("testErrorCount", 0)
        passed = m.get("testPassCount", 0)
        rows.append(
            {
                "provider": p.get("provider", "?"),
                "pass": passed,
                "fail": m.get("testFailCount", 0),
                "error": m.get("testErrorCount", 0),
                "total": total,
                "rate": format_rate_pct(passed / total) if total else "—",
                "rate_val": round(passed / total * 100, 1) if total else None,
            }
        )
    return {
        "path": str(path.relative_to(ROOT)),
        "eval_id": data.get("evalId", "—"),
        "timestamp": results.get("timestamp", "—"),
        "rows": rows,
    }


def build_promptfoo_view(filters: FilterState) -> dict:
    pf_dir = RESULTS / "promptfoo"
    runs = []
    if pf_dir.exists() and filters.includes_framework("promptfoo"):
        for path in sorted(pf_dir.rglob("output.json")):
            model, temp_tag, dataset = parse_promptfoo_path(path)
            if model in ("compare", "unknown") or not temp_tag or not dataset:
                continue
            if not filters.matches_run(model, temp_tag) or not filters.matches_dataset(dataset):
                continue
            summary = _summarize_promptfoo_file(path)
            if not summary:
                continue
            runs.append(
                {
                    "model": model,
                    "temp_tag": temp_tag,
                    "dataset": dataset,
                    "rel": str(path.relative_to(pf_dir)),
                    **summary,
                }
            )
    return {"promptfoo_url": promptfoo_ui_url(), "guide": framework_guide("promptfoo"), "runs": runs}


def build_ragas_view(filters: FilterState) -> dict:
    rg_dir = RESULTS / "ragas"
    sections = []
    if rg_dir.exists() and filters.includes_framework("ragas"):
        for path in sorted(rg_dir.rglob("*_scores.csv")):
            model, temp_tag, config = parse_ragas_path(path)
            if not model or not temp_tag or not config:
                continue
            if not filters.matches_run(model, temp_tag) or not filters.matches_dataset(config):
                continue
            try:
                rows = list(csv.DictReader(path.open(encoding="utf-8")))
            except OSError:
                continue
            if not rows:
                continue
            headers = list(rows[0].keys())
            avg_row: dict[str, str | None] = {}
            for h in headers:
                try:
                    vals = [float(r[h]) for r in rows if r.get(h)]
                    avg_row[h] = format_score(sum(vals) / len(vals)) if vals else None
                except ValueError:
                    avg_row[h] = None
            sections.append(
                {
                    "model": model,
                    "temp_tag": temp_tag,
                    "config": config,
                    "filename": path.name,
                    "headers": headers,
                    "rows": rows[:10],
                    "avg_row": avg_row,
                    "sample_count": len(rows),
                }
            )
    return {"guide": framework_guide("ragas"), "sections": sections}


def _build_perf_table(
    key: str,
    title: str,
    row_headers: list[str],
    rows: list[list[str]],
    runs: list[dict],
    track_rows: bool = False,
) -> dict:
    return {
        "key": key,
        "title": title,
        "headers": row_headers,
        "rows": rows,
        "runs": runs,
        "track_rows": track_rows,
    }


def build_performance_view(filters: FilterState) -> dict:
    perf_path = RESULTS / "report" / "performance.json"
    if perf_path.exists():
        perf = json.loads(perf_path.read_text(encoding="utf-8"))
    else:
        perf = build_performance_report()

    all_runs = perf.get("runs") or []
    runs = [r for r in all_runs if filters.matches_run(r["model"], r["temp_tag"])]
    if not filters.includes_framework("performance"):
        runs = []

    if not runs:
        return {"guide": framework_guide("performance"), "empty": True, "tables": []}

    columns = [r["label"] for r in runs]
    headers = ["Metric"] + columns
    track_headers = ["Track"] + columns

    def col_values(getter) -> list[str]:
        return [getter(r) for r in runs]

    spec_rows = [
        ["Quant"] + col_values(lambda r: r["spec"].get("quant") or "—"),
        ["BPW"] + col_values(lambda r: f"{r['spec']['bpw']:.2f}" if r["spec"].get("bpw") else "—"),
        ["GGUF size"] + col_values(
            lambda r: f"{r['spec']['gguf_gb']:.1f} GB" if r["spec"].get("gguf_gb") else "—"
        ),
        ["Projected RAM"] + col_values(
            lambda r: f"{r['spec']['ram_projected_gb']:.1f} GB" if r["spec"].get("ram_projected_gb") else "—"
        ),
        ["Port"] + col_values(lambda r: str(r["spec"].get("port") or "—")),
    ]
    rollup_rows = [
        ["Promptfoo total"] + col_values(lambda r: r["rollup"].get("promptfoo_total_human") or "—"),
        ["DeepEval total"] + col_values(
            lambda r: f"{r['rollup']['deepeval_total_s']}s" if r["rollup"].get("deepeval_total_s") else "—"
        ),
        ["Avg latency (Promptfoo)"] + col_values(
            lambda r: f"{r['rollup']['avg_latency_ms']} ms" if r["rollup"].get("avg_latency_ms") else "—"
        ),
        ["Completion tok/s"] + col_values(
            lambda r: str(r["rollup"]["completion_tok_per_s"]) if r["rollup"].get("completion_tok_per_s") else "—"
        ),
    ]

    all_tracks = sorted({ds for r in runs for ds in r.get("tracks", {})})
    all_tracks = [t for t in all_tracks if filters.matches_dataset(t)]
    pf_track_rows = []
    de_track_rows = []
    for track in all_tracks:
        pf_row = [track]
        de_row = [track]
        for run in runs:
            t = run.get("tracks", {}).get(track, {})
            pf = t.get("promptfoo")
            de = t.get("deepeval")
            if pf and pf.get("avg_latency_ms") is not None:
                tok = pf.get("completion_tok_per_s")
                tok_s = f" · {tok} tok/s" if tok else ""
                pf_row.append(f"{pf['avg_latency_ms']} ms avg{tok_s}")
            else:
                pf_row.append("—")
            if de and de.get("time_s") is not None:
                de_row.append(f"{de['time_s']}s ({de.get('tests', '?')} tests)")
            else:
                de_row.append("—")
        pf_track_rows.append(pf_row)
        de_track_rows.append(de_row)

    run_meta = [{"model": r["model"], "temp_tag": r["temp_tag"]} for r in runs]
    tables = [
        _build_perf_table("specs", "Static configuration", headers, spec_rows, run_meta),
        _build_perf_table("rollup", "Aggregate runtime (completed tracks only)", headers, rollup_rows, run_meta),
        _build_perf_table(
            "promptfoo",
            "Mean request latency · completion throughput",
            track_headers,
            pf_track_rows,
            run_meta,
            True,
        ),
        _build_perf_table("deepeval", "pytest suite duration", track_headers, de_track_rows, run_meta, True),
    ]
    by_key = {t["key"]: t for t in tables}
    return {"guide": framework_guide("performance"), "empty": False, "tables": tables, "by_key": by_key}


def _finalize_stratum(strata: dict) -> list[dict]:
    rows = []
    for key, s in sorted(strata.items()):
        rate = s.get("pass_rate")
        rows.append(
            {
                "label": key,
                "pass": s.get("pass", 0),
                "fail": s.get("fail", 0),
                "rate": format_rate_pct(rate) if rate is not None else "—",
            }
        )
    return rows


def build_failures_view(filters: FilterState) -> dict:
    report = build_portfolio_failure_report()
    tracks = []
    for track in report.get("tracks") or []:
        model = track.get("model", "")
        dataset = track.get("dataset", "")
        if filters.models and model not in filters.models:
            continue
        if not filters.matches_dataset(dataset):
            continue
        ds = get_dataset_info(dataset)
        by_fw = []
        for fw, s in (track.get("by_framework") or {}).items():
            if not filters.includes_framework(fw):
                continue
            rate = s.get("pass_rate")
            by_fw.append(
                {
                    "framework": fw,
                    "pass": s.get("pass", 0),
                    "fail": s.get("fail", 0),
                    "rate": format_rate_pct(rate) if rate is not None else "—",
                }
            )
        if not by_fw and filters.frameworks:
            continue
        failed = []
        for item in (track.get("failed_samples") or [])[:8]:
            fws = []
            for k, v in (item.get("frameworks") or {}).items():
                if not v.get("passed"):
                    fws.append(f"{k}:{'pass' if v.get('passed') else v.get('failure_mode', 'fail')}")
            failed.append(
                {
                    "sample_id": item.get("sample_id", "?"),
                    "complexity": item.get("complexity") or "?",
                    "context_bucket": item.get("context_bucket") or "?",
                    "frameworks": ", ".join(fws),
                }
            )
        tracks.append(
            {
                "dataset": dataset,
                "model": model,
                "name": ds.name,
                "topic": ds.topic,
                "sample_count": track.get("sample_count", 0),
                "by_framework": by_fw,
                "by_complexity": _finalize_stratum(track.get("by_complexity") or {}),
                "by_context_bucket": _finalize_stratum(track.get("by_context_bucket") or {}),
                "by_category": _finalize_stratum(track.get("by_category") or {}),
                "failure_modes": _finalize_stratum(track.get("failure_modes") or {}),
                "failed_samples": failed,
            }
        )
    return {
        "guide": framework_guide("failures"),
        "methodology": report.get("methodology") or {},
        "tracks": tracks,
    }
