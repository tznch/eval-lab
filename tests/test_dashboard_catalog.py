"""Tests for dashboard filter catalog."""

from shared.reporting.dashboard_catalog import build_dashboard_catalog, run_key


def test_run_key():
    assert run_key("bonsai", "t0.2") == "bonsai:t0.2"


def test_build_dashboard_catalog():
    report = {
        "generated_at": "2026-01-01",
        "comparison": {
            "models": ["bonsai (t0.2)", "qwen27 (t0.2)"],
            "runs": [
                {"model": "bonsai", "temp_tag": "t0.2"},
                {"model": "qwen27", "temp_tag": "t0.2"},
            ],
            "tracks": [{"dataset": "sciq", "models": {}}],
        },
        "performance": {"models": {}},
    }
    catalog = build_dashboard_catalog(report)
    assert catalog["models"] == ["bonsai", "qwen27"]
    assert catalog["temps"] == ["t0.2"]
    assert catalog["datasets"] == ["sciq"]
    assert len(catalog["runs"]) == 2
