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


def test_index_flat_destination_nav():
    """Shell exposes one flat row of destination links (no secondary tablist)."""
    client = TestClient(create_app())
    r = client.get("/")
    assert r.status_code == 200
    html = r.text
    assert 'aria-label="Secondary"' not in html
    assert "sub-tabs" not in html
    for label in (
        "Overview",
        "Report",
        "Performance",
        "DeepEval",
        "RAGAS",
        "Failures",
        "Promptfoo",
    ):
        assert label in html
    assert 'href="?view=overview"' in html or 'href="?view=overview"' in html
    assert 'href="?view=report"' in html
    assert 'href="?view=promptfoo"' in html
    assert 'aria-label="Views"' in html
    assert 'role="tablist"' not in html


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


def test_overview_uses_view_links_and_setup():
    client = TestClient(create_app())
    r = client.get("/partials/overview")
    assert r.status_code == 200
    html = r.text
    assert 'href="?view=promptfoo"' in html
    assert 'href="?view=deepeval"' in html
    assert 'href="?view=ragas"' in html
    assert 'href="?view=performance"' in html
    assert 'href="?view=report"' in html
    assert 'href="?view=failures"' in html
    assert "switch-tab" not in html
    assert "Setup" in html
    assert "Import profile YAML" in html


def test_promptfoo_partial_has_in_page_panels():
    client = TestClient(create_app())
    r = client.get("/partials/promptfoo")
    assert r.status_code == 200
    html = r.text
    assert "panel-seg" in html or 'aria-label="Promptfoo panels"' in html
    assert "Interactive UI" in html or "Summaries" in html
    assert "panel=summaries" in html
    assert "panel=ui" in html


def test_report_partial():
    client = TestClient(create_app())
    r = client.get("/partials/report")
    assert r.status_code == 200


def test_report_partial_has_run_cards():
    client = TestClient(create_app())
    r = client.get("/partials/report")
    assert r.status_code == 200
    html = r.text
    assert "No runs for current filters" in html or "run-card" in html
    if "run-card" in html:
        assert "Export profile YAML" in html
        assert '@click="exportRunProfile($event)"' in html
        assert 'x-data="{ fw:' in html or "x-data=\"{ fw:" in html
        assert 'run-card" x-data=' not in html
        assert "Promptfoo" in html and "DeepEval" in html and "RAGAS" in html


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
    assert "<iframe" not in r.text.lower()
    assert "output.json" in r.text or "No Promptfoo" in r.text
    assert 'panel-seg-btn active' in r.text
    assert 'panel=summaries' in r.text


def test_report_partial_ignores_legacy_panel_param():
    client = TestClient(create_app())
    r = client.get("/partials/report?panel=promptfoo")
    assert r.status_code == 200
    assert "tables" not in r.text
    assert 'aria-label="Report frameworks"' not in r.text


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
    monkeypatch.setattr(
        "scripts.dashboard_api.check_readiness",
        lambda **kwargs: {"can_run": False, "blocking": ["test"], "checks": {}},
    )
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
    assert "readiness" in body
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


def test_export_profile_returns_yaml(monkeypatch):
    monkeypatch.setenv("EVAL_DATASET", "sciq")
    monkeypatch.setenv("TARGET_TEMPERATURE", "0.7")
    monkeypatch.setenv("MODEL", "bonsai")
    monkeypatch.setenv("PROMPTFOO_LIMIT", "10")
    monkeypatch.setenv("DEEPEVAL_LIMIT", "5")
    monkeypatch.setenv("RAGAS_LIMIT", "5")
    client = TestClient(create_app())
    r = client.post("/api/profiles/export", json={"name": "ui-export"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["filename"] == "ui-export.yaml"
    assert "dataset: sciq" in body["yaml"]
    assert "id: bonsai" in body["yaml"]
    assert "OPENROUTER" not in body["yaml"]
    assert "HF_TOKEN" not in body["yaml"]


def test_export_profile_applies_filter_overrides(monkeypatch):
    monkeypatch.setenv("EVAL_DATASET", "sciq")
    monkeypatch.setenv("MODEL", "bonsai")
    client = TestClient(create_app())
    r = client.post(
        "/api/profiles/export",
        json={
            "name": "filtered",
            "dataset": "uda_qa",
            "temperature": 0.2,
            "models": ["bonsai"],
        },
    )
    assert r.status_code == 200
    yaml_text = r.json()["yaml"]
    assert "dataset: uda_qa" in yaml_text
    assert "temperature: 0.2" in yaml_text


def test_export_profile_rejects_secret_keys():
    client = TestClient(create_app())
    r = client.post(
        "/api/profiles/export",
        json={"name": "x", "HF_TOKEN": "nope"},
    )
    assert r.status_code == 400
    assert r.json()["ok"] is False


def test_overview_has_no_export_profile_button():
    client = TestClient(create_app())
    r = client.get("/partials/overview")
    assert r.status_code == 200
    assert "Export profile YAML" not in r.text
    assert "Import profile YAML" in r.text


def test_export_profile_single_run_overrides(monkeypatch):
    monkeypatch.setenv("EVAL_DATASET", "sciq")
    monkeypatch.setenv("MODEL", "qwen27")
    monkeypatch.setenv("TARGET_TEMPERATURE", "0.9")
    client = TestClient(create_app())
    r = client.post(
        "/api/profiles/export",
        json={"name": "bonsai-t0.7", "models": ["bonsai"], "temperature": 0.7},
    )
    assert r.status_code == 200
    yaml_text = r.json()["yaml"]
    assert "id: bonsai" in yaml_text
    assert "temperature: 0.7" in yaml_text
    assert "qwen27" not in yaml_text


def test_setup_options_json():
    client = TestClient(create_app())
    r = client.get("/api/setup/options")
    assert r.status_code == 200
    data = r.json()
    assert "datasets" in data
    assert "dataset_catalog" in data
    assert isinstance(data["dataset_catalog"], list)
    assert data["frameworks"] == ["promptfoo", "deepeval", "ragas"]
    # Only folders with dataset.yaml — not legacy-only ids like paper_text
    assert "paper_text" not in data["datasets"]
    assert "feta" not in data["datasets"]
    if data["dataset_catalog"]:
        row = data["dataset_catalog"][0]
        assert {"id", "name", "description"} <= set(row)
        assert data["datasets"] == [d["id"] for d in data["dataset_catalog"]]


def test_setup_readiness_json(monkeypatch):
    monkeypatch.setattr(
        "scripts.dashboard_api.check_readiness",
        lambda **kwargs: {
            "ok": False,
            "can_run": False,
            "blocking": ["missing samples"],
            "checks": {"dataset_samples": {"ok": False, "message": "missing"}},
        },
    )
    client = TestClient(create_app())
    r = client.get("/api/setup/readiness?model=bonsai&dataset=sciq&frameworks=promptfoo")
    assert r.status_code == 200
    data = r.json()
    assert data["can_run"] is False
    assert "checks" in data


def test_evals_run_rejects_secrets():
    client = TestClient(create_app())
    r = client.post(
        "/api/evals/run",
        json={
            "model_id": "bonsai",
            "dataset_ids": ["sciq"],
            "temperature": 0.7,
            "frameworks": ["promptfoo"],
            "OPENROUTER_API_KEY": "nope",
        },
    )
    assert r.status_code == 400
    assert r.json()["ok"] is False


def test_evals_run_rejects_no_frameworks(monkeypatch):
    monkeypatch.setattr(
        "scripts.dashboard_api.check_readiness",
        lambda **kwargs: {"can_run": True, "blocking": []},
    )
    client = TestClient(create_app())
    r = client.post(
        "/api/evals/run",
        json={
            "model_id": "bonsai",
            "dataset_ids": ["sciq"],
            "temperature": 0.7,
            "frameworks": [],
        },
    )
    assert r.status_code == 400


def test_evals_run_rejects_no_datasets(monkeypatch):
    monkeypatch.setattr(
        "scripts.dashboard_api.check_readiness",
        lambda **kwargs: {"can_run": True, "blocking": []},
    )
    client = TestClient(create_app())
    r = client.post(
        "/api/evals/run",
        json={
            "model_id": "bonsai",
            "dataset_ids": [],
            "temperature": 0.7,
            "frameworks": ["promptfoo"],
        },
    )
    assert r.status_code == 400


def test_evals_run_rejects_not_ready(monkeypatch):
    monkeypatch.setattr(
        "scripts.dashboard_api.check_readiness",
        lambda **kwargs: {
            "can_run": False,
            "blocking": ["Missing samples"],
        },
    )
    client = TestClient(create_app())
    r = client.post(
        "/api/evals/run",
        json={
            "model_id": "bonsai",
            "dataset_ids": ["sciq"],
            "temperature": 0.7,
            "frameworks": ["promptfoo"],
        },
    )
    assert r.status_code == 400
    assert "blocking" in r.json()


def test_evals_run_rejects_when_already_running(monkeypatch):
    monkeypatch.setattr(
        "scripts.dashboard_api.check_readiness",
        lambda **kwargs: {"can_run": True, "blocking": []},
    )
    monkeypatch.setattr(
        "scripts.dashboard_api.read_status",
        lambda: {"status": "running"},
    )
    client = TestClient(create_app())
    r = client.post(
        "/api/evals/run",
        json={
            "model_id": "bonsai",
            "dataset_ids": ["sciq"],
            "temperature": 0.7,
            "frameworks": ["promptfoo"],
        },
    )
    assert r.status_code == 409


def test_evals_run_starts_subprocess(monkeypatch):
    monkeypatch.setattr(
        "scripts.dashboard_api.check_readiness",
        lambda **kwargs: {"can_run": True, "blocking": []},
    )
    monkeypatch.setattr("scripts.dashboard_api.read_status", lambda: {"status": "idle"})
    spawned = {}

    class FakePopen:
        def __init__(self, args, **kwargs):
            spawned["args"] = args
            self.pid = 4242

    monkeypatch.setattr("scripts.dashboard_api.subprocess.Popen", FakePopen)
    client = TestClient(create_app())
    r = client.post(
        "/api/evals/run",
        json={
            "model_id": "bonsai",
            "dataset_ids": ["sciq", "nq"],
            "temperature": 0.7,
            "frameworks": ["promptfoo", "ragas"],
        },
    )
    assert r.status_code == 202
    assert r.json()["ok"] is True
    assert "run_dashboard_eval.py" in spawned["args"][1]
    assert spawned["args"].count("--dataset-id") == 2
    assert "sciq" in spawned["args"] and "nq" in spawned["args"]


def test_evals_run_accepts_legacy_dataset_id(monkeypatch):
    monkeypatch.setattr(
        "scripts.dashboard_api.check_readiness",
        lambda **kwargs: {"can_run": True, "blocking": []},
    )
    monkeypatch.setattr("scripts.dashboard_api.read_status", lambda: {"status": "idle"})

    class FakePopen:
        def __init__(self, args, **kwargs):
            self.pid = 1

    monkeypatch.setattr("scripts.dashboard_api.subprocess.Popen", FakePopen)
    client = TestClient(create_app())
    r = client.post(
        "/api/evals/run",
        json={
            "model_id": "bonsai",
            "dataset_id": "sciq",
            "temperature": 0.7,
            "frameworks": ["promptfoo"],
        },
    )
    assert r.status_code == 202


def test_setup_readiness_multi_datasets(monkeypatch):
    seen = {}

    def fake_check(**kwargs):
        seen.update(kwargs)
        return {
            "ok": True,
            "can_run": True,
            "blocking": [],
            "dataset_ids": kwargs.get("dataset_ids"),
            "checks": {},
        }

    monkeypatch.setattr("scripts.dashboard_api.check_readiness", fake_check)
    client = TestClient(create_app())
    r = client.get(
        "/api/setup/readiness?model=bonsai&datasets=sciq,nq&frameworks=promptfoo"
    )
    assert r.status_code == 200
    assert seen["dataset_ids"] == ["sciq", "nq"]


def test_overview_has_dataset_pills_when_profile_exists(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "shared.setup.readiness.has_env_profile",
        lambda: True,
    )
    monkeypatch.setattr(
        "scripts.dashboard_api.setup_options",
        lambda: {
            "has_profile": True,
            "datasets": ["sciq", "nq"],
            "dataset_catalog": [
                {"id": "sciq", "name": "SciQ", "topic": "Science", "description": "Science QA"},
                {"id": "nq", "name": "NQ", "topic": "QA", "description": "Natural Questions"},
            ],
            "temperatures": [0.7],
            "frameworks": ["promptfoo"],
            "models": ["bonsai"],
            "default_dataset": "sciq",
            "default_datasets": ["sciq"],
            "default_temperature": 0.7,
            "default_model": "bonsai",
            "limits": {},
        },
    )
    client = TestClient(create_app())
    r = client.get("/partials/overview")
    assert r.status_code == 200
    assert "Datasets" in r.text
    assert "toggleSetupDataset" in r.text
    assert "dataset-checklist" in r.text
    assert 'type="checkbox"' in r.text
    assert 'id="setup-dataset"' not in r.text


def test_evals_stop_calls_stop_run(monkeypatch):
    monkeypatch.setattr(
        "scripts.dashboard_api.stop_run",
        lambda: {"ok": True, "message": "Eval stopped", "status": {"status": "cancelled"}},
    )
    client = TestClient(create_app())
    r = client.post("/api/evals/stop")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_evals_stop_when_idle(monkeypatch):
    monkeypatch.setattr(
        "scripts.dashboard_api.stop_run",
        lambda: {"ok": False, "message": "No eval is running", "status": {"status": "idle"}},
    )
    client = TestClient(create_app())
    r = client.post("/api/evals/stop")
    assert r.status_code == 409


def test_progress_partial_shows_stop_when_running(monkeypatch):
    monkeypatch.setattr(
        "scripts.dashboard_api.read_status",
        lambda: {
            "status": "running",
            "model": "bonsai",
            "temp_tag": "t0.7",
            "step": 1,
            "total_steps": 3,
            "completed": [],
            "current": {"track": "sciq", "framework": "promptfoo"},
        },
    )
    client = TestClient(create_app())
    r = client.get("/partials/progress")
    assert r.status_code == 200
    assert "Stop eval" in r.text
    assert '@click="stopEval()"' in r.text



def test_overview_has_run_eval_when_profile_exists(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "shared.setup.readiness.has_env_profile",
        lambda: True,
    )
    monkeypatch.setattr(
        "scripts.dashboard_api.setup_options",
        lambda: {
            "has_profile": True,
            "datasets": ["sciq"],
            "temperatures": [0.7],
            "frameworks": ["promptfoo"],
            "models": ["bonsai"],
            "default_dataset": "sciq",
            "default_temperature": 0.7,
            "default_model": "bonsai",
            "limits": {},
        },
    )
    client = TestClient(create_app())
    r = client.get("/partials/overview")
    assert r.status_code == 200
    assert "Run eval" in r.text
    assert "run-eval-card" in r.text
