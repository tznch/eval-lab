#!/usr/bin/env python3
"""Run DeepEval pytest suite for the current target model."""

import os
import subprocess
import sys
from pathlib import Path

from shared.reporting.run_paths import deepeval_output

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    model_id = os.getenv("EVAL_MODEL_ID", "default")
    dataset = os.getenv("EVAL_DATASET", "sciq")
    out = Path(os.getenv("DEEPEVAL_OUTPUT", deepeval_output(model_id, dataset)))
    out.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        str(ROOT / "eval/deepeval/test_uda_qa.py"),
        "-v",
        "--tb=short",
        f"--junitxml={out}",
    ]
    result = subprocess.run(cmd, cwd=ROOT)
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
