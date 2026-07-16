#!/usr/bin/env python3
"""Smoke test for configured LLM judge (GLM or OpenRouter)."""

import json
import sys

from shared.adapters.judge import get_judge, judge_label
from shared.config import load_settings


def main() -> None:
    settings = load_settings()
    judge = get_judge(settings)
    print(f"Judge: {judge_label(settings)}")
    result = judge.evaluate(
        question="What is 2+2?",
        answer="4",
        ground_truth="4",
    )
    print(json.dumps(result, indent=2))
    if result.get("score", 0) < 0.5:
        sys.exit(1)


if __name__ == "__main__":
    main()
