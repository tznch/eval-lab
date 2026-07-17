"""Tests for live eval run status."""

from shared.reporting import run_status as rs
from shared.reporting.run_status import (
    complete_step,
    finish_run,
    init_run,
    read_status,
    start_step,
)


def test_init_run_sets_running(tmp_path, monkeypatch):
    monkeypatch.setattr(rs, "STATUS_PATH", tmp_path / "run_status.json")
    data = init_run("bonsai", "t0.7", ["sciq"], ["promptfoo", "deepeval", "ragas"])
    assert data["status"] == "running"
    assert data["total_steps"] == 3
    assert data["step"] == 0
    assert read_status()["model"] == "bonsai"


def test_step_advance(tmp_path, monkeypatch):
    monkeypatch.setattr(rs, "STATUS_PATH", tmp_path / "run_status.json")
    init_run("bonsai", "t0.2", ["sciq"], ["promptfoo"])
    start_step("sciq", "promptfoo")
    s = read_status()
    assert s["current"]["track"] == "sciq"
    assert s["current"]["framework"] == "promptfoo"
    complete_step("sciq", "promptfoo", ok=True, duration_s=10.0, artifact="results/promptfoo/bonsai/t0.2/sciq/output.json")
    s = read_status()
    assert s["step"] == 1
    assert len(s["completed"]) == 1
    assert s["completed"][0]["ok"] is True


def test_finish_run(tmp_path, monkeypatch):
    monkeypatch.setattr(rs, "STATUS_PATH", tmp_path / "run_status.json")
    init_run("bonsai", "t0.7", ["sciq"], ["promptfoo"])
    finish_run("complete")
    assert read_status()["status"] == "complete"


def test_init_run_records_pid(tmp_path, monkeypatch):
    monkeypatch.setattr(rs, "STATUS_PATH", tmp_path / "run_status.json")
    data = init_run("bonsai", "t0.7", ["sciq"], ["promptfoo"], pid=12345)
    assert data["pid"] == 12345


def test_stop_run_marks_cancelled(tmp_path, monkeypatch):
    monkeypatch.setattr(rs, "STATUS_PATH", tmp_path / "run_status.json")
    monkeypatch.setattr(rs, "_pid_alive", lambda _pid: False)
    init_run("bonsai", "t0.7", ["sciq"], ["promptfoo"], pid=99999)
    result = rs.stop_run()
    assert result["ok"] is True
    assert read_status()["status"] == "cancelled"


def test_stop_run_when_idle(tmp_path, monkeypatch):
    monkeypatch.setattr(rs, "STATUS_PATH", tmp_path / "run_status.json")
    rs.set_idle()
    result = rs.stop_run()
    assert result["ok"] is False
