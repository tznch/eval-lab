#!/usr/bin/env python3
"""Run Promptfoo IFEval mini-track against Bonsai (or current env target)."""

import os
import subprocess
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
PROMPTFOO_DIR = ROOT / "eval" / "promptfoo"
RESOLVED = "promptfooconfig.ifeval.resolved.yaml"


def main() -> None:
    load_dotenv(ROOT / ".env")
    limit = os.getenv("IFEVAL_LIMIT", "10")
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/prepare_ifeval_promptfoo.py"),
            "--limit",
            limit,
        ],
        check=True,
        cwd=ROOT,
    )

    env = os.environ.copy()
    model_id = env.get("EVAL_MODEL_ID", "bonsai")
    base_url = env.get("TARGET_MODEL_BASE_URL", env.get("BONSAI_BASE_URL", "http://127.0.0.1:8081/v1"))
    model_name = env.get("TARGET_MODEL_NAME", env.get("BONSAI_MODEL_NAME", "bonsai-27b-q1"))
    temp = float(env.get("TARGET_TEMPERATURE", "0.7"))
    out = env.get(
        "PROMPTFOO_IFEVAL_OUTPUT",
        str(ROOT / "results" / "promptfoo" / "ifeval" / f"{model_id}.json"),
    )
    Path(out).parent.mkdir(parents=True, exist_ok=True)

    config = {
        "description": f"IFEval instruction-following ({model_id})",
        "prompts": ["file://prompts/ifeval.txt"],
        "providers": [
            {
                "id": f"openai:chat:{model_name}",
                "label": model_id,
                "config": {
                    "apiBaseUrl": base_url,
                    "apiKey": "local",
                    "max_tokens": 1024,
                    "temperature": temp,
                },
            }
        ],
        "tests": "file://tests/ifeval.yaml",
        "outputPath": out,
        "evaluateOptions": {"maxConcurrency": 1},
    }
    resolved = PROMPTFOO_DIR / RESOLVED
    resolved.write_text(yaml.dump(config, sort_keys=False, allow_unicode=True), encoding="utf-8")

    result = subprocess.run(
        ["promptfoo", "eval", "--config", RESOLVED],
        cwd=PROMPTFOO_DIR,
        env=env,
    )
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
