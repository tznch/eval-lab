#!/usr/bin/env python3
"""Download Qwen3.6-27B UD-Q4_K_XL (MTP GGUF) — ~18 GB 4-bit baseline."""

import argparse
from pathlib import Path

from huggingface_hub import hf_hub_download

from shared.hf_auth import get_hf_token

# Unsloth Dynamic 4-bit; see https://huggingface.co/unsloth/Qwen3.6-27B-MTP-GGUF
REPO = "unsloth/Qwen3.6-27B-MTP-GGUF"
DEFAULT_FILE = "Qwen3.6-27B-UD-Q4_K_XL.gguf"
OUT_DIR = Path("data/models/qwen3.6-27b-q4")


def download(filename: str = DEFAULT_FILE) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {REPO}/{filename} (~17.9 GB, UD-Q4_K_XL) ...")
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
        description="Download Qwen3.6-27B MTP UD-Q4_K_XL GGUF (4-bit quality baseline)"
    )
    parser.add_argument("--file", default=DEFAULT_FILE)
    args = parser.parse_args()
    download(args.file)


if __name__ == "__main__":
    main()
