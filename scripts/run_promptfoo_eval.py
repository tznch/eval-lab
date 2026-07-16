#!/usr/bin/env python3
"""Run promptfoo eval with variables loaded from .env."""

import os
import subprocess
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

from shared.datasets.registry import get_dataset

ROOT = Path(__file__).resolve().parents[1]
PROMPTFOO_DIR = ROOT / "eval" / "promptfoo"
RESOLVED_CONFIG = "promptfooconfig.resolved.yaml"
PROMPT_FILES = {
    "qa": "prompts/qa.txt",
    "intent": "prompts/intent.resolved.txt",
    "faq": "prompts/qa.txt",
}


def prompt_for_dataset(dataset: str) -> str:
    manifest = get_dataset(dataset)
    key = manifest.eval.prompt if manifest else "qa"
    return PROMPT_FILES.get(key, PROMPT_FILES["qa"])


def write_resolved_config(env: dict[str, str]) -> str:
    """Write YAML with typed values (temperature must be numeric, not quoted string)."""
    model_id = env.get("EVAL_MODEL_ID", "default")
    dataset = env.get("EVAL_DATASET", "feta")
    prompt_file = prompt_for_dataset(dataset)
    config = {
        "description": f"{dataset} - single target model ({model_id})",
        "prompts": [f"file://{prompt_file}"],
        "providers": [
            {
                "id": f"openai:chat:{env['TARGET_MODEL_NAME']}",
                "label": model_id,
                "config": {
                    "apiBaseUrl": env["TARGET_MODEL_BASE_URL"],
                    "apiKey": "local",
                    "max_tokens": 512,
                    "temperature": float(env.get("TARGET_TEMPERATURE", "0.2")),
                },
            }
        ],
        "tests": "file://tests/generated.yaml",
        "outputPath": env["PROMPTFOO_OUTPUT"],
        "evaluateOptions": {"maxConcurrency": 1},
    }
    out = PROMPTFOO_DIR / RESOLVED_CONFIG
    out.write_text(yaml.dump(config, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return RESOLVED_CONFIG


def main() -> None:
    load_dotenv(ROOT / ".env")
    limit = os.getenv("PROMPTFOO_LIMIT", "5")
    dataset = os.getenv("EVAL_DATASET", "feta")
    config = os.getenv("PROMPTFOO_CONFIG", "promptfooconfig.single.yaml")
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/jsonl_to_promptfoo.py"),
            "--config",
            dataset,
            "--limit",
            limit,
        ],
        check=True,
        cwd=ROOT,
    )
    env = os.environ.copy()
    model_id = env.get("EVAL_MODEL_ID", "default")
    if "PROMPTFOO_OUTPUT" not in env:
        out = ROOT / "results" / "promptfoo" / model_id / dataset / "output.json"
    else:
        out = Path(env["PROMPTFOO_OUTPUT"])
        if not out.is_absolute():
            out = ROOT / out
    env["PROMPTFOO_OUTPUT"] = str(out)
    out.parent.mkdir(parents=True, exist_ok=True)

    # Per-model single config: resolve env vars in Python (avoids YAML {{}} quirks)
    if config == "promptfooconfig.single.yaml":
        required = ("TARGET_MODEL_NAME", "TARGET_MODEL_BASE_URL", "TARGET_TEMPERATURE")
        missing = [k for k in required if k not in env]
        if missing:
            raise SystemExit(f"Missing env for promptfoo: {', '.join(missing)}")
        config = write_resolved_config(env)

    result = subprocess.run(
        ["promptfoo", "eval", "--config", config],
        cwd=PROMPTFOO_DIR,
        env=env,
    )
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
