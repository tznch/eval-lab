#!/usr/bin/env python3
"""Download Bonsai-27B 1-bit GGUF from HuggingFace."""

import argparse
from pathlib import Path

from huggingface_hub import hf_hub_download

from shared.hf_auth import get_hf_token

REPO = "prism-ml/Bonsai-27B-gguf"
DEFAULT_FILE = "Bonsai-27B-Q1_0.gguf"
OUT_DIR = Path("data/models/bonsai-27b-q1")


def download(filename: str = DEFAULT_FILE) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {REPO}/{filename} ...")
    path = hf_hub_download(
        repo_id=REPO,
        filename=filename,
        local_dir=OUT_DIR,
        token=get_hf_token(),
    )
    print(f"Done: {path}")
    return Path(path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Download Bonsai-27B GGUF")
    parser.add_argument(
        "--file",
        default=DEFAULT_FILE,
        help="GGUF filename (default: Bonsai-27B-Q1_0.gguf, 1-bit ~3.6GB)",
    )
    args = parser.parse_args()
    download(args.file)


if __name__ == "__main__":
    main()
