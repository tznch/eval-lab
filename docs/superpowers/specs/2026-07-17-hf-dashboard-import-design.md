# Design: HuggingFace model & dataset import from dashboard

**Date:** 2026-07-17  
**Status:** Approved for planning  
**Scope:** MVP — Overview UI can download GGUF models and import HF datasets using local `HF_TOKEN`, without bundled per-model scripts.

## Goal

After deleting or ignoring bundled models/datasets, a user can:

1. Save `HF_TOKEN` (already available on Overview).
2. Point the dashboard at a HuggingFace **model repo**, pick a `.gguf`, download it locally, and wire env for Run eval auto-start.
3. Point the dashboard at a HuggingFace **dataset**, map question / answer / optional context columns, download a capped sample, create `datasets/{id}/dataset.yaml`, and prepare samples so the dataset appears in the Run eval checklist.

## Non-goals (MVP)

- Auto-start `llama-server` immediately after model download (existing Run eval auto-start remains).
- Cancel / stop an in-flight HF job.
- Intent/FAQ presets or auto-detect column mapping.
- Full multi-config HF dataset wizard (optional `config` field may be added later).
- Removing bundled examples from the repository.
- Sharing secrets via profiles (keys stay in `.env` only).

## Current constraints

- Model download today is hardcoded to `bonsai` / `qwen27` in `shared/profiles/download.py`.
- Dataset list for Run eval comes from `datasets/*/dataset.yaml` only (`list_setup_datasets`).
- Eval progress uses `results/run_status.json`; HF jobs must not collide with it.

## Approach

**Overview “Add from HuggingFace” + background jobs** (chosen).

Sync endpoints for cheap metadata (list GGUF files). Long work (download / import) returns `202` and runs in a detached subprocess, similar to dashboard eval.

## Architecture

```
Overview Setup
  ├─ API keys (existing)
  └─ Add from HuggingFace
       ├─ Model: repo → list GGUF → download job
       └─ Dataset: hf_id + split + mapping → import job

API
  POST /api/hf/models/list-files     (sync)
  POST /api/hf/models/download       (202)
  POST /api/hf/datasets/import       (202)
  GET  /api/hf/jobs/current          (poll)

Job state: results/hf_jobs.json
Logs:      results/logs/hf-*.log
Runner:    scripts/run_hf_job.py  (+ shared/hf_jobs.py)
```

### Job model

Single active HF job at a time (MVP).

```json
{
  "id": "uuid",
  "kind": "model_download" | "dataset_import",
  "status": "running" | "complete" | "error",
  "message": "human readable",
  "progress": null,
  "started_at": "...",
  "updated_at": "...",
  "result": {}
}
```

If `status == "running"`, new download/import requests return `409`.

HF jobs are **separate** from eval `run_status.json`.

## Model flow

### UI

1. Input: HF repo id (`org/name`).
2. Button: **List GGUF files** → populate select.
3. Optional: local model id / slug (default: sanitized repo name).
4. Button: **Download** → starts job; status area polls.

### API

**`POST /api/hf/models/list-files`**

Body (no secrets):

```json
{ "repo_id": "org/name" }
```

Behavior: `huggingface_hub.list_repo_files` with `HF_TOKEN` from env; return `{ "ok": true, "files": ["...gguf"] }`. Empty list is success with a clear message. Missing token for gated repos → `400` asking to save HF token.

**`POST /api/hf/models/download`**

```json
{
  "repo_id": "org/name",
  "filename": "Model-Q4_K_M.gguf",
  "model_id": "optional-slug"
}
```

Spawn background job → `hf_hub_download` into `data/models/{model_id}/`.

On success, upsert `.env` keys (do not overwrite unrelated keys):

- `{MODEL_ID}_BASE_URL=http://127.0.0.1:{port}/v1`
- `{MODEL_ID}_MODEL_NAME={stem of gguf}`
- `{MODEL_ID}_MODEL_PATH=data/models/{model_id}/{filename}`

Port selection: probe `8080–8090` and assign the first free port to `{MODEL_ID}_BASE_URL`. If all are busy, fail the job with a clear message (user can edit `.env` manually).

Also update process env so readiness sees the new model without restart when possible.

Legacy **Download model (example)** may remain as a convenience that calls the same generic downloader for known bonsai/qwen files, or stay as-is until a follow-up cleanup.

## Dataset flow

### UI

1. HF dataset id (`allenai/sciq`).
2. Split (UI default `train`, user-editable).
3. Local id for `datasets/{id}/` (default: last path segment of HF id).
4. Mapping:
   - `question` (required)
   - `ground_truth` (required; UI label “answer”)
   - `context` (optional)
5. Limit (UI default `200`) for download + prepare.
6. **Import** → job.

### Job steps

1. `load_dataset(hf_id, split=..., token=HF_TOKEN)` (prefer streaming / take first `limit` rows).
2. Write `datasets/{id}/raw/rows.jsonl`.
3. Write `datasets/{id}/dataset.yaml`:

```yaml
id: {id}
name: {id or HF title}
task_type: extractive_qa
topic: HuggingFace import
description: Imported from {hf_id} ({split})
hf_id: {hf_id}
task_prompt: Answer from provided context.
source:
  type: jsonl
  path: raw/rows.jsonl
  mapping:
    question: {user_question_col}
    ground_truth: {user_answer_col}
    context: {user_context_col}   # omit if empty
eval:
  prompt: qa
  portfolio: false
limits:
  default: {limit}
```

4. Call `prepare_dataset(id, limit)`.
5. `discover_datasets.cache_clear()` so Setup checklist refreshes.

### Validation

Before or during import: inspect first row keys. If mapped columns missing → job `error` listing available keys.

Reject unsafe local ids (path traversal, empty, `_template`).

## Security

- Never accept `HF_TOKEN` / `OPENROUTER_API_KEY` in HF request bodies (same guard pattern as other APIs; use lowercase payload fields only for non-secrets).
- Write secrets only via existing `/api/setup/secrets`.
- Profiles remain secret-free.
- Constrain download paths under repo `data/models/` and `datasets/`.

## UI placement

Overview → Setup card, below API keys:

- Subheading **Add from HuggingFace**
- Two stacked forms: Model / Dataset
- Shared job status strip under forms (poll `/api/hf/jobs/current`)

After success, soft-refresh setup options / readiness if Run eval panel is visible.

## Error handling

| Case | Behavior |
|------|----------|
| No HF token (gated / auth error) | `400` or job error: save token first |
| No `.gguf` files | List returns empty + message |
| Job already running | `409` |
| Column mapping miss | Job `error` + available keys |
| Network / disk | Job `error` + log path |

## Testing

- Unit: env upsert for model keys; dataset.yaml generation; job state transitions; id sanitization.
- API: reject uppercase secret keys; 409 when job running (mock); list/download/import with mocked hub/datasets.
- No live HuggingFace calls in CI.

## Implementation modules (expected)

| Module | Role |
|--------|------|
| `shared/hf_jobs.py` | Job status read/write |
| `shared/hf_import/models.py` | List GGUF + download + env wiring |
| `shared/hf_import/datasets.py` | HF → raw + yaml + prepare |
| `scripts/run_hf_job.py` | CLI entry for background Popen |
| `scripts/dashboard_api.py` | Routes above |
| `web/partials/overview.html` + `app.js` | Forms + polling |
| Tests under `tests/test_hf_*.py` | Coverage as above |

Exact filenames may shift slightly in the implementation plan; responsibilities stay the same.

## Success criteria

1. User with only `.env` HF token can download a third-party GGUF via Overview and see `{ID}_MODEL_PATH` set.
2. User can import an HF dataset with manual column mapping and see it in the Run eval dataset checklist after prepare.
3. Concurrent eval run and HF job do not share/clobber `run_status.json`.
4. CI stays offline w.r.t. HuggingFace.
