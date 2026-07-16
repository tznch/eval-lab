import pytest

from shared.adapters.judge import get_judge
from shared.adapters.dataset_loader import load_samples
from shared.adapters.target_model import TargetModelClient
from shared.config import load_settings


@pytest.fixture(scope="session")
def settings():
    return load_settings()


@pytest.fixture(scope="session")
def target_model(settings):
    return TargetModelClient(settings)


@pytest.fixture(scope="session")
def judge(settings):
    return get_judge(settings)


def _format_prompt(sample) -> str:
    if sample.task_type == "intent":
        return (
            f"Support category hint: {sample.context or 'general'}\n\n"
            f"User message: {sample.question}\n\n"
            "Classify the user intent. Reply with ONLY the intent label (snake_case), nothing else."
        )
    ctx = sample.context or "No context provided."
    return f"Context:\n{ctx}\n\nQuestion: {sample.question}\n\nAnswer concisely."


def _load_test_samples():
    import os

    limit = int(os.getenv("DEEPEVAL_LIMIT", "5"))
    dataset = os.getenv("EVAL_DATASET", "feta")
    try:
        return load_samples(dataset, limit=limit)
    except FileNotFoundError:
        pytest.skip(
            f"No samples. Run: python scripts/prepare_samples.py --config {dataset}"
        )


@pytest.mark.parametrize("sample", _load_test_samples(), ids=lambda s: s.id)
def test_answer_quality(sample, target_model, judge):
    answer = target_model.complete(_format_prompt(sample))
    result = judge.evaluate(sample.question, answer, sample.ground_truth)
    assert result["score"] >= 0.3, f"Low score ({result['score']}): {result.get('reason', '')}"
