"""Model specs and runtime performance aggregation for dashboard."""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from shared.reporting.run_paths import (
    LEGACY_TEMP_TAG,
    model_label,
    parse_deepeval_path,
    parse_promptfoo_path,
    parse_ragas_path,
)

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "results"
MISSING = "—"


@dataclass(frozen=True)
class ModelSpec:
    id: str
    name: str
    quant: str
    bpw: float
    gguf_gb: float
    port: int
    gguf_path: str
    notes: str = ""


MODEL_REGISTRY: dict[str, ModelSpec] = {
    "bonsai": ModelSpec(
        id="bonsai",
        name="Bonsai-27B Q1",
        quant="Q1_0",
        bpw=1.125,
        gguf_gb=3.6,
        port=8081,
        gguf_path="data/models/bonsai-27b-q1/Bonsai-27B-Q1_0.gguf",
        notes="PrismML 1-bit transform of Qwen3.6-27B",
    ),
    "qwen27": ModelSpec(
        id="qwen27",
        name="Qwen3.6-27B IQ2_XXS",
        quant="UD-IQ2_XXS",
        bpw=2.8,
        gguf_gb=9.4,
        port=8082,
        gguf_path="data/models/qwen3.6-27b-iq2/Qwen3.6-27B-UD-IQ2_XXS.gguf",
        notes="Whitepaper comparable conventional quant baseline",
    ),
    "gemma": ModelSpec(
        id="gemma",
        name="Gemma-4-26B",
        quant="A4B",
        bpw=4.0,
        gguf_gb=0.0,
        port=8080,
        gguf_path="(configured via TARGET_MODEL)",
        notes="Optional lab target",
    ),
}


def _fmt_seconds(ms: int | float | None) -> str:
    if ms is None:
        return MISSING
    sec = float(ms) / 1000.0
    if sec < 60:
        return f"{sec:.1f}s"
    return f"{sec / 60:.1f}m"


def _fmt_tok_s(tokens: int | float | None, ms: int | float | None) -> str:
    if not tokens or not ms or ms <= 0:
        return MISSING
    rate = float(tokens) / (float(ms) / 1000.0)
    return f"{rate:.2f}"


def _fmt_mib(mib: int | float | None) -> str:
    if mib is None:
        return MISSING
    return f"{mib / 1024:.1f} GB"


def parse_server_ram_mib(log_path: Path) -> int | None:
    if not log_path.exists():
        return None
    text = log_path.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"projected to use (\d+) MiB of host memory", text)
    return int(match.group(1)) if match else None


def summarize_promptfoo_perf(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    metrics = (data.get("results", {}).get("prompts") or [{}])[0].get("metrics", {})
    rows = data.get("results", {}).get("results") or []
    lats = [r.get("latencyMs", 0) for r in rows if r.get("latencyMs")]
    usage = metrics.get("tokenUsage") or {}
    total_ms = metrics.get("totalLatencyMs") or sum(lats)
    completion = usage.get("completion") or 0
    total_tokens = usage.get("total") or 0
    n = len(rows) or metrics.get("testPassCount", 0) + metrics.get("testFailCount", 0)
    return {
        "samples": n,
        "total_latency_ms": total_ms,
        "avg_latency_ms": round(sum(lats) / len(lats)) if lats else None,
        "prompt_tokens": usage.get("prompt"),
        "completion_tokens": completion,
        "total_tokens": total_tokens,
        "completion_tok_per_s": round(completion / (total_ms / 1000), 2) if total_ms and completion else None,
        "avg_completion_tok_per_s": _fmt_tok_s(completion, total_ms),
    }


def summarize_deepeval_perf(path: Path) -> dict | None:
    try:
        tree = ET.parse(path)
    except (ET.ParseError, OSError):
        return None
    for suite in tree.getroot().iter("testsuite"):
        tests = int(suite.get("tests", 0))
        failures = int(suite.get("failures", 0))
        errors = int(suite.get("errors", 0))
        time_s = float(suite.get("time", 0) or 0)
        return {
            "tests": tests,
            "passed": tests - failures - errors,
            "time_s": round(time_s, 1),
            "sec_per_test": round(time_s / tests, 1) if tests else None,
        }
    return None


def _discover_run_ids() -> set[tuple[str, str]]:
    runs: set[tuple[str, str]] = set()
    for framework, parser in (
        ("promptfoo", parse_promptfoo_path),
        ("deepeval", parse_deepeval_path),
        ("ragas", parse_ragas_path),
    ):
        base = RESULTS / framework
        if not base.exists():
            continue
        glob = "**/output.json" if framework == "promptfoo" else (
            "**/junit.xml" if framework == "deepeval" else "**/*_scores.csv"
        )
        for path in base.glob(glob):
            model, temp, _dataset = parser(path)
            if model and temp and model not in ("compare", "unknown"):
                runs.add((model, temp))
    return runs


def build_performance_report() -> dict:
    run_ids = sorted(_discover_run_ids(), key=lambda x: (x[0], x[1]))
    runs: list[dict] = []
    pf_base = RESULTS / "promptfoo"
    de_base = RESULTS / "deepeval"

    for model, temp in run_ids:
        spec = MODEL_REGISTRY.get(model)
        ram = parse_server_ram_mib(RESULTS / "logs" / f"{model}-server.log")
        tracks: dict[str, dict] = {}
        pf_total_ms = 0
        de_total_s = 0.0
        pf_samples = 0
        pf_completion = 0

        if pf_base.exists():
            pf_dir = pf_base / model / temp
            if pf_dir.is_dir():
                for output in sorted(pf_dir.glob("*/output.json")):
                    dataset = output.parent.name
                    pf = summarize_promptfoo_perf(output)
                    if pf:
                        tracks.setdefault(dataset, {})["promptfoo"] = pf
                        pf_total_ms += pf.get("total_latency_ms") or 0
                        pf_samples += pf.get("samples") or 0
                        pf_completion += pf.get("completion_tokens") or 0

        if de_base.exists():
            de_dir = de_base / model / temp
            if de_dir.is_dir():
                for junit in sorted(de_dir.glob("*/junit.xml")):
                    dataset = junit.parent.name
                    de = summarize_deepeval_perf(junit)
                    if de:
                        tracks.setdefault(dataset, {})["deepeval"] = de
                        de_total_s += de.get("time_s") or 0

        avg_latencies = [
            t["promptfoo"]["avg_latency_ms"]
            for t in tracks.values()
            if t.get("promptfoo", {}).get("avg_latency_ms")
        ]
        runs.append(
            {
                "label": model_label(model, temp.removeprefix("t")),
                "model": model,
                "temp_tag": temp,
                "spec": {
                    "name": spec.name if spec else model,
                    "quant": spec.quant if spec else MISSING,
                    "bpw": spec.bpw if spec else None,
                    "gguf_gb": spec.gguf_gb if spec else None,
                    "port": spec.port if spec else None,
                    "ram_projected_mib": ram,
                    "ram_projected_gb": round(ram / 1024, 1) if ram else None,
                },
                "tracks": tracks,
                "rollup": {
                    "promptfoo_total_ms": pf_total_ms or None,
                    "promptfoo_total_human": _fmt_seconds(pf_total_ms) if pf_total_ms else MISSING,
                    "deepeval_total_s": round(de_total_s, 1) if de_total_s else None,
                    "promptfoo_samples": pf_samples or None,
                    "avg_latency_ms": round(sum(avg_latencies) / len(avg_latencies)) if avg_latencies else None,
                    "completion_tok_per_s": round(pf_completion / (pf_total_ms / 1000), 2)
                    if pf_total_ms and pf_completion
                    else None,
                },
            }
        )

    columns = [r["label"] for r in runs]
    return {
        "models": {m.id: m.__dict__ for m in MODEL_REGISTRY.values()},
        "runs": runs,
        "columns": columns,
    }
