from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from shared.config import Settings


class RagasGLMLLM(BaseChatModel):
    settings: Settings

    @property
    def _llm_type(self) -> str:
        return "glm-zai"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        import httpx

        lc_messages = []
        for m in messages:
            if isinstance(m, SystemMessage):
                lc_messages.append({"role": "system", "content": m.content})
            elif isinstance(m, HumanMessage):
                lc_messages.append({"role": "user", "content": m.content})
            elif isinstance(m, AIMessage):
                lc_messages.append({"role": "assistant", "content": m.content})

        payload = {
            "model": self.settings.glm_model,
            "messages": lc_messages,
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


def build_ragas_llm(settings: Settings) -> RagasGLMLLM:
    return RagasGLMLLM(settings=settings)
