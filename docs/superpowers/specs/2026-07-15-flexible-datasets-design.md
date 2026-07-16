# Flexible datasets folder — design spec

**Date:** 2026-07-15  
**Status:** Approved · Phase 1 implemented

## Goal

Add datasets without editing Python: drop CSV/JSONL into `datasets/{id}/raw/`, configure `dataset.yaml`, run prepare → eval.

## Layout

```
datasets/
  _template/          # copy to start a new task
    dataset.yaml
    raw/
  {id}/
    dataset.yaml      # manifest (metadata + column mapping)
    raw/              # user files
    samples.jsonl     # generated (or drop-in ready)
```

## Manifest (`dataset.yaml`)

| Field | Purpose |
|-------|---------|
| `id` | Selector for `EVAL_DATASET` |
| `task_type` | `extractive_qa` \| `faq` \| `intent` → prompt + assert |
| `source.type` | `csv` \| `jsonl` \| `samples` \| `legacy` |
| `source.path` | Glob or file path relative to dataset folder |
| `source.mapping` | Column → EvalSample field |
| `eval.prompt` | `qa` \| `faq` \| `intent` |
| `eval.portfolio` | Include in `make portfolio` |
| `limits.default` | Default sample limit |

## Registry

- Auto-discover: scan `datasets/*/dataset.yaml` (skip `_`-prefixed dirs)
- `list_datasets()`, `get_dataset(id)`, `samples_path(id)`
- Legacy fallback: `data/processed/{id}/samples.jsonl` for unmigrated configs

## Prepare pipeline

1. Read manifest
2. Load CSV/JSONL via pandas (or pass-through `samples.jsonl`)
3. Map columns → `EvalSample`
4. `annotate_sample()` for complexity metadata
5. Write `datasets/{id}/samples.jsonl`

## Eval integration

All frameworks consume `samples.jsonl` via `dataset_loader.load_samples(EVAL_DATASET)`.

Promptfoo assert chosen from `manifest.eval.prompt`, not hardcoded dataset id.

## Phase scope

**Phase 1 (this release):** csv, jsonl, samples, legacy preparers; registry; CLI; wired pipeline.

**Phase 2:** HF download in YAML; migrate all built-ins to `datasets/`; drop legacy if/elif.

## Commands

```bash
make datasets-list
make prepare-dataset DATASET=my_task
EVAL_DATASET=my_task make lab MODEL=bonsai
```
