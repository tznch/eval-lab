"""Canonical paths for per-dataset eval artifacts."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "results"


def promptfoo_output(model: str, dataset: str) -> Path:
    per_ds = RESULTS / "promptfoo" / model / dataset / "output.json"
    legacy = RESULTS / "promptfoo" / model / "output.json"
    return per_ds if per_ds.exists() else legacy


def deepeval_junit(model: str, dataset: str) -> Path:
    per_ds = RESULTS / "deepeval" / model / dataset / "junit.xml"
    legacy = RESULTS / "deepeval" / model / "junit.xml"
    return per_ds if per_ds.exists() else legacy


def ragas_scores(model: str, dataset: str) -> Path:
    return RESULTS / "ragas" / model / f"{dataset}_scores.csv"
