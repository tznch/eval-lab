"""Known model metadata for profiles (optional enrichment).

Empty by default — models are configured via HuggingFace import / env keys
(`{ID}_BASE_URL`, `{ID}_MODEL_PATH`, `{ID}_MODEL_NAME`).
"""

MODEL_REGISTRY: dict[str, dict[str, str]] = {}
