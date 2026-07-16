import os

import httpx
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from shared.config import Settings


def _messages_to_openai(messages) -> list[dict]:
    lc_messages = []
    for m in messages:
        if isinstance(m, SystemMessage):
            lc_messages.append({"role": "system", "content": m.content})
        elif isinstance(m, HumanMessage):
            lc_messages.append({"role": "user", "content": m.content})
        elif isinstance(m, AIMessage):
            lc_messages.append({"role": "assistant", "content": m.content})
    return lc_messages


class RagasGLMLLM(BaseChatModel):
    settings: Settings

    @property
    def _llm_type(self) -> str:
        return "glm-zai"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        payload = {
            "model": self.settings.judge_model,
            "messages": _messages_to_openai(messages),
            "temperature": 0.0,
            "thinking": {"type": self.settings.glm_thinking},
        }
        response = httpx.post(
            f"{self.settings.glm_base_url.rstrip('/')}/chat/completions",
            json=payload,
            headers={
                "Authorization": f"Bearer {self.settings.zai_api_key}",
                "Content-Type": "application/json",
            },
            timeout=120.0,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=content))])


class RagasOpenRouterLLM(BaseChatModel):
    settings: Settings

    @property
    def _llm_type(self) -> str:
        return "openrouter"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        payload = {
            "model": self.settings.judge_model,
            "messages": _messages_to_openai(messages),
            "temperature": 0.0,
        }
        response = httpx.post(
            f"{self.settings.openrouter_base_url.rstrip('/')}/chat/completions",
            json=payload,
            headers={
                "Authorization": f"Bearer {self.settings.openrouter_api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/llmtesting",
                "X-OpenRouter-Title": "llmtesting",
            },
            timeout=180.0,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=content))])


def build_ragas_llm(settings: Settings) -> BaseChatModel:
    if settings.judge_provider.lower() == "openrouter":
        return RagasOpenRouterLLM(settings=settings)
    return RagasGLMLLM(settings=settings)


def build_ragas_embeddings(settings: Settings) -> Embeddings:
    """RAGAS answer_relevancy needs embeddings; use OpenRouter OpenAI-compatible API."""
    if settings.openrouter_api_key:
        from langchain_openai import OpenAIEmbeddings

        model = settings.openrouter_embedding_model
        return OpenAIEmbeddings(
            model=model,
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
        )

    from langchain_community.embeddings import HuggingFaceEmbeddings

    model = os.getenv(
        "RAGAS_EMBEDDING_MODEL",
        "sentence-transformers/all-MiniLM-L6-v2",
    )
    return HuggingFaceEmbeddings(model_name=model)
