#!/usr/bin/env python3
"""Run HuggingFace work for a job already started by the dashboard API."""

from __future__ import annotations

import argparse

from shared.hf_import.datasets import import_hf_dataset
from shared.hf_import.models import download_gguf
from shared.hf_jobs import finish_job


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a background HuggingFace job")
    subparsers = parser.add_subparsers(dest="command", required=True)

    model = subparsers.add_parser("model-download")
    model.add_argument("--repo-id", required=True)
    model.add_argument("--filename", required=True)
    model.add_argument("--model-id")

    dataset = subparsers.add_parser("dataset-import")
    dataset.add_argument("--hf-id", required=True)
    dataset.add_argument("--split", required=True)
    dataset.add_argument("--local-id", required=True)
    dataset.add_argument("--question-col", required=True)
    dataset.add_argument("--answer-col", required=True)
    dataset.add_argument("--context-col")
    dataset.add_argument("--limit", type=int, default=200)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    try:
        if args.command == "model-download":
            result = download_gguf(
                repo_id=args.repo_id,
                filename=args.filename,
                model_id=args.model_id,
            )
            message = "Model download complete"
        else:
            mapping = {
                "question": args.question_col,
                "ground_truth": args.answer_col,
            }
            if args.context_col:
                mapping["context"] = args.context_col
            result = import_hf_dataset(
                hf_id=args.hf_id,
                split=args.split,
                local_id=args.local_id,
                mapping=mapping,
                limit=args.limit,
            )
            message = "Dataset import complete"
    except Exception as exc:
        finish_job(status="error", message=str(exc))
        raise SystemExit(1) from exc

    finish_job(status="complete", message=message, result=result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
