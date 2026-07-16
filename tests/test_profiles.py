import warnings

import pytest

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
