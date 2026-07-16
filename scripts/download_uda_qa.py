#!/usr/bin/env python3
"""Download UDA-QA parquet subset from HuggingFace."""

import argparse
from pathlib import Path

from huggingface_hub import hf_hub_download, snapshot_download

from shared.hf_auth import get_hf_token

REPO = "qinchuanhui/UDA-QA"
RAW_DIR = Path("data/raw/uda-qa")


def download_config(config: str, with_docs: bool = False, extended: bool = False) -> None:
    token = get_hf_token()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Downloading UDA-QA config: {config}")
    hf_hub_download(
        repo_id=REPO,
        filename=f"{config}/test_00000_of_00001.parquet",
        repo_type="dataset",
        local_dir=RAW_DIR,
        token=token,
    )
    if extended or config in ("feta", "nq"):
        ext_file = f"extended_qa_info/{config}_qa.json"
        print(f"Downloading {ext_file} ...")
        hf_hub_download(
            repo_id=REPO,
            filename=ext_file,
            repo_type="dataset",
            local_dir=RAW_DIR,
            token=token,
        )
    if with_docs:
        print("Downloading source documents (wiki_feta_docs.zip)...")
        snapshot_download(
            repo_id=REPO,
            repo_type="dataset",
            allow_patterns=["src_doc_files/wiki_feta_docs.zip"],
            local_dir=RAW_DIR,
            token=token,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Download UDA-QA dataset files")
    parser.add_argument(
        "--config",
        default="feta",
        choices=["feta", "nq", "paper_text", "paper_tab", "fin", "tat"],
    )
    parser.add_argument("--with-docs", action="store_true", help="Also download src_doc_files")
    parser.add_argument("--extended", action="store_true", help="Force download extended_qa_info")
    args = parser.parse_args()
    download_config(args.config, args.with_docs, args.extended)
    print(f"Done. Files in {RAW_DIR / args.config}")


if __name__ == "__main__":
    main()
