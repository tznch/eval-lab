"""Tests for dashboard view builders."""

import json
from pathlib import Path

from shared.reporting.dashboard_filters import FilterState
from shared.reporting.dashboard_views import (
    build_deepeval_groups,
    build_performance_view,
    build_promptfoo_view,
    build_report_view,
    _report_cell,
)


def test_build_promptfoo_view_filters(tmp_path, monkeypatch):
    root = tmp_path
    pf = root / "results" / "promptfoo" / "bonsai" / "t0.2" / "sciq" / "output.json"
    pf.parent.mkdir(parents=True)
    pf.write_text(
        json.dumps(
            {
                "evalId": "test",
                "results": {
                    "timestamp": "2026-01-01",
                    "prompts": [
                        {
                            "provider": "local",
                            "metrics": {"testPassCount": 8, "testFailCount": 2, "testErrorCount": 0, "score": 0.8},
                        }
                    ],
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("shared.reporting.dashboard_views.ROOT", root)
    monkeypatch.setattr("shared.reporting.dashboard_views.RESULTS", root / "results")
    monkeypatch.setattr("shared.reporting.run_paths.ROOT", root)
    monkeypatch.setattr("shared.reporting.run_paths.RESULTS", root / "results")

    filters = FilterState(models=["bonsai"], temps=["t0.2"], dataset="all", frameworks=["promptfoo"])
    view = build_promptfoo_view(filters)
    assert len(view["runs"]) == 1
    assert view["runs"][0]["rows"][0]["pass"] == 8


def test_build_performance_view_empty_framework():
    filters = FilterState(models=["bonsai"], temps=["t0.2"], dataset="all", frameworks=["promptfoo"])
    view = build_performance_view(filters)
    assert view["empty"] is True


def test_build_report_short_titles():
    catalog = {
        "generated_at": "2026-01-01",
        "comparison": {
            "models": ["bonsai (t0.2)"],
            "runs": [{"model": "bonsai", "temp_tag": "t0.2"}],
            "tracks": [
                {
                    "dataset": "sciq",
                    "models": {
                        "bonsai (t0.2)": {
                            "promptfoo": {"pass": 5, "total": 10, "pass_rate": 0.5},
                        },
                    },
                }
            ],
        },
    }
    filters = FilterState(models=["bonsai"], temps=["t0.2"], dataset="all", frameworks=["promptfoo"])
    view = build_report_view(filters, catalog)
    assert view["tables"][0]["short_title"] == "Promptfoo"


def test_report_cell_levels():
    cell = _report_cell("promptfoo", {"pass_rate": 0.5, "pass": 5, "total": 10}, "5/10 (50.000%)")
    assert cell["level"] == "low"
    assert cell["rate"] == 50.0


def test_build_deepeval_groups(tmp_path, monkeypatch):
    root = tmp_path
    de = root / "results" / "deepeval" / "bonsai" / "t0.2" / "sciq"
    de.mkdir(parents=True)
    (de / "junit.xml").write_text(
        '<?xml version="1.0"?><testsuite tests="10" failures="1" errors="0" time="5.0"/>',
        encoding="utf-8",
    )
    monkeypatch.setattr("shared.reporting.dashboard_views.ROOT", root)
    monkeypatch.setattr("shared.reporting.dashboard_views.RESULTS", root / "results")
    monkeypatch.setattr("shared.reporting.run_paths.ROOT", root)
    monkeypatch.setattr("shared.reporting.run_paths.RESULTS", root / "results")

    filters = FilterState(models=["bonsai"], temps=["t0.2"], dataset="all", frameworks=["deepeval"])
    groups = build_deepeval_groups(filters)
    assert len(groups) == 1
    assert groups[0]["model"] == "bonsai"
    assert groups[0]["tracks"][0]["dataset"] == "sciq"
    assert groups[0]["passed_total"] == 9


def test_build_report_view_filters_columns():
    catalog = {
        "generated_at": "2026-01-01",
        "comparison": {
            "models": ["bonsai (t0.2)", "qwen27 (t0.2)"],
            "runs": [
                {"model": "bonsai", "temp_tag": "t0.2"},
                {"model": "qwen27", "temp_tag": "t0.2"},
            ],
            "tracks": [
                {
                    "dataset": "sciq",
                    "models": {
                        "bonsai (t0.2)": {
                            "promptfoo": {"pass": 5, "total": 10, "pass_rate": 0.5},
                        },
                        "qwen27 (t0.2)": {
                            "promptfoo": {"pass": 8, "total": 10, "pass_rate": 0.8},
                        },
                    },
                }
            ],
        },
    }
    filters = FilterState(models=["bonsai"], temps=["t0.2"], dataset="all", frameworks=["promptfoo"])
    view = build_report_view(filters, catalog)
    assert view["models"] == ["bonsai (t0.2)"]
    assert len(view["tables"]) == 1
    assert view["tables"][0]["rows"][0]["cells"][0]["value"].startswith("5/10")
