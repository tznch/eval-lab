"""Tests for setup readiness checks."""

from pathlib import Path

import pytest

from shared.setup.readiness import check_readiness


def test_dataset_missing_samples_fails(tmp_path, monkeypatch):
    root = tmp_path
    monkeypatch.setattr("shared.datasets.registry.ROOT", root)
    monkeypatch.setattr("shared.datasets.registry.DATASETS_ROOT", root / "datasets")
    monkeypatch.setattr("shared.setup.readiness.samples_path", lambda _id: root / "missing.jsonl")

    result = check_readiness(
        model_id="custom",
        dataset_id="sciq",
        frameworks=["promptfoo"],
        env={
            "TARGET_MODEL_BASE_URL": "http://127.0.0.1:8080/v1",
            "TARGET_MODEL_NAME": "local",
        },
    )
    assert result["checks"]["dataset_samples"]["ok"] is False
    assert result["can_run"] is False
    assert result["blocking"]


def test_judge_not_required_for_promptfoo_only(monkeypatch):
    monkeypatch.setattr(
        "shared.setup.readiness.samples_path",
        lambda _id: Path("/tmp/fake-samples.jsonl"),
    )
    monkeypatch.setattr("pathlib.Path.is_file", lambda self: self.name == "fake-samples.jsonl")

    result = check_readiness(
        model_id="custom",
        dataset_id="sciq",
        frameworks=["promptfoo"],
        env={
            "TARGET_MODEL_BASE_URL": "http://127.0.0.1:8080/v1",
            "TARGET_MODEL_NAME": "local",
            "JUDGE_PROVIDER": "openrouter",
        },
    )
    assert result["checks"]["judge"]["ok"] is True
    assert "not required" in result["checks"]["judge"]["message"].lower()


def test_judge_required_when_deepeval_selected(monkeypatch):
    monkeypatch.setattr(
        "shared.setup.readiness.samples_path",
        lambda _id: Path("/tmp/fake-samples.jsonl"),
    )
    monkeypatch.setattr("pathlib.Path.is_file", lambda self: self.name == "fake-samples.jsonl")

    result = check_readiness(
        model_id="custom",
        dataset_id="sciq",
        frameworks=["deepeval"],
        env={
            "TARGET_MODEL_BASE_URL": "http://127.0.0.1:8080/v1",
            "TARGET_MODEL_NAME": "local",
            "JUDGE_PROVIDER": "openrouter",
        },
    )
    assert result["checks"]["judge"]["ok"] is False


def test_unknown_model_without_endpoint_fails(monkeypatch):
    monkeypatch.setattr(
        "shared.setup.readiness.samples_path",
        lambda _id: Path("/tmp/fake-samples.jsonl"),
    )
    monkeypatch.setattr("pathlib.Path.is_file", lambda self: self.name == "fake-samples.jsonl")

    result = check_readiness(
        model_id="unknown-model",
        dataset_id="sciq",
        frameworks=["promptfoo"],
        env={},
    )
    assert result["checks"]["model_configured"]["ok"] is False
    assert "TARGET_MODEL_BASE_URL" in result["checks"]["model_configured"]["message"]


def test_multi_dataset_missing_samples_lists_all(monkeypatch):
    monkeypatch.setattr(
        "shared.setup.readiness.samples_path",
        lambda ds: Path(f"/tmp/{ds}-samples.jsonl"),
    )
    monkeypatch.setattr("pathlib.Path.is_file", lambda self: False)
    monkeypatch.setattr("shared.setup.readiness.get_dataset", lambda _id: object())

    result = check_readiness(
        model_id="custom",
        dataset_ids=["sciq", "nq"],
        frameworks=["promptfoo"],
        env={
            "TARGET_MODEL_BASE_URL": "http://127.0.0.1:8080/v1",
            "TARGET_MODEL_NAME": "local",
        },
    )
    assert result["checks"]["dataset_samples"]["ok"] is False
    assert "sciq" in result["checks"]["dataset_samples"]["message"]
    assert "nq" in result["checks"]["dataset_samples"]["message"]
    assert result["dataset_ids"] == ["sciq", "nq"]


def test_list_setup_datasets_from_folder_only(tmp_path, monkeypatch):
    from shared.setup.readiness import list_setup_datasets
    import shared.datasets.registry as reg

    ds_root = tmp_path / "datasets"
    (ds_root / "alpha").mkdir(parents=True)
    (ds_root / "alpha" / "dataset.yaml").write_text(
        "id: alpha\nname: Alpha Track\ndescription: First dataset\n",
        encoding="utf-8",
    )
    (ds_root / "_template").mkdir()
    (ds_root / "_template" / "dataset.yaml").write_text("id: template\n", encoding="utf-8")

    monkeypatch.setattr(reg, "DATASETS_ROOT", ds_root)
    reg.discover_datasets.cache_clear()

    catalog = list_setup_datasets()
    assert [d["id"] for d in catalog] == ["alpha"]
    assert catalog[0]["name"] == "Alpha Track"
    assert "paper_text" not in [d["id"] for d in catalog]
