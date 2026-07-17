"""Tests for model endpoint resolution."""

from shared.setup.model_endpoint import resolve_model_endpoint


def test_per_model_env_takes_priority_over_target_model():
    env = {
        "MODEL": "bonsai",
        "TARGET_MODEL_BASE_URL": "http://127.0.0.1:8080/v1",
        "TARGET_MODEL_NAME": "gemma-4-26b-a4b",
        "BONSAI_BASE_URL": "http://127.0.0.1:8081/v1",
        "BONSAI_MODEL_NAME": "bonsai-27b-q1",
    }
    base, name = resolve_model_endpoint("bonsai", env)
    assert base == "http://127.0.0.1:8081/v1"
    assert name == "bonsai-27b-q1"


def test_target_model_used_when_no_per_model_vars():
    env = {
        "MODEL": "custom",
        "TARGET_MODEL_BASE_URL": "http://127.0.0.1:9000/v1",
        "TARGET_MODEL_NAME": "my-model",
    }
    base, name = resolve_model_endpoint("custom", env)
    assert base == "http://127.0.0.1:9000/v1"
    assert name == "my-model"


def test_bundled_default_last_resort():
    base, name = resolve_model_endpoint("bonsai", {})
    assert base == "http://127.0.0.1:8081/v1"
    assert name == "bonsai-27b-q1"
