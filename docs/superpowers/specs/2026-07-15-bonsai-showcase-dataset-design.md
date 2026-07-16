# Bonsai Eval Showcase — Dataset Design

**Date:** 2026-07-15  
**Status:** Approved / Implemented

## Goal

Give Bonsai-27B Q1 a **representative, LinkedIn-ready eval track** that exercises **Promptfoo**, **DeepEval**, and **RAGAS** with clear metrics — without UDA-QA table noise.

## Primary dataset: SciQ

| Field | Value |
|-------|-------|
| HF id | [`allenai/sciq`](https://huggingface.co/datasets/allenai/sciq) |
| Split | `validation` |
| Why | Short `correct_answer` + paragraph `support` → maps cleanly to `EvalSample` and all three frameworks |
| Mapping | `question` → question; `correct_answer` → ground_truth; `support` → context |

### Sample sizes

| Run | SciQ n | Est. time (CPU) |
|-----|--------|-----------------|
| Dev smoke | 5 | ~15 min |
| LinkedIn post | 30 | ~2–3 h |
| Full local | 100 | overnight |

### Command

```bash
EVAL_DATASET=sciq PROMPTFOO_LIMIT=30 DEEPEVAL_LIMIT=30 RAGAS_LIMIT=30 make lab MODEL=bonsai
```

## Secondary wing: IFEval

| Field | Value |
|-------|-------|
| HF id | [`google/IFEval`](https://huggingface.co/datasets/google/IFEval) |
| Framework | Promptfoo only |
| Graders | Rule-based JS asserts for a supported constraint subset (no_comma, word/sentence counts, highlights, bullets, quotes) |
| Command | `IFEVAL_LIMIT=10 make eval-promptfoo-ifeval` |

## Out of scope (v1)

- Bitext retail chatbot (needs judge rubric; post #2)
- Gated financial QA (`finqa`, `tatqa`) until HF token confirmed
- Replacing UDA-QA — remains available via `EVAL_DATASET=feta|nq`

## Architecture

```
HF SciQ ──download_sciq.py──► data/raw/sciq/*.jsonl
          prepare_samples.py──► data/processed/sciq/samples.jsonl
                                      │
                    ┌─────────────────┼─────────────────┐
                    ▼                 ▼                 ▼
               Promptfoo         DeepEval            RAGAS
                    └─────────────────┬─────────────────┘
                                      ▼
                            results/dashboard (:3100)
```

## Config

| Env | Default | Meaning |
|-----|---------|---------|
| `EVAL_DATASET` | `sciq` | Dataset for promptfoo / deepeval / ragas |
| `HF_TOKEN` / `HF_FULL_ACCESS` | — | HF auth (aliases via `shared/hf_auth.py`) |
| `IFEVAL_LIMIT` | `10` | IFEval Promptfoo tests |

## LinkedIn narrative

> 27B-class model at ~3.6 GB (Bonsai Q1) running locally on CPU — evaluated with Promptfoo, DeepEval, and RAGAS on 30 SciQ science questions with evidence. Optional IFEval wing for instruction following.

## Key files

- [`scripts/download_sciq.py`](../../../scripts/download_sciq.py)
- [`scripts/prepare_samples.py`](../../../scripts/prepare_samples.py) (`--config sciq`)
- [`scripts/prepare_ifeval_promptfoo.py`](../../../scripts/prepare_ifeval_promptfoo.py)
- [`shared/adapters/dataset_loader.py`](../../../shared/adapters/dataset_loader.py)
- [`shared/hf_auth.py`](../../../shared/hf_auth.py)
- [`scripts/run_all_evals.sh`](../../../scripts/run_all_evals.sh)
