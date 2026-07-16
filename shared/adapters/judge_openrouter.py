import httpx

from shared.adapters.judge_common import JUDGE_SYSTEM, parse_judge_json
from shared.config import Settings


class OpenRouterJudge:
    """LLM-as-judge via OpenRouter (OpenAI-compatible API)."""

    def __init__(self, settings: Settings):
        if not settings.openrouter_api_key:
            raise ValueError("OPENROUTER_API_KEY not set in .env")
        self.api_key = settings.openrouter_api_key
        self.model = settings.judge_model
        self.base_url = settings.openrouter_base_url.rstrip("/")

    def evaluate(self, question: str, answer: str, ground_truth: str) -> dict:
        user_msg = (
            f"Question: {question}\n"
            f"Answer: {answer}\n"
            f"Ground truth: {ground_truth}"
        )
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": JUDGE_SYSTEM},
                {"role": "user", "content": user_msg},
            ],
            "temperature": 0.0,
        }
        response = httpx.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/llmtesting",
                "X-OpenRouter-Title": "llmtesting",
            },
            timeout=180.0,
        )
        if response.is_error:
            raise httpx.HTTPStatusError(
                f"{response.status_code} from OpenRouter: {response.text[:300]}",
                request=response.request,
                response=response,
            )
        content = response.json()["choices"][0]["message"]["content"]
        return parse_judge_json(content)
