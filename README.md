# LLM Testing Lab

Run the same eval suite — **Promptfoo**, **DeepEval**, and **RAGAS** — against any local OpenAI-compatible target and any dataset registered in this repo.

## Stack

| Role | What you plug in |
|------|------------------|
| Target model | Any GGUF (or compatible) served by `llama-server` / OpenAI-compatible HTTP API |
| Judge | OpenRouter (any chat model) |
| Dataset | Any id under `datasets/` (manifest + samples) |
| Frameworks | Promptfoo · DeepEval · RAGAS |

Bundled manifests, download helpers, and server scripts are **examples** — swap them via env, profiles, or your own `datasets/{id}/`.

Longer reproduction notes: [docs/reproduce-run.md](docs/reproduce-run.md).

## Prerequisites

- Python 3.11+
- Node.js 20+ (for Promptfoo)
- [llama.cpp](https://github.com/ggml-org/llama.cpp) with `llama-server` (or another OpenAI-compatible local server)

```bash
git clone https://github.com/ggml-org/llama.cpp
cmake llama.cpp -B llama.cpp/build -DGGML_CUDA=OFF
cmake --build llama.cpp/build --config Release -j --target llama-server
# Add llama.cpp/build/bin to PATH (or set LLAMA_SERVER)
```

## Quick Start

```bash
# 1. Config
cp .env.example .env   # OPENROUTER_API_KEY + optional HF_TOKEN
# Point TARGET_MODEL_* (or MODEL-specific URLs) at your local server
make setup

# 2. Dataset — list, prepare, or add your own
make datasets-list
make prepare-dataset DATASET=<id> LIMIT=50
# or: cp -r datasets/_template datasets/my_task  → edit dataset.yaml

# 3. Model server (separate terminal)
# Example helpers exist (make server-<id> / …) — or start your own llama-server
# and set TARGET_MODEL_BASE_URL / TARGET_MODEL_NAME in .env

# 4. Smoke judge
make smoke-judge

# 5. Run
EVAL_DATASET=<id> make lab MODEL=<model_id>
# or shorter limits:
# EVAL_DATASET=<id> PROMPTFOO_LIMIT=5 DEEPEVAL_LIMIT=3 RAGAS_LIMIT=5 make lab MODEL=<model_id>
```

`make lab` will:

1. Prepare `EVAL_DATASET` if needed  
2. Start known model servers when `MODEL` matches a helper (otherwise use your already-running API)  
3. Run Promptfoo, DeepEval, and RAGAS  
4. Serve the dashboard on **:3100**

**Dashboard:** http://127.0.0.1:3100/  
Exports: `/exports/combined_report.json` · `/exports/combined_report.md`  
Optional Promptfoo UI: http://127.0.0.1:15500/

```bash
make export-report      # results/report/ without serving
make dashboard-serve    # binds 127.0.0.1:3100 only (default)
# DASHBOARD_PORT=3000 make dashboard-serve
# Remote Firefox over SSH:
#   ssh -L 3100:127.0.0.1:3100 user@host
# Opt-in LAN bind (not the default):
#   DASHBOARD_HOST=0.0.0.0 make dashboard-serve
```

## Judge (OpenRouter)

```bash
JUDGE_PROVIDER=openrouter
JUDGE_MODEL=<openrouter-model-id>   # e.g. tencent/hy3:free
OPENROUTER_API_KEY=sk-or-v1-...
```

```bash
make smoke-judge
```

## Datasets

Any folder `datasets/{id}/` with a `dataset.yaml` is a first-class eval track.

```bash
make datasets-list
make prepare-dataset DATASET=<id> LIMIT=50
EVAL_DATASET=<id> make lab MODEL=<model_id>
```

Add your own:

```bash
cp -r datasets/_template datasets/my_task
# put files in datasets/my_task/raw/
# edit datasets/my_task/dataset.yaml (column mapping)
```

See `datasets/_template/README.md`. Bundled ids (`sciq`, `financial_qa`, …) are samples you can keep or ignore.

## Models

Eval runners call an OpenAI-compatible `/v1` endpoint. Configure in `.env`:

```bash
TARGET_MODEL_BASE_URL=http://127.0.0.1:8080/v1
TARGET_MODEL_NAME=<served-model-name>
# optional: per-model overrides — see .env.example (MODEL_BASE_URL / MODEL_NAME pattern)
```

Download models via Overview **Add from HuggingFace**, or set `{ID}_BASE_URL` / `{ID}_MODEL_PATH` / `{ID}_MODEL_NAME` in `.env` and start your own OpenAI-compatible server.

`MODEL=<id>` in Make selects which configured endpoint the lab uses. Share exact recipe via profiles (below).

## Shareable run profiles

Secret-free YAML: dataset, temperature, limits, model HF refs.

```bash
make profile-export NAME=my-run
make profile-import PROFILE=path/to/profile.yaml
# → writes .env.profile; does not touch API keys
# download weights via Overview → Add from HuggingFace, then:
make lab MODEL=<model_id>
```

Dashboard: Report shows one card per `(model, temperature)` with eval tabs; **Export profile YAML** on a card downloads that run's recipe.  
**Import profile YAML** uploads a shared recipe into `.env.profile` (no API keys).  
On Overview, after import (or when `.env.profile` exists), the **Run eval** panel validates model/dataset/judge readiness and starts Promptfoo / DeepEval / RAGAS in the background with your chosen temperature, dataset, and frameworks.

Overview also supports importing directly from HuggingFace. Configure the required `HF_TOKEN` in `.env` or the dashboard's **Setup secrets** panel, then use **Add from HuggingFace** to list and download a repository's GGUF file in the background or import a dataset split by mapping its question, answer, and optional context columns; imported models are added to the local endpoint configuration, and imported datasets are registered and prepared for evaluation.

## Update eval tools

```bash
make tools-update   # uv pip -U + promptfoo@latest; prints versions
```

Framework upgrades can change scores — record printed versions next to your profile.

## Project Structure

```
datasets/              # {id}/dataset.yaml (+ optional helpers)
data/                  # raw / processed / models (gitignored)
shared/                # adapters, dataset registry, reporting, profiles
eval/                  # promptfoo · deepeval · ragas
models/                # optional llama-server start helper
profiles/              # shareable run recipes (YAML)
scripts/               # CLI, downloads, lab runner, dashboard
web/                   # HTMX dashboard
results/               # outputs (gitignored)
docs/                  # reproduction guide
```

## Docs

- [docs/reproduce-run.md](docs/reproduce-run.md) — comparable runs, profiles, outputs  
- `datasets/_template/README.md` — add a custom dataset  
