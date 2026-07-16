"""Sample complexity tagging and failure stratification (eval best practices).

Best-practice references applied here:
- Stratify RAG metrics by context length quartiles (RAGAS / retrieval literature).
- Report pass rate by difficulty proxy when human labels are unavailable (HELM-style).
- Separate failure modes: grounding (faithfulness) vs answer quality (judge) vs format (assert).
"""

from __future__ import annotations

from shared.reporting.score_format import round_score
from shared.schemas.eval_sample import EvalSample

# Context length buckets (characters) — align with local CPU context windows
CONTEXT_BUCKETS = (
    ("short", 0, 299),
    ("medium", 300, 799),
    ("long", 800, 10_000_000),
)

COMPLEXITY_TIERS = ("easy", "medium", "hard")


def context_bucket(context_chars: int) -> str:
    for name, lo, hi in CONTEXT_BUCKETS:
        if lo <= context_chars <= hi:
            return name
    return "long"


def _question_complexity(question: str) -> float:
    """Heuristic 0–1: longer / multi-clause questions score higher."""
    words = question.split()
    n = len(words)
    word_score = min(1.0, n / 25)
    multi = sum(1 for w in (" and ", " or ", " how many ", " what are ", " which ") if w in question.lower())
    multi_score = min(1.0, multi / 2)
    return 0.6 * word_score + 0.4 * multi_score


def complexity_score(
    *,
    context_chars: int,
    answer_chars: int,
    question: str,
    task_type: str,
) -> float:
    ctx_score = min(1.0, context_chars / 1200)
    ans_score = min(1.0, answer_chars / 120)
    q_score = _question_complexity(question)
    if task_type == "intent":
        # Intent utterances are short; weight question + category ambiguity lightly
        return 0.5 * q_score + 0.3 * ans_score + 0.2 * ctx_score
    return 0.45 * ctx_score + 0.25 * ans_score + 0.30 * q_score


def complexity_tier(score: float) -> str:
    if score < 0.33:
        return "easy"
    if score < 0.66:
        return "medium"
    return "hard"


def annotate_sample(sample: EvalSample) -> EvalSample:
    """Fill complexity metadata on a sample (mutates copy)."""
    ctx = len(sample.context or "")
    ans = len(sample.ground_truth or "")
    q = len(sample.question or "")
    score = complexity_score(
        context_chars=ctx,
        answer_chars=ans,
        question=sample.question,
        task_type=sample.task_type,
    )
    return sample.model_copy(
        update={
            "context_chars": ctx,
            "answer_chars": ans,
            "question_chars": q,
            "context_bucket": context_bucket(ctx),
            "complexity_score": round(score, 3),
            "complexity": complexity_tier(score),
        }
    )


def empty_stratum() -> dict:
    return {"pass": 0, "fail": 0, "total": 0, "pass_rate": None}


def add_outcome(stratum: dict, passed: bool) -> None:
    stratum["total"] += 1
    if passed:
        stratum["pass"] += 1
    else:
        stratum["fail"] += 1
    t = stratum["total"]
    stratum["pass_rate"] = round_score(stratum["pass"] / t) if t else None


def finalize_strata(table: dict[str, dict]) -> dict[str, dict]:
    return dict(sorted(table.items()))
