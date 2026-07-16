import json
import re

JUDGE_SYSTEM = """You are an evaluation judge. Score how well the answer matches the ground truth.
Reply with JSON only, no markdown: {"score": 0.0, "reason": "brief explanation"}
Score 1.0 = fully correct, 0.0 = completely wrong. Partial credit allowed."""


def parse_judge_json(content: str) -> dict:
    from shared.reporting.score_format import round_score

    content = content.strip()
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            data = json.loads(match.group())
        else:
            raise ValueError(f"Judge returned non-JSON: {content[:200]}")
    if "score" in data and data["score"] is not None:
        data["score"] = round_score(data["score"])
    return data
