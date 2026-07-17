from shared import hf_jobs as hj


def test_start_job_sets_running(tmp_path, monkeypatch):
    monkeypatch.setattr(hj, "JOBS_PATH", tmp_path / "hf_jobs.json")
    data = hj.start_job(kind="model_download", message="starting")
    assert data["status"] == "running"
    assert data["kind"] == "model_download"
    assert data["id"]
    assert hj.is_job_running() is True


def test_start_job_rejects_when_running(tmp_path, monkeypatch):
    monkeypatch.setattr(hj, "JOBS_PATH", tmp_path / "hf_jobs.json")
    hj.start_job(kind="model_download")
    try:
        hj.start_job(kind="dataset_import")
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "already" in str(exc).lower()


def test_finish_job_complete(tmp_path, monkeypatch):
    monkeypatch.setattr(hj, "JOBS_PATH", tmp_path / "hf_jobs.json")
    hj.start_job(kind="model_download")
    done = hj.finish_job(status="complete", message="ok", result={"path": "x"})
    assert done["status"] == "complete"
    assert done["result"]["path"] == "x"
    assert hj.is_job_running() is False
