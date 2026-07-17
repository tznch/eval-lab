#!/usr/bin/env python3
"""CLI entry for dashboard-triggered eval runs."""

from __future__ import annotations

import argparse
import sys

from shared.eval_runner import run_eval


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run eval from dashboard selections")
    parser.add_argument("--model-id", required=True)
    parser.add_argument(
        "--dataset-id",
        action="append",
        dest="dataset_ids",
        required=True,
        help="Dataset id (repeat or pass comma-separated)",
    )
    parser.add_argument("--temperature", type=float, required=True)
    parser.add_argument(
        "--frameworks",
        required=True,
        help="Comma-separated: promptfoo,deepeval,ragas",
    )
    args = parser.parse_args(argv)

    frameworks = [f.strip() for f in args.frameworks.split(",") if f.strip()]
    datasets: list[str] = []
    for raw in args.dataset_ids:
        datasets.extend(d.strip() for d in raw.split(",") if d.strip())
    # Preserve order, drop duplicates
    seen: set[str] = set()
    dataset_ids = []
    for d in datasets:
        if d not in seen:
            seen.add(d)
            dataset_ids.append(d)

    try:
        run_eval(
            model_id=args.model_id,
            dataset_ids=dataset_ids,
            temperature=args.temperature,
            frameworks=frameworks,
        )
    except Exception as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
