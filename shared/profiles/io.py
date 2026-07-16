from dataclasses import asdict
import os
from pathlib import Path

import yaml

from shared.profiles.registry import MODEL_REGISTRY
from shared.profiles.schema import RunProfile, profile_from_dict


def load_profile(path: Path) -> RunProfile:
    with path.open(encoding="utf-8") as profile_file:
        data = yaml.safe_load(profile_file)
    return profile_from_dict(data)


def load_profile_yaml(text: str) -> RunProfile:
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError("profile YAML must be a mapping/object")
    return profile_from_dict(data)


def save_profile(path: Path, profile: RunProfile) -> None:
    with path.open("w", encoding="utf-8") as profile_file:
        yaml.safe_dump(asdict(profile), profile_file, sort_keys=False)


def _model_ids_from_env() -> list[str]:
    value = os.getenv("MODEL") or os.getenv("MODELS") or "bonsai"
    return [model_id.strip() for model_id in value.split(",") if model_id.strip()]


def export_profile_from_env(name: str) -> RunProfile:
    models = []
    for model_id in _model_ids_from_env():
        models.append({"id": model_id, **MODEL_REGISTRY.get(model_id, {})})

    data = {
        "name": name,
        "dataset": os.getenv("EVAL_DATASET", "uda_qa"),
        "temperature": float(os.getenv("TARGET_TEMPERATURE", "0.7")),
        "models": models,
        "limits": {
            "promptfoo": int(os.getenv("PROMPTFOO_LIMIT", "25")),
            "deepeval": int(os.getenv("DEEPEVAL_LIMIT", "25")),
            "ragas": int(os.getenv("RAGAS_LIMIT", "25")),
        },
        "judge_model": os.getenv("JUDGE_MODEL") or None,
    }
    return profile_from_dict(data)


def _validate_env_value(key: str, value: str) -> None:
    if "\r" in value or "\n" in value:
        raise ValueError(f"{key} must not contain newline characters")


def _format_env_value(value: str) -> str:
    if any(char in value for char in " #="):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


def write_env_profile(
    profile: RunProfile, path: Path = Path(".env.profile")
) -> None:
    values = [
        ("EVAL_DATASET", profile.dataset),
        ("TARGET_TEMPERATURE", str(profile.temperature)),
        ("PROMPTFOO_LIMIT", str(profile.limits.promptfoo)),
        ("DEEPEVAL_LIMIT", str(profile.limits.deepeval)),
        ("RAGAS_LIMIT", str(profile.limits.ragas)),
        ("MODEL", ",".join(model.id for model in profile.models)),
    ]
    if profile.judge_model:
        values.append(("JUDGE_MODEL", profile.judge_model))

    lines: list[str] = []
    for key, value in values:
        _validate_env_value(key, value)
        lines.append(f"{key}={_format_env_value(value)}")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
