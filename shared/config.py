import os
from dataclasses import dataclass

from shared.env_files import load_project_env

load_project_env()


@dataclass(frozen=True)
class Settings:
    judge_provider: str  # "glm" | "openrouter"
    judge_model: str  # resolved model for the active provider
    zai_api_key: str
    target_base_url: str
    target_model_name: str
    glm_model: str
    glm_base_url: str
    glm_thinking: str  # "enabled" | "disabled"
    openrouter_api_key: str
    openrouter_model: str
    openrouter_base_url: str
    openrouter_embedding_model: str
    bonsai_base_url: str
    bonsai_model_name: str


def load_settings() -> Settings:
    judge_provider = os.getenv("JUDGE_PROVIDER", "openrouter").lower()
    zai_key = os.getenv("zai_api_key", "")
    openrouter_key = os.getenv("OPENROUTER_API_KEY", "")

    openrouter_model = os.getenv("OPENROUTER_MODEL", "tencent/hy3:free")
    glm_model = os.getenv("GLM_MODEL", "glm-5.2")
    judge_model_override = os.getenv("JUDGE_MODEL", "").strip()
    if judge_model_override:
        if judge_provider == "openrouter":
            openrouter_model = judge_model_override
        elif judge_provider == "glm":
            glm_model = judge_model_override

    judge_model = openrouter_model if judge_provider == "openrouter" else glm_model

    if judge_provider == "glm" and not zai_key:
        raise ValueError("zai_api_key not set in .env (required for JUDGE_PROVIDER=glm)")
    if judge_provider == "openrouter" and not openrouter_key:
        raise ValueError("OPENROUTER_API_KEY not set in .env (required for JUDGE_PROVIDER=openrouter)")
    if judge_provider not in ("glm", "openrouter"):
        raise ValueError(
            f"Unknown JUDGE_PROVIDER: {judge_provider!r}. Use 'openrouter' or 'glm'."
        )

    return Settings(
        judge_provider=judge_provider,
        judge_model=judge_model,
        zai_api_key=zai_key,
        target_base_url=os.getenv("TARGET_MODEL_BASE_URL", "http://127.0.0.1:8080/v1"),
        target_model_name=os.getenv("TARGET_MODEL_NAME", "gemma-4-12b"),
        glm_base_url=os.getenv(
            "GLM_BASE_URL",
            "https://api.z.ai/api/coding/paas/v4",
        ),
        glm_model=glm_model,
        glm_thinking=os.getenv("GLM_THINKING", "disabled"),
        openrouter_api_key=openrouter_key,
        openrouter_model=openrouter_model,
        openrouter_base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        openrouter_embedding_model=os.getenv(
            "OPENROUTER_EMBEDDING_MODEL", "openai/text-embedding-3-small"
        ),
        bonsai_base_url=os.getenv("BONSAI_BASE_URL", "http://127.0.0.1:8081/v1"),
        bonsai_model_name=os.getenv("BONSAI_MODEL_NAME", "bonsai-27b-q1"),
    )
