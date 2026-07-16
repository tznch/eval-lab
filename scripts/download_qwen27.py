#!/usr/bin/env python3
"""Download Qwen3.6-27B UD-IQ2_XXS — whitepaper comparable conventional quant (~9.4 GB)."""

import argparse
from pathlib import Path

from huggingface_hub import hf_hub_download

from shared.hf_auth import get_hf_token

# Matches whitepaper row: Qwen3.6-27B IQ2_XXS (~9.4 GB, 2.8 bpw)
REPO = "unsloth/Qwen3.6-27B-GGUF"
DEFAULT_FILE = "Qwen3.6-27B-UD-IQ2_XXS.gguf"
OUT_DIR = Path("data/models/qwen3.6-27b-iq2")


def download(filename: str = DEFAULT_FILE) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {REPO}/{filename} (~9.4 GB, whitepaper IQ2_XXS comparable) ...")
    path = hf_hub_download(
        repo_id=REPO,
        filename=filename,
        local_dir=OUT_DIR,
        token=get_hf_token(),
    )
    print(f"Done: {path}")
    return Path(path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download Qwen3.6-27B IQ2_XXS GGUF (conventional quant baseline for Bonsai)"
    )
    parser.add_argument("--file", default=DEFAULT_FILE)
    args = parser.parse_args()
    download(args.file)


if __name__ == "__main__":
    main()
