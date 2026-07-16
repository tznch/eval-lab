#!/usr/bin/env python3
"""Move legacy flat result paths into t0.2/ temperature subfolders."""

from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
TAG = "t0.2"


def migrate_tree(base: Path, leaf_name: str) -> int:
    moved = 0
    if not base.exists():
        return moved
    for model_dir in sorted(base.iterdir()):
        if not model_dir.is_dir() or model_dir.name.startswith("t"):
            continue
        for child in sorted(model_dir.iterdir()):
            if child.name.startswith("t"):
                continue
            if child.is_dir():
                dest = model_dir / TAG / child.name
                if dest.exists():
                    continue
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(child), str(dest))
                moved += 1
                print(f"  {child.relative_to(ROOT)} -> {dest.relative_to(ROOT)}")
            elif child.is_file() and child.name.endswith("_scores.csv"):
                dest = model_dir / TAG / child.name
                if dest.exists():
                    continue
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(child), str(dest))
                moved += 1
                print(f"  {child.relative_to(ROOT)} -> {dest.relative_to(ROOT)}")
    return moved


def main() -> None:
    total = 0
    for framework in ("promptfoo", "deepeval", "ragas"):
        print(f"Migrating {framework}...")
        total += migrate_tree(RESULTS / framework, "output.json")
    print(f"Done. Moved {total} paths into {TAG}/.")


if __name__ == "__main__":
    main()
