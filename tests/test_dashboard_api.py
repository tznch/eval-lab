"""Tests for dashboard API routes."""

from pathlib import Path

from fastapi.testclient import TestClient

from scripts.dashboard_api import create_app


def test_progress_partial_idle():
    client = TestClient(create_app())
    r = client.get("/partials/progress")
    assert r.status_code == 200
    assert "progress" in r.text.lower() or "idle" in r.text.lower()


def test_run_status_json():
    client = TestClient(create_app())
    r = client.get("/api/run-status")
    assert r.status_code == 200
    assert "status" in r.json()


def test_index():
    client = TestClient(create_app())
    r = client.get("/")
    assert r.status_code == 200


def test_catalog_json():
    client = TestClient(create_app())
    r = client.get("/api/catalog")
    assert r.status_code == 200
    data = r.json()
    assert "models" in data
    assert "frameworks" in data


def test_overview_partial():
    client = TestClient(create_app())
    r = client.get("/partials/overview")
    assert r.status_code == 200
    assert "Framework runs" in r.text or "Eval progress" in r.text


def test_report_partial():
    client = TestClient(create_app())
    r = client.get("/partials/report")
    assert r.status_code == 200


def test_deepeval_partial():
    client = TestClient(create_app())
    r = client.get("/partials/deepeval")
    assert r.status_code == 200
    assert "run-group" in r.text or "No DeepEval" in r.text


def test_deepeval_partial_filtered():
    client = TestClient(create_app())
    r = client.get("/partials/deepeval?models=bonsai&temps=t0.7")
    assert r.status_code == 200


def test_promptfoo_partial():
    client = TestClient(create_app())
    r = client.get("/partials/promptfoo")
    assert r.status_code == 200


def test_ragas_partial():
    client = TestClient(create_app())
    r = client.get("/partials/ragas")
    assert r.status_code == 200


def test_performance_partial():
    client = TestClient(create_app())
    r = client.get("/partials/performance")
    assert r.status_code == 200


def test_failures_partial():
    client = TestClient(create_app())
    r = client.get("/partials/failures")
    assert r.status_code == 200


def test_promptfoo_panel_summaries():
    client = TestClient(create_app())
    r = client.get("/partials/promptfoo?panel=summaries")
    assert r.status_code == 200
    assert "Interactive UI" not in r.text
    assert "<iframe" not in r.text.lower()
    assert "output.json" in r.text or "No Promptfoo" in r.text


def test_report_panel():
    client = TestClient(create_app())
    r = client.get("/partials/report?panel=promptfoo")
    assert r.status_code == 200


def test_performance_panel():
    client = TestClient(create_app())
    r = client.get("/partials/performance?panel=rollup")
    assert r.status_code == 200


def test_deepeval_uses_accordion():
    client = TestClient(create_app())
    r = client.get("/partials/deepeval")
    assert r.status_code == 200
    assert "details" in r.text or "No DeepEval" in r.text


def test_download_rejects_token_in_body():
    client = TestClient(create_app())
    r = client.post(
        "/api/models/download",
        json={
            "profile": "profiles/examples/bonsai-sciq-t07.yaml",
            "model_id": "bonsai",
            "HF_TOKEN": "hf_should_reject",
        },
    )
    assert r.status_code == 400
    assert r.json()["ok"] is False


def test_download_rejects_nested_token_in_body():
    client = TestClient(create_app())
    r = client.post(
        "/api/models/download",
        json={
            "profile": "profiles/examples/does-not-exist.yaml",
            "options": {"HF_TOKEN": "hf_should_reject"},
        },
    )
    assert r.status_code == 400
    assert r.json()["ok"] is False


def test_download_missing_profile():
    client = TestClient(create_app())
    r = client.post(
        "/api/models/download",
        json={
            "profile": "profiles/examples/does-not-exist.yaml",
            "model_id": "bonsai",
        },
    )
    assert r.status_code in (400, 404)
    assert r.json()["ok"] is False


def test_download_rejects_non_string_profile():
    client = TestClient(create_app())
    r = client.post(
        "/api/models/download",
        json={"profile": {}, "model_id": "bonsai"},
    )
    assert r.status_code == 400
    assert r.json()["ok"] is False
    assert "profile" in r.json()["message"].lower()


def test_download_rejects_non_string_model_id():
    client = TestClient(create_app())
    r = client.post(
        "/api/models/download",
        json={
            "profile": "profiles/examples/bonsai-sciq-t07.yaml",
            "model_id": ["bonsai"],
        },
    )
    assert r.status_code == 400
    assert r.json()["ok"] is False
    assert "model_id" in r.json()["message"].lower()


def test_download_rejects_profile_path_outside_root():
    client = TestClient(create_app())
    r = client.post(
        "/api/models/download",
        json={"profile": "/etc/passwd", "model_id": "bonsai"},
    )
    assert r.status_code in (400, 404)
    assert r.json()["ok"] is False


def test_download_calls_dispatcher(monkeypatch):
    called = {}

    def fake_download(profile, model_id=None):
        called["id"] = model_id or profile.models[0].id
        return Path("/tmp/fake.gguf")

    monkeypatch.setattr(
        "scripts.dashboard_api.download_profile_model", fake_download
    )
    client = TestClient(create_app())
    r = client.post(
        "/api/models/download",
        json={
            "profile": "profiles/examples/bonsai-sciq-t07.yaml",
            "model_id": "bonsai",
        },
    )
    assert r.status_code == 200
    assert r.json() == {
        "ok": True,
        "message": "Download complete",
        "path": "/tmp/fake.gguf",
    }
    assert called["id"] == "bonsai"


def test_import_profile_writes_env_profile(tmp_path, monkeypatch):
    env_path = tmp_path / ".env.profile"
    monkeypatch.setattr("scripts.dashboard_api.ROOT", tmp_path)
    client = TestClient(create_app())
    yaml_text = """
name: ui-import
dataset: sciq
temperature: 0.7
models:
  - id: bonsai
limits:
  promptfoo: 10
  deepeval: 5
  ragas: 5
"""
    r = client.post("/api/profiles/import", json={"yaml": yaml_text})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["dataset"] == "sciq"
    assert env_path.is_file()
    text = env_path.read_text()
    assert "EVAL_DATASET=sciq" in text
    assert "OPENROUTER" not in text


def test_import_profile_rejects_secret_keys():
    client = TestClient(create_app())
    r = client.post(
        "/api/profiles/import",
        json={
            "yaml": "name: x\ndataset: sciq\nmodels:\n  - id: bonsai\n",
            "HF_TOKEN": "nope",
        },
    )
    assert r.status_code == 400
    assert r.json()["ok"] is False


def test_import_profile_rejects_invalid_yaml():
    client = TestClient(create_app())
    r = client.post("/api/profiles/import", json={"yaml": "- just a list\n"})
    assert r.status_code == 400
    assert r.json()["ok"] is False
