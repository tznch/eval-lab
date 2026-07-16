from typing import Protocol

from shared.adapters.judge_glm import GLMJudge
from shared.adapters.judge_openrouter import OpenRouterJudge
from shared.config import Settings


class Judge(Protocol):
    def evaluate(self, question: str, answer: str, ground_truth: str) -> dict: ...


def get_judge(settings: Settings) -> Judge:
    provider = settings.judge_provider.lower()
    if provider == "openrouter":
        return OpenRouterJudge(settings)
    if provider == "glm":
        return GLMJudge(settings)
    raise ValueError(f"Unknown JUDGE_PROVIDER: {settings.judge_provider!r}. Use 'glm' or 'openrouter'.")


def judge_label(settings: Settings) -> str:
    if settings.judge_provider.lower() == "openrouter":
        return f"openrouter/{settings.judge_model}"
    return f"glm/{settings.judge_model} (thinking={settings.glm_thinking})"
