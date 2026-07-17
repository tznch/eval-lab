import pytest

from scripts import run_hf_job as cli
from shared import hf_jobs


def _start_job(tmp_path, monkeypatch, *, kind):
    monkeypatch.setattr(hf_jobs, "JOBS_PATH", tmp_path / "hf_jobs.json")
    hf_jobs.start_job(kind=kind)


def test_model_download_runs_work_and_finishes_existing_job(tmp_path, monkeypatch):
    _start_job(tmp_path, monkeypatch, kind="model_download")
    calls = {}

    def fake_download(**kwargs):
        calls.update(kwargs)
        return {"path": "x", "model_id": "m"}

    monkeypatch.setattr(cli, "download_gguf", fake_download)

    result = cli.main(
        [
            "model-download",
            "--repo-id",
            "a/b",
            "--filename",
            "f.gguf",
            "--model-id",
            "m",
        ]
    )

    assert result == 0
    assert calls == {"repo_id": "a/b", "filename": "f.gguf", "model_id": "m"}
    assert hf_jobs.read_job()["status"] == "complete"
    assert hf_jobs.read_job()["result"] == {"path": "x", "model_id": "m"}


def test_dataset_import_maps_columns_and_finishes_existing_job(tmp_path, monkeypatch):
    _start_job(tmp_path, monkeypatch, kind="dataset_import")
    calls = {}

    def fake_import(**kwargs):
        calls.update(kwargs)
        return {"dataset_id": "local", "rows": 12}

    monkeypatch.setattr(cli, "import_hf_dataset", fake_import)

    result = cli.main(
        [
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
    )

    assert result == 0
    assert calls == {
        "hf_id": "org/data",
        "split": "validation",
        "local_id": "local",
        "mapping": {
            "question": "prompt",
            "ground_truth": "answer",
            "context": "passage",
        },
        "limit": 12,
    }
    assert hf_jobs.read_job()["status"] == "complete"
    assert hf_jobs.read_job()["result"] == {"dataset_id": "local", "rows": 12}


def test_failed_work_finishes_job_with_error(tmp_path, monkeypatch):
    _start_job(tmp_path, monkeypatch, kind="model_download")

    def fail_download(**kwargs):
        raise RuntimeError("download failed")

    monkeypatch.setattr(cli, "download_gguf", fail_download)

    with pytest.raises(SystemExit) as exc_info:
        cli.main(
            [
                "model-download",
                "--repo-id",
                "a/b",
                "--filename",
                "f.gguf",
            ]
        )

    assert exc_info.value.code == 1
    job = hf_jobs.read_job()
    assert job["status"] == "error"
    assert job["message"] == "download failed"
