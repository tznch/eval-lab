# Real-world dataset portfolio & failure stratification

**Date:** 2026-07-15  
**Status:** Implemented

## Goal

Balance eval coverage across domains (science baseline, fintech, e-commerce, support) and report **where** models fail — by complexity tier, context length, and category — not only aggregate pass rates.

## Portfolio tracks

| ID | HF dataset | Domain | Task |
|----|------------|--------|------|
| `sciq` | `allenai/sciq` | Science baseline | Extractive QA over support paragraph |
| `financial_qa` | `virattt/financial-qa-10K` | Fintech / SEC 10-K | Extractive QA over filing excerpts |
| `ecommerce_faq` | `NebulaByte/E-Commerce_FAQs` | Retail FAQ | FAQ answer from policy context |
| `bitext_intent` | `bitext/Bitext-customer-support-llm-chatbot-training-dataset` | Support routing | Intent classification |

## Eval best practices applied

1. **Stratified reporting** — Pass rate by complexity (`easy` / `medium` / `hard`) and context bucket (`short` / `medium` / `long`), following RAG eval literature (report metrics by context length quartiles, not only means).

2. **Difficulty proxy without human labels** — HELM-style heuristic: combine context length, answer length, and question complexity when gold difficulty labels are unavailable (`shared/reporting/complexity.py`).

3. **Separate failure modes** — Do not collapse all failures into one score:
   - `grounding` — RAGAS faithfulness below threshold (answer not supported by context)
   - `judge_quality` — DeepEval LLM judge rejection
   - `format_or_content` — Promptfoo assert / keyword mismatch

4. **Per-dataset artifact paths** — Results stored under `results/{framework}/{model}/{dataset}/` so portfolio runs do not overwrite prior tracks.

5. **Balanced portfolio** — One command runs all four tracks with the same sample limit for fair cross-domain comparison.

## Commands

```bash
# Prepare all tracks (25 samples each)
make prepare-portfolio

# Run full portfolio eval for Bonsai
make portfolio MODEL=bonsai

# One command: evals + dashboard
make lab-portfolio MODEL=bonsai

# Dashboard failure view
make dashboard
# → http://127.0.0.1:3100/failures.html
```

## Outputs

- `results/analysis/failure_stratification.json` — stratified pass/fail by dimension
- `results/dashboard/failures.html` — human-readable breakdown
- Per track: `results/promptfoo/{model}/{dataset}/output.json`, `results/deepeval/{model}/{dataset}/junit.xml`, `results/ragas/{model}/{dataset}_scores.csv`

## Complexity annotation

Each sample in `data/processed/{dataset}/samples.jsonl` includes:

- `complexity`, `complexity_score`
- `context_bucket`, `context_chars`, `answer_chars`, `question_chars`
- `category`, `task_type`

Re-run `make prepare-portfolio` or `prepare_samples.py` to refresh annotations on existing raw data.
