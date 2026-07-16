#!/usr/bin/env python3
"""Smoke test local target model via llama-server."""

import sys

from shared.adapters.target_model import TargetModelClient
from shared.config import load_settings


def main() -> None:
    settings = load_settings()
    client = TargetModelClient(settings)
    print(f"Target: {settings.target_model_name} @ {settings.target_base_url}")
    answer = client.complete("What is 2+2? Reply with just the number.")
    print(f"Response: {answer.strip()}")
    if "4" not in answer:
        sys.exit(1)


if __name__ == "__main__":
    main()
