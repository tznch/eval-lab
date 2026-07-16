#!/usr/bin/env python3
"""Export combined eval report (JSON + Markdown) for external visualization."""

import argparse
from pathlib import Path

from dotenv import load_dotenv

from shared.reporting.combined_report import export_report

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description="Export combined eval report")
    parser.add_argument(
        "--dataset",
        default=None,
        help="Dataset id for agenda metadata (default: EVAL_DATASET env or sciq)",
    )
    parser.add_argument(
        "--out",
        default=str(ROOT / "results" / "report"),
        help="Output directory",
    )
    args = parser.parse_args()

    paths = export_report(Path(args.out), args.dataset)
    print(f"JSON:     {paths['json']}")
    print(f"Markdown: {paths['markdown']}")


if __name__ == "__main__":
    main()
