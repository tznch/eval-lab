from pydantic import BaseModel, Field


class EvalSample(BaseModel):
    id: str
    question: str
    ground_truth: str
    context: str = ""
    doc_name: str = ""
    source: str = ""
    # Stratification metadata (filled at prepare time)
    category: str = ""
    task_type: str = "extractive_qa"  # extractive_qa | faq | intent
    complexity: str = "medium"  # easy | medium | hard
    complexity_score: float = 0.0
    context_chars: int = 0
    context_bucket: str = "short"  # short | medium | long
    answer_chars: int = 0
    question_chars: int = 0
    metadata: dict = Field(default_factory=dict)
