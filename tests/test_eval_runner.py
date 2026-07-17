"""Tests for dashboard eval runner."""

from pathlib import Path

import pytest

from shared.eval_runner import (
    is_run_in_progress,
    temp_tag,
)
from shared.setup.model_server import find_legacy_start_script


def test_temp_tag():
    assert temp_tag(0.7) == "t0.7"
    assert temp_tag(1.0) == "t1"


def test_find_legacy_start_script_unknown():
    assert find_legacy_start_script("no-such-model") is None


def test_find_legacy_start_script_matches_file(tmp_path, monkeypatch):
    models = tmp_path / "models"
    models.mkdir()
    script = models / "start-demo-server.sh"
    script.write_text("#!/bin/bash\n")
    monkeypatch.setattr("shared.setup.model_server.ROOT", tmp_path)
    path = find_legacy_start_script("demo")
    assert path == script


def test_is_run_in_progress_when_running(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "shared.eval_runner.read_status",
        lambda: {"status": "running"},
    )
    assert is_run_in_progress() is True


def test_is_run_in_progress_when_idle(monkeypatch):
    monkeypatch.setattr("shared.eval_runner.read_status", lambda: {"status": "idle"})
    assert is_run_in_progress() is False


def test_run_eval_refuses_when_already_running(monkeypatch):
    monkeypatch.setattr("shared.eval_runner.is_run_in_progress", lambda: True)
    from shared.eval_runner import run_eval

    with pytest.raises(RuntimeError, match="already running"):
        run_eval(
            model_id="bonsai",
            dataset_ids=["sciq"],
            temperature=0.7,
            frameworks=["promptfoo"],
        )


def test_run_eval_calls_frameworks(monkeypatch, tmp_path):
    calls: list[tuple[str | None, str]] = []

    monkeypatch.setattr("shared.eval_runner.is_run_in_progress", lambda: False)
    monkeypatch.setattr("shared.eval_runner.is_cancel_requested", lambda: False)
    monkeypatch.setattr("shared.eval_runner.init_run", lambda *a, **k: {})
    monkeypatch.setattr("shared.eval_runner.load_project_env", lambda: None)
    monkeypatch.setattr(
        "shared.eval_runner.prepare_dataset_if_needed",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        "shared.eval_runner.apply_run_env",
        lambda **_k: ("http://127.0.0.1:8081/v1", "t0.7"),
    )
    monkeypatch.setattr("shared.eval_runner.ensure_server", lambda *_a, **_k: None)

    def fake_run_fw(framework, **kwargs):
        calls.append((kwargs.get("dataset_id"), framework))
        return True

    monkeypatch.setattr("shared.eval_runner.run_framework", fake_run_fw)
    monkeypatch.setattr(
        "shared.eval_runner._run_cmd",
        lambda *_a, **_k: True,
    )
    finished: list[str] = []
    monkeypatch.setattr(
        "shared.eval_runner.finish_run",
        lambda status="complete": finished.append(status),
    )

    from shared.eval_runner import run_eval

    run_eval(
        model_id="bonsai",
        dataset_ids=["sciq", "nq"],
        temperature=0.7,
        frameworks=["promptfoo", "ragas"],
    )
    assert calls == [
        ("sciq", "promptfoo"),
        ("sciq", "ragas"),
        ("nq", "promptfoo"),
        ("nq", "ragas"),
    ]
    assert finished == ["complete"]
