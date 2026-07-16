# LLM Testing Lab — Design Spec

**Date:** 2026-07-15  
**Status:** Approved

## Goal

Practice LLM evaluation using three frameworks — **RAGAS**, **DeepEval**, and **Promptfoo** — on the **UDA-QA** RAG benchmark. Bitext CSV remains an optional separate track for non-RAG chatbot eval later.

## Constraints

| Constraint | Value |
|------------|-------|
| Hardware | Ryzen HX, 32 GB RAM, **no dGPU** |
| Target model inference | llama-server (llama.cpp, CPU) |
| Default target model | Gemma-4-12B Q4 (`unsloth/gemma-4-12b-it-GGUF:UD-Q4_K_XL`) |
| Alternative target | Qwen3.6-9B Q4 (Promptfoo A/B, sequential runs) |
| Judge model | GLM via Z.ai API (`zai_api_key` in `.env`) |
| Primary dataset | UDA-QA — start with `feta`, then `nq` |
| Dev sample size | 50 samples per framework run |
| Bitext | Optional `tracks/bitext/` — not in initial scope |

## Architecture

Framework-first layout with shared adapters:

```
llmtesting/
├── data/
│   ├── raw/uda-qa/           # HF parquet + src_doc_files
│   └── processed/uda-qa/       # unified samples.jsonl
├── shared/
│   ├── adapters/
│   │   ├── target_model.py     # OpenAI-compatible → llama-server :8080
│   │   ├── judge_glm.py        # Z.ai GLM API
│   │   └── dataset_loader.py   # UDA-QA → EvalSample
│   └── schemas/eval_sample.py
├── eval/
│   ├── ragas/
│   ├── deepeval/
│   └── promptfoo/
├── models/start-server.sh
├── tracks/bitext/              # future, out of scope v1
└── results/{ragas,deepeval,promptfoo}/
```

### Data Flow

1. Download UDA-QA parquet subset (`feta` or `nq`) + matching `src_doc_files`.
2. `dataset_loader.py` converts rows to unified `EvalSample` JSONL.
3. Each eval framework reads JSONL, calls target model via `target_model.py`, scores via framework metrics + `judge_glm.py`.
4. Results written to `results/<framework>/`.

### Unified Sample Format

```json
{
  "id": "feta_001",
  "question": "which datasets did they experiment with?",
  "ground_truth": "Europarl, MultiUN",
  "context": "... document text or retrieved chunks ...",
  "doc_name": "1912.01214",
  "source": "uda-qa/feta"
}
```

## Framework Roles

| Framework | Primary use on UDA-QA | Judge |
|-----------|----------------------|-------|
| **Promptfoo** | YAML-driven A/B: prompts, Gemma vs Qwen | GLM via custom provider |
| **DeepEval** | pytest-style runs, custom LLM metrics | GLM via DeepEval model wrapper |
| **RAGAS** | faithfulness, answer_relevancy, context_precision | GLM via Ragas LLM wrapper |

## Learning Path (implementation order)

1. **Promptfoo** — 20 `feta` samples, fastest feedback loop
2. **DeepEval** — 50 `feta` samples, GLM-as-judge integration
3. **RAGAS** — 50 `nq` samples, full RAG metric pipeline

## Model Strategy (CPU-only)

```bash
llama-server \
  -hf unsloth/gemma-4-12b-it-GGUF:UD-Q4_K_XL \
  --spec-type draft-mtp --spec-draft-n-max 2 \
  -t 8 --port 8080 --host 127.0.0.1
```

- MTP enabled; expect modest speedup on CPU (~10–30%).
- Promptfoo model comparison: sequential runs, not two servers simultaneously.
- Context for RAGAS v1: full-document text (no custom retriever).

## UDA-QA Download Scope

| Phase | Subset | Samples |
|-------|--------|---------|
| dev | `feta` | 50 |
| practice | `feta` + `nq` | 200 each |
| full | all configs | 10K+ (later) |

Excluded from v1: `fin`, `tat` (heavy PDFs, 77K+ words/doc).

## Out of Scope (v1)

- Bitext pipeline
- Docker / CI
- Custom retrieval pipeline
- Simultaneous multi-model inference
- `fin` / `tat` sub-datasets

## Success Criteria

- [ ] llama-server responds at `http://127.0.0.1:8080/v1`
- [ ] GLM judge returns scores via API
- [ ] UDA-QA `feta` samples loaded as JSONL
- [ ] Promptfoo run completes on 20 samples
- [ ] DeepEval pytest run completes on 50 samples
- [ ] RAGAS run completes on 50 `nq` samples with faithfulness score
