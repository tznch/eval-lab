"""Tests for HuggingFace dashboard API routes."""

import pytest
from fastapi.testclient import TestClient

from scripts.dashboard_api import create_app


def test_list_files_ok(monkeypatch):
    monkeypatch.setattr(
        "scripts.dashboard_api.list_gguf_files", lambda repo_id: ["a.gguf"]
    )

    response = TestClient(create_app()).post(
        "/api/hf/models/list-files", json={"repo_id": "org/x"}
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True, "files": ["a.gguf"]}


def test_list_files_rejects_extra_fields():
    response = TestClient(create_app()).post(
        "/api/hf/models/list-files",
        json={"repo_id": "org/x", "token": "not-accepted"},
    )

    assert response.status_code == 400
    assert response.json()["ok"] is False


def test_download_409_when_job_running(monkeypatch):
    monkeypatch.setattr("scripts.dashboard_api.is_job_running", lambda: True)

    response = TestClient(create_app()).post(
        "/api/hf/models/download",
        json={"repo_id": "org/x", "filename": "a.gguf"},
    )

    assert response.status_code == 409
    assert response.json()["ok"] is False


@pytest.mark.parametrize(
    ("route", "payload"),
    [
        (
            "/api/hf/models/download",
            {"repo_id": "org/x", "filename": "a.gguf"},
        ),
        (
            "/api/hf/datasets/import",
            {
                "hf_id": "org/data",
                "split": "train",
                "local_id": "local",
                "question_col": "question",
                "answer_col": "answer",
            },
        ),
    ],
)
def test_start_job_race_returns_409(monkeypatch, route, payload):
    monkeypatch.setattr("scripts.dashboard_api.is_job_running", lambda: False)

    def raise_running(**kwargs):
        raise RuntimeError("An HF job is already running")

    monkeypatch.setattr("scripts.dashboard_api.start_job", raise_running)

    response = TestClient(create_app()).post(route, json=payload)

    assert response.status_code == 409
    assert response.json() == {
        "ok": False,
        "message": "An HF job is already running",
    }


@pytest.mark.parametrize(
    ("route", "payload"),
    [
        (
            "/api/hf/models/download",
            {"repo_id": "org/x", "filename": "a.gguf"},
        ),
        (
            "/api/hf/datasets/import",
            {
                "hf_id": "org/data",
                "split": "train",
                "local_id": "local",
                "question_col": "question",
                "answer_col": "answer",
            },
        ),
    ],
)
def test_spawn_failure_finishes_job_with_error(
    tmp_path, monkeypatch, route, payload
):
    monkeypatch.setattr("scripts.dashboard_api.ROOT", tmp_path)
    monkeypatch.setattr("scripts.dashboard_api.is_job_running", lambda: False)
    monkeypatch.setattr(
        "scripts.dashboard_api.start_job",
        lambda **kwargs: {"id": "1", "status": "running"},
    )
    finished = {}

    def fake_finish_job(**kwargs):
        finished.update(kwargs)
        return {"id": "1", **kwargs}

    def fail_spawn(*args, **kwargs):
        raise OSError("spawn failed")

    monkeypatch.setattr("scripts.dashboard_api.finish_job", fake_finish_job)
    monkeypatch.setattr("scripts.dashboard_api.subprocess.Popen", fail_spawn)

    response = TestClient(create_app()).post(route, json=payload)

    assert response.status_code == 500
    assert response.json() == {
        "ok": False,
        "message": "Failed to start HF job: spawn failed",
    }
    assert finished == {"status": "error", "message": "spawn failed"}


def test_download_starts_job_before_spawning(monkeypatch):
    monkeypatch.setattr("scripts.dashboard_api.is_job_running", lambda: False)
    events = []

    def fake_start_job(**kwargs):
        events.append(("start", kwargs))
        return {"id": "1", "kind": kwargs["kind"], "status": "running"}

    class FakePopen:
        def __init__(self, args, **kwargs):
            events.append(("spawn", args, kwargs))
            self.pid = 1

    monkeypatch.setattr("scripts.dashboard_api.start_job", fake_start_job)
    monkeypatch.setattr("scripts.dashboard_api.subprocess.Popen", FakePopen)

    response = TestClient(create_app()).post(
        "/api/hf/models/download",
        json={"repo_id": "org/x", "filename": "a.gguf", "model_id": "x"},
    )

    assert response.status_code == 202
    assert response.json()["job"]["id"] == "1"
    assert events[0] == (
        "start",
        {"kind": "model_download", "message": "Starting model download"},
    )
    args = events[1][1]
    assert "run_hf_job.py" in args[1]
    assert args[2:] == [
        "model-download",
        "--repo-id",
        "org/x",
        "--filename",
        "a.gguf",
        "--model-id",
        "x",
    ]


def test_dataset_import_spawns_with_optional_fields(monkeypatch):
    monkeypatch.setattr("scripts.dashboard_api.is_job_running", lambda: False)
    monkeypatch.setattr(
        "scripts.dashboard_api.start_job",
        lambda **kwargs: {"id": "2", "kind": kwargs["kind"], "status": "running"},
    )
    spawned = {}

    class FakePopen:
        def __init__(self, args, **kwargs):
            spawned["args"] = args
            self.pid = 2

    monkeypatch.setattr("scripts.dashboard_api.subprocess.Popen", FakePopen)

    response = TestClient(create_app()).post(
        "/api/hf/datasets/import",
        json={
            "hf_id": "org/data",
            "split": "validation",
            "local_id": "local",
            "question_col": "prompt",
            "answer_col": "answer",
            "context_col": "passage",
            "limit": 12,
        },
    )

    assert response.status_code == 202
    assert response.json()["job"]["kind"] == "dataset_import"
    assert spawned["args"][2:] == [
        "dataset-import",
        "--hf-id",
        "org/data",
        "--split",
        "validation",
        "--local-id",
        "local",
        "--question-col",
        "prompt",
        "--answer-col",
        "answer",
        "--context-col",
        "passage",
        "--limit",
        "12",
    ]


def test_dataset_import_defaults_split_to_train(monkeypatch):
    monkeypatch.setattr("scripts.dashboard_api.is_job_running", lambda: False)
    monkeypatch.setattr(
        "scripts.dashboard_api.start_job",
        lambda **kwargs: {"id": "3", "kind": kwargs["kind"], "status": "running"},
    )
    spawned = {}

    class FakePopen:
        def __init__(self, args, **kwargs):
            spawned["args"] = args
            self.pid = 3

    monkeypatch.setattr("scripts.dashboard_api.subprocess.Popen", FakePopen)

    response = TestClient(create_app()).post(
        "/api/hf/datasets/import",
        json={
            "hf_id": "org/data",
            "local_id": "local",
            "question_col": "question",
            "answer_col": "answer",
        },
    )

    assert response.status_code == 202
    split_index = spawned["args"].index("--split")
    assert spawned["args"][split_index + 1] == "train"


def test_import_rejects_secret_key():
    response = TestClient(create_app()).post(
        "/api/hf/datasets/import",
        json={"hf_id": "a/b", "HF_TOKEN": "nope"},
    )

    assert response.status_code == 400
    assert response.json()["ok"] is False


def test_download_rejects_secret_key():
    response = TestClient(create_app()).post(
        "/api/hf/models/download",
        json={
            "repo_id": "org/x",
            "filename": "a.gguf",
            "OPENROUTER_API_KEY": "nope",
        },
    )

    assert response.status_code == 400
    assert response.json()["ok"] is False


def test_current_job(monkeypatch):
    monkeypatch.setattr(
        "scripts.dashboard_api.read_job",
        lambda: {"id": "1", "status": "running"},
    )

    response = TestClient(create_app()).get("/api/hf/jobs/current")

    assert response.status_code == 200
    assert response.json() == {"id": "1", "status": "running"}


def test_current_job_idle(monkeypatch):
    monkeypatch.setattr("scripts.dashboard_api.read_job", lambda: None)

    response = TestClient(create_app()).get("/api/hf/jobs/current")

    assert response.status_code == 200
    assert response.json() == {"status": "idle"}
