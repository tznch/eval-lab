import warnings
from pathlib import Path

import pytest

from shared.profiles.download import download_profile_model
from shared.profiles.io import (
    export_profile_from_env,
    load_profile,
    save_profile,
    write_env_profile,
)
from shared.profiles.schema import profile_from_dict


def test_profile_from_dict_minimal():
    p = profile_from_dict(
        {
            "name": "demo",
            "dataset": "sciq",
            "models": [{"id": "bonsai"}],
        }
    )
    assert p.name == "demo"
    assert p.dataset == "sciq"
    assert p.models[0].id == "bonsai"
    assert p.temperature == 0.7
    assert p.limits.promptfoo == 25


def test_profile_rejects_secret_keys():
    with pytest.raises(ValueError, match="secret"):
        profile_from_dict(
            {
                "name": "bad",
                "dataset": "sciq",
                "models": [{"id": "bonsai"}],
                "HF_TOKEN": "hf_xxx",
            }
        )


def test_profile_rejects_nested_secret_keys():
    with pytest.raises(ValueError, match="secret"):
        profile_from_dict(
            {
                "name": "bad",
                "dataset": "sciq",
                "models": [{"id": "bonsai", "HF_TOKEN": "hf_xxx"}],
            }
        )


def test_profile_requires_name_dataset_model():
    with pytest.raises(ValueError):
        profile_from_dict({"dataset": "sciq", "models": [{"id": "bonsai"}]})
    with pytest.raises(ValueError):
        profile_from_dict({"name": "x", "models": [{"id": "bonsai"}]})
    with pytest.raises(ValueError):
        profile_from_dict({"name": "x", "dataset": "sciq", "models": []})


def test_profile_warns_on_unknown_fields():
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        profile_from_dict(
            {
                "name": "demo",
                "dataset": "sciq",
                "models": [{"id": "bonsai"}],
                "extra_thing": 1,
            }
        )
    assert any("extra_thing" in str(x.message) for x in w)


def test_roundtrip_yaml(tmp_path: Path):
    p = profile_from_dict(
        {
            "name": "demo",
            "dataset": "sciq",
            "temperature": 0.7,
            "models": [
                {
                    "id": "bonsai",
                    "hf_repo": "prism-ml/Bonsai-27B-gguf",
                    "quant": "Q1_0",
                }
            ],
            "limits": {"promptfoo": 10, "deepeval": 5, "ragas": 5},
        }
    )
    path = tmp_path / "p.yaml"
    save_profile(path, p)
    loaded = load_profile(path)
    assert loaded.name == "demo"
    assert loaded.limits.promptfoo == 10


def test_write_env_profile_rejects_newline_injection(tmp_path: Path):
    p = profile_from_dict(
        {
            "name": "bad",
            "dataset": "sciq\nHF_TOKEN=secret",
            "models": [{"id": "bonsai"}],
        }
    )
    out = tmp_path / ".env.profile"
    with pytest.raises(ValueError, match="newline"):
        write_env_profile(p, out)


def test_write_env_profile_rejects_newline_in_judge_model(tmp_path: Path):
    p = profile_from_dict(
        {
            "name": "bad",
            "dataset": "sciq",
            "models": [{"id": "bonsai"}],
            "judge_model": "model\nHF_TOKEN=secret",
        }
    )
    out = tmp_path / ".env.profile"
    with pytest.raises(ValueError, match="newline"):
        write_env_profile(p, out)


def test_write_env_profile_quotes_special_characters(tmp_path: Path):
    p = profile_from_dict(
        {
            "name": "demo",
            "dataset": "data set",
            "models": [{"id": "bonsai"}],
            "judge_model": "vendor/model#free",
        }
    )
    out = tmp_path / ".env.profile"
    write_env_profile(p, out)
    text = out.read_text()
    assert 'EVAL_DATASET="data set"' in text
    assert 'JUDGE_MODEL="vendor/model#free"' in text


def test_write_env_profile_omits_secrets(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-secret")
    p = profile_from_dict(
        {
            "name": "demo",
            "dataset": "sciq",
            "models": [{"id": "bonsai"}],
            "judge_model": "tencent/hy3:free",
        }
    )
    out = tmp_path / ".env.profile"
    write_env_profile(p, out)
    text = out.read_text()
    assert "OPENROUTER" not in text
    assert "EVAL_DATASET=sciq" in text
    assert "JUDGE_MODEL=tencent/hy3:free" in text


def test_export_profile_from_env(monkeypatch):
    monkeypatch.setenv("EVAL_DATASET", "sciq")
    monkeypatch.setenv("TARGET_TEMPERATURE", "0.7")
    monkeypatch.setenv("MODEL", "bonsai")
    monkeypatch.setenv("PROMPTFOO_LIMIT", "30")
    p = export_profile_from_env("bonsai-sciq-t07")
    assert p.dataset == "sciq"
    assert p.temperature == 0.7
    assert p.models[0].id == "bonsai"
    assert p.models[0].hf_repo
    assert p.limits.promptfoo == 30


def test_download_unknown_model_lists_supported():
    p = profile_from_dict(
        {"name": "demo", "dataset": "sciq", "models": [{"id": "nope"}]}
    )
    with pytest.raises(ValueError, match="bonsai"):
        download_profile_model(p, "nope")
