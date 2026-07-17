"""Tests for universal model server launcher."""

from pathlib import Path

from shared.setup.model_server import (
    build_server_command,
    can_auto_start_server,
    port_from_base_url,
    resolve_model_weights_path,
)


def test_port_from_base_url():
    assert port_from_base_url("http://127.0.0.1:8081/v1") == 8081
    assert port_from_base_url("http://127.0.0.1/v1") == 80


def test_resolve_weights_from_per_model_env(tmp_path, monkeypatch):
    gguf = tmp_path / "custom.gguf"
    gguf.write_text("fake", encoding="utf-8")
    monkeypatch.setattr("shared.setup.model_server.ROOT", tmp_path)
    env = {"CUSTOM_BASE_MODEL_PATH": str(gguf)}
    # env key for "custom-base" -> CUSTOM_BASE_MODEL_PATH
    path = resolve_model_weights_path("custom-base", {"CUSTOM_BASE_MODEL_PATH": str(gguf)})
    assert path == gguf


def test_build_server_command_uses_weights_and_port(monkeypatch, tmp_path):
    binary = tmp_path / "llama-server"
    binary.write_text("#!/bin/sh\n", encoding="utf-8")
    binary.chmod(0o755)
    weights = tmp_path / "model.gguf"
    weights.write_text("fake", encoding="utf-8")

    env = {
        "LLAMA_SERVER": str(binary),
        "MYMODEL_MODEL_PATH": str(weights),
        "LLAMA_THREADS": "8",
    }
    cmd = build_server_command("mymodel", "http://127.0.0.1:9090/v1", env)
    assert cmd is not None
    assert str(binary) in cmd
    assert "-m" in cmd and str(weights) in cmd
    assert "9090" in cmd


def test_can_auto_start_with_registry_weights(monkeypatch, tmp_path):
    binary = tmp_path / "llama-server"
    binary.write_text("x", encoding="utf-8")
    weights = tmp_path / "w.gguf"
    weights.write_text("x", encoding="utf-8")
    monkeypatch.setattr(
        "shared.setup.model_server.model_weights_path",
        lambda _id: weights,
    )
    env = {"LLAMA_SERVER": str(binary)}
    assert can_auto_start_server("anything", env) is True
