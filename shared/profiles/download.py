from collections.abc import Callable
from pathlib import Path

from shared.profiles.schema import RunProfile


def _download_bonsai() -> Path:
    from scripts.download_bonsai import download

    return download()


def _download_qwen27() -> Path:
    from scripts.download_qwen27 import download

    return download()


MODEL_DOWNLOADERS: dict[str, Callable[[], Path]] = {
    "bonsai": _download_bonsai,
    "qwen27": _download_qwen27,
}


def download_profile_model(
    profile: RunProfile, model_id: str | None = None
) -> Path:
    if model_id is None:
        if len(profile.models) != 1:
            raise ValueError("model_id is required when a profile has multiple models")
        model_id = profile.models[0].id

    downloader = MODEL_DOWNLOADERS.get(model_id)
    if downloader is None:
        supported = ", ".join(sorted(MODEL_DOWNLOADERS))
        raise ValueError(
            f"unsupported model id {model_id!r}; supported ids: {supported}"
        )
    return downloader()
