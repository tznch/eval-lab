#!/usr/bin/env python3
"""Download real-world HF datasets: financial QA, e-commerce FAQ, Bitext support."""

import argparse
import json
from pathlib import Path

from datasets import load_dataset

from shared.hf_auth import get_hf_token

RAW = Path("data/raw")

DATASETS = {
    "financial_qa": {
        "repo": "virattt/financial-qa-10K",
        "split": "train",
        "limit_default": 500,
    },
    "ecommerce_faq": {
        "repo": "NebulaByte/E-Commerce_FAQs",
        "split": "train",
        "limit_default": 500,
    },
    "bitext_intent": {
        "repo": "bitext/Bitext-customer-support-llm-chatbot-training-dataset",
        "split": "train",
        "limit_default": 2000,
    },
}


def download(name: str, limit: int | None = None) -> Path:
    if name not in DATASETS:
        raise ValueError(f"Unknown dataset {name}. Choose: {list(DATASETS)}")
    spec = DATASETS[name]
    token = get_hf_token()
    out_dir = RAW / name
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{spec['split']}.jsonl"
    cap = limit if limit is not None else spec["limit_default"]
    print(f"Downloading {spec['repo']} (limit={cap}) ...")
    ds = load_dataset(spec["repo"], split=spec["split"], token=token, streaming=True)
    n = 0
    with out.open("w", encoding="utf-8") as f:
        for row in ds:
            if n >= cap:
                break
            f.write(json.dumps(dict(row), ensure_ascii=False) + "\n")
            n += 1
    print(f"Wrote {n} rows → {out}")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Download real-world eval datasets")
    parser.add_argument(
        "dataset",
        choices=list(DATASETS.keys()) + ["all"],
        help="Dataset to download (or all)",
    )
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    if args.dataset == "all":
        for name in DATASETS:
            download(name, args.limit)
    else:
        download(args.dataset, args.limit)


if __name__ == "__main__":
    main()
