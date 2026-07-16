from __future__ import annotations

import warnings
from dataclasses import dataclass, field

SECRET_KEYS = frozenset(
    {
        "OPENROUTER_API_KEY",
        "zai_api_key",
        "HF_TOKEN",
        "HF_FULL_ACCESS",
        "HUGGING_FACE_HUB_TOKEN",
    }
)

KNOWN_TOP_LEVEL_KEYS = frozenset(
    {
        "name",
        "dataset",
        "temperature",
        "models",
        "limits",
        "judge_model",
    }
)


@dataclass
class ProfileModelSpec:
    id: str
    hf_repo: str | None = None
    quant: str | None = None
    gguf_hint: str | None = None


@dataclass
class ProfileLimits:
    promptfoo: int = 25
    deepeval: int = 25
    ragas: int = 25


@dataclass
class RunProfile:
    name: str
    dataset: str
    models: list[ProfileModelSpec]
    limits: ProfileLimits = field(default_factory=ProfileLimits)
    temperature: float = 0.7
    judge_model: str | None = None


def _find_secret_keys(data: object) -> list[str]:
    found: list[str] = []
    if isinstance(data, dict):
        for key, value in data.items():
            if key in SECRET_KEYS:
                found.append(key)
            found.extend(_find_secret_keys(value))
    elif isinstance(data, list):
        for item in data:
            found.extend(_find_secret_keys(item))
    return found


def _parse_model_spec(raw: object) -> ProfileModelSpec:
    if not isinstance(raw, dict):
        raise ValueError("each model must be a mapping")
    if "id" not in raw or not raw["id"]:
        raise ValueError("each model requires id")
    return ProfileModelSpec(
        id=str(raw["id"]),
        hf_repo=raw.get("hf_repo"),
        quant=raw.get("quant"),
        gguf_hint=raw.get("gguf_hint"),
    )


def _parse_limits(raw: object) -> ProfileLimits:
    if raw is None:
        return ProfileLimits()
    if not isinstance(raw, dict):
        raise ValueError("limits must be a mapping")
    return ProfileLimits(
        promptfoo=int(raw.get("promptfoo", 25)),
        deepeval=int(raw.get("deepeval", 25)),
        ragas=int(raw.get("ragas", 25)),
    )


def profile_from_dict(data: dict) -> RunProfile:
    if not isinstance(data, dict):
        raise ValueError("profile must be a mapping")

    secret_hits = _find_secret_keys(data)
    if secret_hits:
        raise ValueError(f"profile contains secret key(s): {', '.join(secret_hits)}")

    for key in data:
        if key not in KNOWN_TOP_LEVEL_KEYS:
            warnings.warn(f"unknown profile field ignored: {key}", stacklevel=2)

    if "name" not in data or not data["name"]:
        raise ValueError("profile requires name")
    if "dataset" not in data or not data["dataset"]:
        raise ValueError("profile requires dataset")

    models_raw = data.get("models")
    if not models_raw:
        raise ValueError("profile requires at least one model")
    if not isinstance(models_raw, list):
        raise ValueError("models must be a list")

    models = [_parse_model_spec(m) for m in models_raw]

    return RunProfile(
        name=str(data["name"]),
        dataset=str(data["dataset"]),
        temperature=float(data.get("temperature", 0.7)),
        models=models,
        limits=_parse_limits(data.get("limits")),
        judge_model=data.get("judge_model"),
    )
