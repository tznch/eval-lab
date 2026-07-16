"""Tests for dashboard filter parsing."""

from shared.reporting.dashboard_filters import FilterState, parse_filter_params


CATALOG = {
    "models": ["bonsai", "qwen27"],
    "temps": ["t0.2", "t0.7"],
    "datasets": ["sciq", "bitext_intent"],
    "frameworks": ["promptfoo", "deepeval", "ragas"],
}


def test_default_filters_use_catalog():
    f = parse_filter_params({}, CATALOG)
    assert f.models == ["bonsai", "qwen27"]
    assert f.temps == ["t0.2", "t0.7"]
    assert f.dataset == "all"


def test_filter_single_model():
    f = parse_filter_params({"models": "bonsai"}, CATALOG)
    assert f.models == ["bonsai"]
    assert f.matches_run("bonsai", "t0.2")
    assert not f.matches_run("qwen27", "t0.2")


def test_filter_dataset():
    f = parse_filter_params({"dataset": "sciq"}, CATALOG)
    assert f.matches_dataset("sciq")
    assert not f.matches_dataset("bitext_intent")
