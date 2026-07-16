"""Dataset metadata and eval agenda for dashboard / export reports."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DatasetInfo:
    id: str
    name: str
    topic: str
    hf_id: str
    description: str
    task_prompt: str


@dataclass(frozen=True)
class FrameworkMetric:
    framework: str
    metric: str
    description: str
    interpretation: str


# Built-in metadata for legacy datasets without dataset.yaml
_LEGACY_DATASETS: dict[str, DatasetInfo] = {
    "sciq": DatasetInfo(
        id="sciq",
        name="SciQ",
        topic="Science QA with evidence",
        hf_id="allenai/sciq",
        description=(
            "Middle-school science questions with a supporting paragraph and a short "
            "correct answer. Each sample maps to context + question + ground truth — "
            "ideal for RAG-style evaluation."
        ),
        task_prompt=(
            "Given a science passage (context), answer the question concisely using "
            "only that evidence."
        ),
    ),
    "feta": DatasetInfo(
        id="feta",
        name="UDA-QA Feta",
        topic="Wikipedia table QA (hard RAG)",
        hf_id="qinchuanhui/UDA-QA",
        description=(
            "Table-based questions from Wikipedia. Requires parsing structured evidence — "
            "harder than SciQ, useful as a stress test."
        ),
        task_prompt="Answer from table/document evidence in context.",
    ),
    "nq": DatasetInfo(
        id="nq",
        name="UDA-QA NQ",
        topic="Natural Questions RAG",
        hf_id="qinchuanhui/UDA-QA",
        description="Open-domain QA subset from UDA-QA with short/long answers.",
        task_prompt="Answer from retrieved document context.",
    ),
    "financial_qa": DatasetInfo(
        id="financial_qa",
        name="Financial QA (10-K)",
        topic="Fintech / SEC filing RAG",
        hf_id="virattt/financial-qa-10K",
        description=(
            "Questions over SEC 10-K excerpts with short factual answers. "
            "Real-world fintech RAG; similar difficulty profile to SciQ."
        ),
        task_prompt="Answer from filing context using only the provided excerpt.",
    ),
    "ecommerce_faq": DatasetInfo(
        id="ecommerce_faq",
        name="E-Commerce FAQs",
        topic="Retail / delivery & orders FAQ",
        hf_id="NebulaByte/E-Commerce_FAQs",
        description=(
            "Real e-commerce FAQ pairs (orders, delivery, returns). "
            "Policy text used as RAG context."
        ),
        task_prompt="Answer the customer FAQ using the policy context.",
    ),
    "bitext_intent": DatasetInfo(
        id="bitext_intent",
        name="Bitext Support Intent",
        topic="Customer support intent routing",
        hf_id="bitext/Bitext-customer-support-llm-chatbot-training-dataset",
        description=(
            "User instructions mapped to support intents (cancel_order, track_order, …). "
            "Evaluates routing accuracy for chatbot use cases."
        ),
        task_prompt="Classify the user message into the correct support intent label.",
    ),
}

@dataclass(frozen=True)
class FrameworkGuide:
    """Per-tab explainer for the dashboard."""

    id: str
    title: str
    tagline: str
    what_it_does: str
    how_to_read: tuple[str, ...]
    caveats: tuple[str, ...] = ()


FRAMEWORK_GUIDES: dict[str, FrameworkGuide] = {
    "overview": FrameworkGuide(
        id="overview",
        title="Eval lab agenda",
        tagline="Same samples → three frameworks → one comparable report.",
        what_it_does=(
            "We take fixed JSONL samples (context, question, ground truth), run a local "
            "target model (llama-server), then score outputs with Promptfoo, DeepEval, and RAGAS. "
            "Portfolio tracks repeat this across SciQ, fintech, e-commerce FAQ, and support intent."
        ),
        how_to_read=(
            "Each framework measures a different failure mode — use all three, not one in isolation.",
            "Compare models (bonsai vs qwen27) only on identical samples and judge settings.",
            "Stratified failures show where quality drops (easy vs hard, short vs long context).",
        ),
        caveats=(
            "Judge model (HY3 via OpenRouter) affects DeepEval and RAGAS — keep it fixed across runs.",
            "Run one 27B model server at a time on CPU; results are not comparable across different temps unless noted.",
        ),
    ),
    "promptfoo": FrameworkGuide(
        id="promptfoo",
        title="Promptfoo",
        tagline="Fast, deterministic checks — keyword overlap and JavaScript asserts.",
        what_it_does=(
            "Promptfoo sends each sample to the target model with a task-specific prompt "
            "(QA, intent classification, etc.), then runs automated asserts on the raw text. "
            "No LLM judge — pass/fail is rule-based (ground-truth overlap, intent label match)."
        ),
        how_to_read=(
            "Pass rate = share of tests where asserts succeeded (0–100%, 3 decimal places).",
            "Errors = infrastructure failures (template, API) — not model quality; fix before comparing.",
            "Lower Promptfoo vs high DeepEval often means answers are semantically correct but phrased differently.",
        ),
        caveats=(
            "Strict on formatting — penalizes extra words even when meaning is right.",
            "Intent datasets need escaped templates; curly braces in user text can cause errors.",
        ),
    ),
    "deepeval": FrameworkGuide(
        id="deepeval",
        title="DeepEval",
        tagline="pytest + LLM-as-judge — semantic correctness vs ground truth.",
        what_it_does=(
            "Each sample is a pytest case: the target model generates an answer, then a judge LLM "
            "(default: OpenRouter tencent/hy3:free) scores alignment with ground truth on a 0–1 scale. "
            "Pass threshold is ≥ 0.3 — tuned for partial credit on paraphrases."
        ),
        how_to_read=(
            "Pass rate = fraction of samples the judge accepted (shown as passed / total).",
            "Scores are rounded to 3 decimal places in exports.",
            "100% pass with low Promptfoo → model understands task but fails strict string matching.",
        ),
        caveats=(
            "Judge bias and cost — HY3 is free but not identical to human review.",
            "Same judge must be used when comparing bonsai vs qwen27.",
        ),
    ),
    "ragas": FrameworkGuide(
        id="ragas",
        title="RAGAS",
        tagline="RAG quality metrics — is the answer grounded and on-topic?",
        what_it_does=(
            "RAGAS evaluates retrieval-augmented answers with two core metrics: "
            "faithfulness (is the answer supported by the provided context?) and "
            "answer relevancy (does it address the question?). "
            "Both use the same judge LLM as DeepEval for consistency."
        ),
        how_to_read=(
            "Scores are 0–1 (3 decimal places); higher is better.",
            "Portfolio pass rule: faithfulness ≥ 0.5 AND answer_relevancy ≥ 0.5.",
            "Low faithfulness on long financial_qa → hallucination or ignoring context.",
            "Intent-only tasks may show low faithfulness — little RAG context by design.",
        ),
        caveats=(
            "Not meaningful for pure classification without context — interpret intent tracks carefully.",
            "Embedding model (OpenRouter text-embedding-3-small) affects relevancy scores.",
        ),
    ),
    "failures": FrameworkGuide(
        id="failures",
        title="Failure analysis",
        tagline="Where the model fails — not just how much.",
        what_it_does=(
            "Aggregates pass/fail from all three frameworks and slices results by complexity tier "
            "(easy / medium / hard), context length bucket (short / medium / long), and category. "
            "Failure modes tag the primary reason: grounding (RAGAS), judge_quality (DeepEval), "
            "or format_or_content (Promptfoo)."
        ),
        how_to_read=(
            "Compare pass rates across buckets — a high overall score hiding long-context failures is a red flag.",
            "Same sample failing Promptfoo but passing DeepEval → formatting, not understanding.",
            "Export JSON for deeper dives into per-sample framework breakdown.",
        ),
        caveats=(
            "Complexity tiers are heuristics (length, question shape) — not human-labeled difficulty.",
        ),
    ),
    "performance": FrameworkGuide(
        id="performance",
        title="Performance metrics",
        tagline="Quantization, size, latency, and throughput — same hardware, same stack.",
        what_it_does=(
            "Aggregates static model specs (quant, BPW, GGUF size) with runtime signals from "
            "Promptfoo (latencyMs, tokenUsage), DeepEval (pytest wall time), and llama-server "
            "startup logs (projected host RAM). Lets you compare speed vs quality trade-offs."
        ),
        how_to_read=(
            "Avg latency = mean Promptfoo request time per track; lower is faster on CPU.",
            "Completion tok/s = completion tokens ÷ total Promptfoo wall time for that track.",
            "Projected RAM comes from server log at load — actual RSS may differ slightly.",
            "Compare models at the same temperature tag (t0.2 vs t0.7) separately.",
        ),
        caveats=(
            "CPU-only llama-server — not comparable to GPU or whitepaper GPU benchmarks.",
            "Sequential portfolio runs — only one 27B server at a time; RAM is per-model load.",
            "Partial runs (in-progress portfolio) show only completed tracks.",
        ),
    ),
    "report": FrameworkGuide(
        id="report",
        title="Combined report",
        tagline="Side-by-side model comparison on the same eval stack.",
        what_it_does=(
            "Rolls up Promptfoo pass rates, DeepEval judge pass rates, and RAGAS averages "
            "per model and dataset. Designed for portfolio showcases and export to JSON/Markdown."
        ),
        how_to_read=(
            "Compare bars across models on the same dataset — identical samples and judge.",
            "Promptfoo = strict format · DeepEval = semantic quality · RAGAS = RAG grounding.",
            "Use failures tab to explain score gaps (which bucket or mode drives the difference).",
        ),
        caveats=(
            "Report default dataset tag reflects last build — portfolio spans multiple tracks.",
            "External benchmarks (Bonsai whitepaper) use different harness — see docs/benchmarks/comparable-baseline.md.",
        ),
    ),
}


FRAMEWORK_METRICS: list[FrameworkMetric] = [
    FrameworkMetric(
        framework="Promptfoo",
        metric="Pass rate",
        description="Keyword/overlap assert on model output vs ground truth.",
        interpretation="Higher = more answers match expected content (fast, deterministic).",
    ),
    FrameworkMetric(
        framework="DeepEval",
        metric="Judge pass rate",
        description="pytest + LLM-as-judge scores each answer (threshold ≥ 0.3).",
        interpretation="Higher = judge agrees the answer is correct vs ground truth.",
    ),
    FrameworkMetric(
        framework="RAGAS",
        metric="Faithfulness · Answer relevancy",
        description=(
            "Faithfulness: answer grounded in context. "
            "Answer relevancy: answer addresses the question."
        ),
        interpretation="Scores 0–1; higher is better. Failures often cluster in long-context buckets.",
    ),
    FrameworkMetric(
        framework="Failure analysis",
        metric="Stratified pass rate",
        description=(
            "Pass/fail broken down by complexity tier (easy/medium/hard), "
            "context length bucket, and category. Failure modes: grounding, judge, format."
        ),
        interpretation="Shows WHERE the model fails, not just overall score (eval best practice).",
    ),
]

TASK_AGENDA = {
    "title": "Local LLM evaluation lab",
    "goal": (
        "Run the same target model through three industry eval frameworks on a fixed "
        "dataset, compare metrics, and export a combined report for sharing "
        "(e.g. LinkedIn, portfolio)."
    ),
    "pipeline": [
        "Prepare dataset samples (context + question + ground truth)",
        "Start local model server (llama-server)",
        "Run Promptfoo, DeepEval, and RAGAS on identical samples",
        "Stratify failures by complexity, context length, and category",
        "Build dashboard + export combined JSON/Markdown report",
    ],
}

PORTFOLIO_DATASETS: list[str] = []  # filled from registry at import


def _portfolio_ids() -> list[str]:
    from shared.datasets.registry import portfolio_dataset_ids

    return portfolio_dataset_ids()


def get_dataset_info(dataset_id: str) -> DatasetInfo:
    from shared.datasets.registry import get_dataset

    manifest = get_dataset(dataset_id)
    if manifest is not None:
        return DatasetInfo(
            id=manifest.id,
            name=manifest.name,
            topic=manifest.topic,
            hf_id=manifest.hf_id,
            description=manifest.description,
            task_prompt=manifest.task_prompt,
        )
    return _LEGACY_DATASETS.get(
        dataset_id,
        DatasetInfo(
            id=dataset_id,
            name=dataset_id.upper(),
            topic="Custom dataset",
            hf_id="—",
            description=f"Eval samples from config `{dataset_id}`.",
            task_prompt="Answer from provided context.",
        ),
    )


def portfolio_datasets() -> list[str]:
    return _portfolio_ids()
