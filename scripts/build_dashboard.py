#!/usr/bin/env python3
"""Export dashboard JSON artifacts (live UI served by dashboard_api)."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from dotenv import load_dotenv

from shared.reporting.combined_report import export_report
from shared.reporting.dashboard_catalog import build_dashboard_catalog
from shared.reporting.failure_analysis import export_failure_analysis

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
OUT = RESULTS / "dashboard"

load_dotenv(ROOT / ".env")


def main() -> None:
    dataset = os.getenv("EVAL_DATASET", "sciq")
    OUT.mkdir(parents=True, exist_ok=True)

    exported = export_report(RESULTS / "report", dataset)
    report = exported["report"]

    catalog = build_dashboard_catalog(report)
    catalog_path = RESULTS / "report" / "dashboard_catalog.json"
    catalog_path.write_text(json.dumps(catalog, indent=2, ensure_ascii=False), encoding="utf-8")

    failure_path = export_failure_analysis()

    for name in ("combined_report.json", "combined_report.md", "performance.json", "dashboard_catalog.json"):
        src = RESULTS / "report" / name
        if src.exists():
            shutil.copy2(src, OUT / name)
    if failure_path.exists():
        shutil.copy2(failure_path, OUT / "failure_stratification.json")

    print(f"Dashboard exports written to {OUT}/")
    print(f"Combined report: {exported['json']}")
    print("Live UI: make dashboard-serve → http://127.0.0.1:3100/")


if __name__ == "__main__":
    main()
