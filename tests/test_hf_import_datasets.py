from shared.hf_import import datasets as d


def test_import_writes_yaml_and_raw(tmp_path, monkeypatch):
    monkeypatch.setattr(d, "ROOT", tmp_path)
    monkeypatch.setattr(d, "DATASETS_ROOT", tmp_path / "datasets")
    rows = [
        {"q": "Q1", "a": "A1", "c": "C1"},
        {"q": "Q2", "a": "A2", "c": "C2"},
    ]
    monkeypatch.setattr(d, "load_hf_rows", lambda **kw: rows)
    monkeypatch.setattr(
        d,
        "prepare_dataset",
        lambda dataset_id, limit=None: tmp_path / "datasets" / dataset_id / "samples.jsonl",
    )
    monkeypatch.setattr(d, "clear_dataset_cache", lambda: None)

    result = d.import_hf_dataset(
        hf_id="org/demo",
        split="train",
        local_id="demo",
        mapping={"question": "q", "ground_truth": "a", "context": "c"},
        limit=10,
    )

    assert result == {
        "dataset_id": "demo",
        "samples_path": str(tmp_path / "datasets" / "demo" / "samples.jsonl"),
        "rows": 2,
    }
    yaml_text = (tmp_path / "datasets" / "demo" / "dataset.yaml").read_text(encoding="utf-8")
    assert "id: demo" in yaml_text
    assert "question: q" in yaml_text
    raw = (tmp_path / "datasets" / "demo" / "raw" / "rows.jsonl").read_text(encoding="utf-8")
    assert "Q1" in raw


def test_import_fails_on_missing_columns(tmp_path, monkeypatch):
    monkeypatch.setattr(d, "ROOT", tmp_path)
    monkeypatch.setattr(d, "DATASETS_ROOT", tmp_path / "datasets")
    monkeypatch.setattr(d, "load_hf_rows", lambda **kw: [{"q": "only"}])

    try:
        d.import_hf_dataset(
            hf_id="org/demo",
            split="train",
            local_id="demo",
            mapping={"question": "q", "ground_truth": "missing"},
            limit=5,
        )
        assert False
    except ValueError as exc:
        assert "missing" in str(exc).lower() or "available" in str(exc).lower()
