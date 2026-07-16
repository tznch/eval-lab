#!/usr/bin/env python3
"""Run RAGAS evaluation on UDA-QA samples."""

import argparse
import os
from pathlib import Path

from datasets import Dataset

from shared.adapters.dataset_loader import load_samples
from shared.adapters.target_model import TargetModelClient
from shared.config import load_settings


def _format_prompt(question: str, context: str, task_type: str = "extractive_qa") -> str:
    if task_type == "intent":
        return (
            f"Support category hint: {context or 'general'}\n\n"
            f"User message: {question}\n\n"
            "Classify the user intent. Reply with ONLY the intent label (snake_case), nothing else."
        )
    ctx = context or "No context provided."
    return f"Context:\n{ctx}\n\nQuestion: {question}\n\nAnswer concisely."


def main() -> None:
    parser = argparse.ArgumentParser(description="RAGAS eval on prepared samples")
    parser.add_argument(
        "--config",
        default=os.getenv("EVAL_DATASET") or os.getenv("RAGAS_CONFIG") or "nq",
    )
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument(
        "--model-id",
        default=os.getenv("EVAL_MODEL_ID", "default"),
        help="Subfolder under results/ragas/",
    )
    args = parser.parse_args()

    settings = load_settings()
    target = TargetModelClient(settings)
    samples = load_samples(args.config, args.limit)

    rows = []
    for s in samples:
        answer = target.complete(_format_prompt(s.question, s.context, s.task_type))
        rows.append(
            {
                "sample_id": s.id,
                "question": s.question,
                "answer": answer,
                "contexts": [s.context or "No context."],
                "ground_truth": s.ground_truth,
            }
        )

    dataset = Dataset.from_list(rows)

    from shared.adapters.ragas_compat import ensure_ragas_imports

    ensure_ragas_imports()
    from ragas import evaluate
    from ragas.metrics import answer_relevancy, faithfulness

    from shared.adapters.ragas_llm import build_ragas_embeddings, build_ragas_llm
    from shared.reporting.run_paths import ragas_output

    llm = build_ragas_llm(settings)
    embeddings = build_ragas_embeddings(settings)
    result = evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy],
        llm=llm,
        embeddings=embeddings,
    )

    out_path = ragas_output(args.model_id, args.config, os.getenv("TARGET_TEMPERATURE", "0.2"))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    result_df = result.to_pandas()
    from shared.reporting.score_format import round_score

    for col in ("faithfulness", "answer_relevancy"):
        if col in result_df.columns:
            result_df[col] = result_df[col].apply(
                lambda v: round_score(v) if v == v else v  # preserve NaN
            )
    result_df.to_csv(out_path, index=False)
    print(f"Results saved to {out_path}")


if __name__ == "__main__":
    main()
