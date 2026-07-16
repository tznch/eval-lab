import pytest


def test_load_settings_requires_glm_key_when_glm_judge(monkeypatch):
    monkeypatch.setenv("JUDGE_PROVIDER", "glm")
    monkeypatch.setenv("zai_api_key", "")
    from shared.config import load_settings

    with pytest.raises(ValueError, match="zai_api_key"):
        load_settings()


def test_load_settings_requires_openrouter_key_when_openrouter_judge(monkeypatch):
    monkeypatch.setenv("JUDGE_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    monkeypatch.setenv("zai_api_key", "dummy")
    from shared.config import load_settings

    with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
        load_settings()


def test_openrouter_is_default_judge(monkeypatch):
    monkeypatch.delenv("JUDGE_PROVIDER", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    from shared.config import load_settings

    settings = load_settings()
    assert settings.judge_provider == "openrouter"
    assert settings.judge_model == "tencent/hy3:free"


def test_judge_model_overrides_openrouter_model(monkeypatch):
    monkeypatch.setenv("JUDGE_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    monkeypatch.setenv("JUDGE_MODEL", "google/gemini-2.0-flash-exp:free")
    monkeypatch.setenv("OPENROUTER_MODEL", "tencent/hy3:free")
    from shared.config import load_settings

    settings = load_settings()
    assert settings.judge_model == "google/gemini-2.0-flash-exp:free"
    assert settings.openrouter_model == "google/gemini-2.0-flash-exp:free"


def test_judge_model_overrides_glm_model(monkeypatch):
    monkeypatch.setenv("JUDGE_PROVIDER", "glm")
    monkeypatch.setenv("zai_api_key", "test-key")
    monkeypatch.setenv("JUDGE_MODEL", "glm-5-turbo")
    monkeypatch.setenv("GLM_MODEL", "glm-5.2")
    from shared.config import load_settings

    settings = load_settings()
    assert settings.judge_model == "glm-5-turbo"
    assert settings.glm_model == "glm-5-turbo"
