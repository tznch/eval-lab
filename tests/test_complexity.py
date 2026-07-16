"""Tests for complexity tagging and failure stratification helpers."""

from shared.reporting.complexity import (
    annotate_sample,
    complexity_tier,
    context_bucket,
    empty_stratum,
    add_outcome,
    finalize_strata,
)
from shared.schemas.eval_sample import EvalSample


def test_context_bucket_short_medium_long():
    assert context_bucket(100) == "short"
    assert context_bucket(500) == "medium"
    assert context_bucket(1200) == "long"


def test_complexity_tier_boundaries():
    assert complexity_tier(0.2) == "easy"
    assert complexity_tier(0.5) == "medium"
    assert complexity_tier(0.8) == "hard"


def test_annotate_sample_fills_metadata():
    sample = EvalSample(
        id="t1",
        question="What is the capital of France and why?",
        ground_truth="Paris",
        context="x" * 400,
        task_type="extractive_qa",
        category="geo",
    )
    out = annotate_sample(sample)
    assert out.context_chars == 400
    assert out.context_bucket == "medium"
    assert out.complexity in ("easy", "medium", "hard")
    assert 0 <= out.complexity_score <= 1


def test_stratum_pass_rate():
    s = empty_stratum()
    add_outcome(s, True)
    add_outcome(s, False)
    assert s["total"] == 2
    assert s["pass"] == 1
    assert s["fail"] == 1
    assert s["pass_rate"] == 0.5
    table = finalize_strata({"hard": s, "easy": empty_stratum()})
    assert list(table.keys()) == ["easy", "hard"]
