import httpx

from shared.config import Settings


class TargetModelClient:
    def __init__(self, settings: Settings):
        self.base_url = settings.target_base_url.rstrip("/")
        self.model = settings.target_model_name

    def complete(self, prompt: str, system: str = "You are a helpful assistant.") -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.7,
        }
        response = httpx.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            timeout=120.0,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
