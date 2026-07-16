import httpx

from shared.adapters.judge_common import JUDGE_SYSTEM, parse_judge_json
from shared.config import Settings


class GLMJudge:
    def __init__(self, settings: Settings):
        if not settings.zai_api_key:
            raise ValueError("zai_api_key not set in .env")
        self.api_key = settings.zai_api_key
        self.model = settings.judge_model
        self.base_url = settings.glm_base_url.rstrip("/")
        self.thinking = settings.glm_thinking

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
            "thinking": {"type": self.thinking},
        }
        response = httpx.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=120.0,
        )
        if response.is_error:
            raise httpx.HTTPStatusError(
                f"{response.status_code} from GLM API: {response.text[:300]}",
                request=response.request,
                response=response,
            )
        content = response.json()["choices"][0]["message"]["content"]
        return parse_judge_json(content)
