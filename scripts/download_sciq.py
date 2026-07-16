#!/usr/bin/env python3
"""Download AllenAI SciQ validation split to data/raw/sciq/."""

import argparse
import json
from pathlib import Path

from datasets import load_dataset

from shared.hf_auth import get_hf_token

REPO = "allenai/sciq"
RAW_DIR = Path("data/raw/sciq")


def download(split: str = "validation", limit: int | None = None) -> Path:
    token = get_hf_token()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {REPO} split={split} ...")
    ds = load_dataset(REPO, split=split, token=token)
    out = RAW_DIR / f"{split}.jsonl"
    n = 0
    with out.open("w", encoding="utf-8") as f:
        for i, row in enumerate(ds):
            if limit is not None and i >= limit:
                break
            f.write(json.dumps(dict(row), ensure_ascii=False) + "\n")
            n += 1
    print(f"Wrote {n} rows → {out}")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Download SciQ dataset")
    parser.add_argument("--split", default="validation", choices=["train", "validation", "test"])
    parser.add_argument("--limit", type=int, default=None, help="Max rows (default: all)")
    args = parser.parse_args()
    download(args.split, args.limit)


if __name__ == "__main__":
    main()
