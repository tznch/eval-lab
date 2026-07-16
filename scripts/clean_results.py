#!/usr/bin/env python3
"""Remove generated eval artifacts (promptfoo, deepeval, ragas, dashboard, reports)."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIRS = [
    "results/promptfoo",
    "results/deepeval",
    "results/ragas",
    "results/analysis",
    "results/report",
    "results/dashboard",
]
FILES = [
    "eval/promptfoo/tests/generated.yaml",
    "eval/promptfoo/promptfooconfig.resolved.yaml",
]


def clean(*, dry_run: bool = False) -> None:
    for rel in DIRS:
        path = ROOT / rel
        if not path.exists():
            continue
        if dry_run:
            count = sum(1 for _ in path.rglob("*") if _.is_file())
            print(f"would remove {rel}/ ({count} files)")
            continue
        shutil.rmtree(path)
        path.mkdir(parents=True, exist_ok=True)
        print(f"removed {rel}/")

    logs = ROOT / "results/logs"
    if logs.exists():
        for log in logs.glob("*.log"):
            if dry_run:
                print(f"would remove {log.relative_to(ROOT)}")
            else:
                log.unlink(missing_ok=True)

    for rel in FILES:
        path = ROOT / rel
        if not path.exists():
            continue
        if dry_run:
            print(f"would remove {rel}")
        else:
            path.unlink(missing_ok=True)
            print(f"removed {rel}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean eval result artifacts")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    clean(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
