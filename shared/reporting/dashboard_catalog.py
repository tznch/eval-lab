"""Filter catalog for interactive dashboard controls."""

from __future__ import annotations

from shared.reporting.run_paths import model_label


def run_key(model: str, temp_tag: str) -> str:
    return f"{model}:{temp_tag}"


def build_dashboard_catalog(report: dict) -> dict:
    comparison = report.get("comparison") or {}
    runs_meta = comparison.get("runs") or []
    run_labels = comparison.get("models") or []
    tracks = comparison.get("tracks") or []

    runs = []
    for meta, label in zip(runs_meta, run_labels):
        model = meta["model"]
        temp_tag = meta["temp_tag"]
        runs.append(
            {
                "key": run_key(model, temp_tag),
                "model": model,
                "temp_tag": temp_tag,
                "temp": temp_tag.removeprefix("t"),
                "label": label,
            }
        )

    models = sorted({r["model"] for r in runs})
    temps = sorted({r["temp_tag"] for r in runs}, key=lambda t: float(t.removeprefix("t")))
    datasets = [t["dataset"] for t in tracks]

    perf = report.get("performance") or {}
    model_specs = {
        mid: {
            "name": spec.get("name", mid),
            "quant": spec.get("quant"),
            "gguf_gb": spec.get("gguf_gb"),
        }
        for mid, spec in (perf.get("models") or {}).items()
    }

    return {
        "generated_at": report.get("generated_at"),
        "scope": report.get("scope") or {},
        "runs": runs,
        "models": models,
        "temps": temps,
        "datasets": datasets,
        "frameworks": ["promptfoo", "deepeval", "ragas", "performance"],
        "model_specs": model_specs,
        "comparison": comparison,
        "performance": perf,
    }
