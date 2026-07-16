"""Consistent numeric precision for eval scores and rates."""

from __future__ import annotations

SCORE_DECIMALS = 3


def round_score(value: float | int | None) -> float | None:
    if value is None:
        return None
    return round(float(value), SCORE_DECIMALS)


def format_score(value: float | int | None) -> str:
    if value is None:
        return "—"
    return f"{round_score(value):.{SCORE_DECIMALS}f}"


def format_rate_pct(value: float | None) -> str:
    """Format a 0–1 pass rate as percentage with SCORE_DECIMALS precision."""
    if value is None:
        return "—"
    return f"{round_score(value * 100):.{SCORE_DECIMALS}f}%"
