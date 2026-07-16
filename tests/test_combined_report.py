"""Tests for combined report comparison matrix."""

from shared.reporting.combined_report import (
    _format_promptfoo_cell,
    _report_scope,
    build_comparison,
)


def test_build_comparison_side_by_side():
    report = {
        "runs": {
            "promptfoo": [
                {
                    "path": "results/promptfoo/bonsai/t0.2/sciq/output.json",
                    "providers": [{"pass": 25, "fail": 0, "error": 0, "total": 25, "pass_rate": 1.0}],
                    "track": "qa",
                },
                {
                    "path": "results/promptfoo/qwen27/t0.2/sciq/output.json",
                    "providers": [{"pass": 24, "fail": 1, "error": 0, "total": 25, "pass_rate": 0.96}],
                    "track": "qa",
                },
            ],
            "deepeval": [
                {
                    "path": "results/deepeval/bonsai/t0.2/sciq/junit.xml",
                    "model": "bonsai",
                    "dataset": "sciq",
                    "tests": 25,
                    "passed": 25,
                    "pass_rate": 1.0,
                },
            ],
            "ragas": [
                {
                    "path": "results/ragas/bonsai/t0.2/sciq_scores.csv",
                    "model": "bonsai",
                    "config": "sciq",
                    "samples": 25,
                    "averages": {"faithfulness": 0.9, "answer_relevancy": 0.5},
                },
            ],
        }
    }
    comparison = build_comparison(report)
    assert comparison["models"] == ["bonsai (t0.2)", "qwen27 (t0.2)"]
    sciq = next(t for t in comparison["tracks"] if t["dataset"] == "sciq")
    assert sciq["models"]["bonsai (t0.2)"]["promptfoo"]["pass"] == 25
    assert sciq["models"]["qwen27 (t0.2)"]["promptfoo"]["pass"] == 24
    assert sciq["models"]["bonsai (t0.2)"]["deepeval"]["passed"] == 25
    assert sciq["models"]["qwen27 (t0.2)"]["deepeval"] is None


def test_format_promptfoo_cell_missing():
    assert _format_promptfoo_cell(None) == "—"


def test_report_scope_portfolio():
    comparison = {
        "tracks": [{"dataset": "sciq"}, {"dataset": "bitext_intent"}],
    }
    scope = _report_scope(comparison, "sciq")
    assert scope["mode"] == "portfolio"
    assert scope["track_count"] == 2
