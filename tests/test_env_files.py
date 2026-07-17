"""Tests for .env secret upsert helpers."""

from shared.env_files import mask_secret, save_managed_secrets, secret_status, upsert_env_file


def test_mask_secret():
    assert mask_secret(None) is None
    assert mask_secret("short") == "••••••••"
    assert mask_secret("sk-or-v1-abcdefghijklmnop") == "sk-o…mnop"


def test_upsert_env_file_sets_and_clears(tmp_path):
    path = tmp_path / ".env"
    path.write_text("FOO=1\nHF_TOKEN=old\nBAR=2\n", encoding="utf-8")
    upsert_env_file(path, {"HF_TOKEN": "newtoken", "OPENROUTER_API_KEY": "sk-or-x"})
    text = path.read_text(encoding="utf-8")
    assert "HF_TOKEN=newtoken" in text
    assert "OPENROUTER_API_KEY=sk-or-x" in text
    assert "FOO=1" in text
    assert "BAR=2" in text

    upsert_env_file(path, {"HF_TOKEN": ""})
    text = path.read_text(encoding="utf-8")
    assert "HF_TOKEN=" not in text
    assert "OPENROUTER_API_KEY=sk-or-x" in text


def test_save_managed_secrets_updates_process_env(tmp_path, monkeypatch):
    path = tmp_path / ".env"
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    status = save_managed_secrets(
        hf_token="hf_abcdefghij",
        openrouter_api_key="sk-or-abcdefghij",
        path=path,
    )
    assert status["hf_token"]["configured"] is True
    assert status["openrouter_api_key"]["configured"] is True
    assert "hf_a" in (status["hf_token"]["hint"] or "")
    text = path.read_text(encoding="utf-8")
    assert "HF_TOKEN=hf_abcdefghij" in text
    assert "OPENROUTER_API_KEY=" in text


def test_secret_status_never_returns_full_value():
    status = secret_status(
        {
            "HF_TOKEN": "hf_super_secret_token_value",
            "OPENROUTER_API_KEY": "sk-or-super-secret-key-value",
        }
    )
    blob = str(status)
    assert "super_secret" not in blob
    assert status["hf_token"]["configured"] is True
