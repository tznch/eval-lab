#!/usr/bin/env python3
"""Smoke test Bonsai-27B Q1 via llama-server on :8081."""

import sys

import httpx

from shared.config import load_settings


def main() -> None:
    settings = load_settings()
    base = settings.bonsai_base_url.rstrip("/")
    model = settings.bonsai_model_name
    print(f"Bonsai: {model} @ {base}")
    response = httpx.post(
        f"{base}/chat/completions",
        json={
            "model": model,
            "messages": [{"role": "user", "content": "What is 2+2? Reply with just the number."}],
            "max_tokens": 20,
            "temperature": 0.7,
        },
        timeout=120.0,
    )
    response.raise_for_status()
    answer = response.json()["choices"][0]["message"]["content"].strip()
    print(f"Response: {answer}")
    if "4" not in answer:
        sys.exit(1)


if __name__ == "__main__":
    main()
