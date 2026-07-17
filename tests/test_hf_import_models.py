import os

from shared.hf_import import models as m


def test_list_gguf_files_filters_and_sorts(monkeypatch):
    calls = {}
    monkeypatch.setattr(m, "get_hf_token", lambda: "tok")

    def fake_list(repo_id, token=None):
        calls.update(repo_id=repo_id, token=token)
        return ["b/Q4.GGUF", "README.md", "a.gguf"]

    monkeypatch.setattr(m, "list_repo_files", fake_list)

    assert m.list_gguf_files("org/x") == ["a.gguf", "b/Q4.GGUF"]
    assert calls == {"repo_id": "org/x", "token": "tok"}


def test_download_gguf_writes_env(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "ROOT", tmp_path)
    monkeypatch.setattr(m, "ENV_PATH", tmp_path / ".env")
    monkeypatch.setattr(m, "get_hf_token", lambda: "tok")
    monkeypatch.setattr(m, "find_free_port", lambda: 8085)
    out = tmp_path / "data" / "models" / "my-model" / "file.gguf"
    download_kwargs = {}

    def fake_dl(**kwargs):
        download_kwargs.update(kwargs)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"gguf")
        return str(out)

    monkeypatch.setattr(m, "hf_hub_download", fake_dl)

    result = m.download_gguf(
        repo_id="org/x",
        filename="file.gguf",
        model_id="My Model",
    )

    assert download_kwargs == {
        "repo_id": "org/x",
        "filename": "file.gguf",
        "local_dir": out.parent,
        "token": "tok",
    }
    assert result == {
        "model_id": "my-model",
        "path": str(out),
        "base_url": "http://127.0.0.1:8085/v1",
        "model_name": "file",
        "port": 8085,
    }
    text = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "MY_MODEL_BASE_URL=http://127.0.0.1:8085/v1" in text
    assert f"MY_MODEL_MODEL_PATH={out}" in text
    assert "MY_MODEL_MODEL_NAME=file" in text
    assert os.environ["MY_MODEL_BASE_URL"] == result["base_url"]
    assert os.environ["MY_MODEL_MODEL_PATH"] == result["path"]
    assert os.environ["MY_MODEL_MODEL_NAME"] == result["model_name"]


def test_download_gguf_defaults_model_id_from_repo(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "ROOT", tmp_path)
    monkeypatch.setattr(m, "ENV_PATH", tmp_path / ".env")
    monkeypatch.setattr(m, "get_hf_token", lambda: None)
    monkeypatch.setattr(m, "find_free_port", lambda: 8080)
    out = tmp_path / "data" / "models" / "my-model-gguf" / "nested" / "Q4.gguf"

    def fake_dl(**kwargs):
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"gguf")
        return str(out)

    monkeypatch.setattr(m, "hf_hub_download", fake_dl)

    result = m.download_gguf(
        repo_id="org/My-Model-GGUF",
        filename="nested/Q4.gguf",
    )

    assert result["model_id"] == "my-model-gguf"
    assert result["model_name"] == "Q4"
