"""Tests for datasets/ registry and generic prepare."""

import json
from pathlib import Path

import pytest
import yaml

from shared.datasets.manifest import load_manifest
from shared.datasets.registry import discover_datasets, get_dataset, list_dataset_ids, samples_path
from shared.datasets.prepare import prepare_dataset


def test_discover_template_and_bitext_retail():
    manifests = discover_datasets()
    assert "bitext_retail" in manifests
    assert "_template" not in manifests
    assert "sciq" in manifests


def test_bitext_retail_manifest_mapping():
    m = get_dataset("bitext_retail")
    assert m is not None
    assert m.task_type == "intent"
    assert m.source.mapping["question"] == "instruction"
    assert m.eval.prompt == "intent"
    assert m.eval.portfolio is True


def test_samples_path_prefers_datasets_folder():
    path = samples_path("bitext_retail")
    assert path.name == "samples.jsonl"
    assert path.parent.name == "bitext_retail"


def test_bitext_retail_stratified_sampling():
    csv_src = Path("bitext-retail-ecommerce-llm-chatbot-training-dataset.csv")
    if not csv_src.exists():
        pytest.skip("CSV not in repo root")

    out = prepare_dataset("bitext_retail", limit=25)
    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 25
    intents = {json.loads(line)["ground_truth"] for line in lines}
    assert len(intents) >= 20


def test_prepare_bitext_retail_from_csv(tmp_path, monkeypatch):
    csv_src = Path("bitext-retail-ecommerce-llm-chatbot-training-dataset.csv")
    if not csv_src.exists():
        pytest.skip("CSV not in repo root")

    ds_dir = tmp_path / "datasets" / "test_retail"
    ds_dir.mkdir(parents=True)
    (ds_dir / "dataset.yaml").write_text(
        yaml.dump(
            {
                "id": "test_retail",
                "name": "Test",
                "task_type": "intent",
                "source": {
                    "type": "csv",
                    "path": str(csv_src.resolve()),
                    "mapping": {
                        "question": "instruction",
                        "ground_truth": "intent",
                        "category": "category",
                    },
                },
                "limits": {"default": 5},
            }
        ),
        encoding="utf-8",
    )

    import shared.datasets.registry as reg

    monkeypatch.setattr(reg, "DATASETS_ROOT", tmp_path / "datasets")
    reg.discover_datasets.cache_clear()

    out = prepare_dataset("test_retail", limit=5)
    assert out.exists()
    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 5
    assert '"task_type":"intent"' in lines[0]


def test_list_includes_legacy_ids():
    ids = list_dataset_ids()
    assert "sciq" in ids
    assert "feta" in ids
