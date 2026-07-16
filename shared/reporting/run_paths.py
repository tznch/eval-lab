"""Result path helpers — separate artifacts by model, temperature, and dataset."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "results"
LEGACY_TEMP_TAG = "t0.2"


def temp_tag(temp: str | float | None = None) -> str:
    value = temp if temp is not None else os.getenv("TARGET_TEMPERATURE", "0.2")
    return f"t{float(value):g}"


def promptfoo_output(model: str, dataset: str, temp: str | float | None = None) -> Path:
    return RESULTS / "promptfoo" / model / temp_tag(temp) / dataset / "output.json"


def deepeval_output(model: str, dataset: str, temp: str | float | None = None) -> Path:
    return RESULTS / "deepeval" / model / temp_tag(temp) / dataset / "junit.xml"


def ragas_output(model: str, config: str, temp: str | float | None = None) -> Path:
    return RESULTS / "ragas" / model / temp_tag(temp) / f"{config}_scores.csv"


def model_label(model: str, temp: str | float | None) -> str:
    return f"{model} ({temp_tag(temp)})"


def parse_promptfoo_path(path: Path) -> tuple[str, str | None, str | None]:
    """Return (model, temp_tag|None, dataset). Supports legacy flat layout."""
    full = path if path.is_absolute() else ROOT / path
    try:
        rel = full.relative_to(RESULTS / "promptfoo")
    except ValueError:
        return "unknown", None, None
    if full.parent.name == "ifeval":
        return full.stem, None, "ifeval"
    if rel.parts[0] == "compare" or full.name == "compare.json":
        return "compare", None, None
    if len(rel.parts) == 3 and rel.parts[2] == "output.json":
        return rel.parts[0], LEGACY_TEMP_TAG, rel.parts[1]
    if len(rel.parts) == 4 and rel.parts[3] == "output.json" and rel.parts[1].startswith("t"):
        return rel.parts[0], rel.parts[1], rel.parts[2]
    return rel.parts[0], None, None


def parse_deepeval_path(path: Path) -> tuple[str, str | None, str | None]:
    full = path if path.is_absolute() else ROOT / path
    try:
        rel = full.relative_to(RESULTS / "deepeval")
    except ValueError:
        return "unknown", None, None
    if len(rel.parts) == 3 and rel.parts[2] == "junit.xml":
        return rel.parts[0], LEGACY_TEMP_TAG, rel.parts[1]
    if len(rel.parts) == 4 and rel.parts[3] == "junit.xml" and rel.parts[1].startswith("t"):
        return rel.parts[0], rel.parts[1], rel.parts[2]
    return rel.parts[0], None, None


def parse_ragas_path(path: Path) -> tuple[str, str | None, str | None]:
    full = path if path.is_absolute() else ROOT / path
    try:
        rel = full.relative_to(RESULTS / "ragas")
    except ValueError:
        return "unknown", None, None
    config = full.stem.replace("_scores", "")
    if len(rel.parts) == 2:
        return rel.parts[0], LEGACY_TEMP_TAG, config
    if len(rel.parts) == 3 and rel.parts[1].startswith("t"):
        return rel.parts[0], rel.parts[1], config
    return rel.parts[0], None, config
