"""Tests for performance report aggregation."""

import json
from pathlib import Path

from shared.reporting.performance_report import (
    build_performance_report,
    parse_server_ram_mib,
    summarize_promptfoo_perf,
)


def test_summarize_promptfoo_perf(tmp_path):
    payload = {
        "results": {
            "prompts": [
                {
                    "metrics": {
                        "totalLatencyMs": 10000,
                        "tokenUsage": {"prompt": 100, "completion": 50, "total": 150},
                    }
                }
            ],
            "results": [{"latencyMs": 400}, {"latencyMs": 600}],
        }
    }
    p = tmp_path / "output.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    stats = summarize_promptfoo_perf(p)
    assert stats["total_latency_ms"] == 10000
    assert stats["avg_latency_ms"] == 500
    assert stats["completion_tok_per_s"] == 5.0


def test_parse_server_ram_mib(tmp_path):
    log = tmp_path / "server.log"
    log.write_text("projected to use 20987 MiB of host memory vs. 60895 MiB\n", encoding="utf-8")
    assert parse_server_ram_mib(log) == 20987


def test_build_performance_report_empty():
    report = build_performance_report()
    assert "runs" in report
    assert "columns" in report
