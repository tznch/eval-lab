# LLM Testing Lab

Practice LLM evaluation with **RAGAS**, **DeepEval**, and **Promptfoo** on [SciQ](https://huggingface.co/datasets/allenai/sciq) (showcase) and [UDA-QA](https://huggingface.co/datasets/qinchuanhui/UDA-QA) (hard RAG).

## Stack

| Role | Tool |
|------|------|
| Target model | Gemma-4 / Bonsai-27B Q1 via `llama-server` (CPU) |
| Judge | **OpenRouter** (`tencent/hy3:free` default) or GLM API (Z.ai) |
| Dataset | **SciQ** (default showcase) · UDA-QA (`feta`, `nq`) · IFEval mini-track |
| Frameworks | Promptfoo · DeepEval · RAGAS |

**Reproduce a full portfolio run on your own machine:** see [docs/reproduce-run.md](docs/reproduce-run.md) (models, datasets, links, env, commands).


## Prerequisites

- Python 3.11+
- Node.js 20+ (for Promptfoo)
- [llama.cpp](https://github.com/ggml-org/llama.cpp) with `llama-server` (CPU build, no CUDA)

```bash
git clone https://github.com/ggml-org/llama.cpp
cmake llama.cpp -B llama.cpp/build -DGGML_CUDA=OFF
cmake --build llama.cpp/build --config Release -j --target llama-server
# Add llama.cpp/build/bin to PATH
```

## Judge configuration

**Default:** OpenRouter with [`tencent/hy3:free`](https://openrouter.ai/tencent/hy3:free) — free 295B MoE, good for eval scoring. **Note:** free tier ends **July 21, 2026**.

Copy `.env.example` → `.env` and set `OPENROUTER_API_KEY`. To switch models without touching provider-specific vars, use `JUDGE_MODEL`:

```bash
JUDGE_PROVIDER=openrouter          # default
JUDGE_MODEL=tencent/hy3:free         # optional override
OPENROUTER_API_KEY=sk-or-v1-...
```

```bash
make smoke-judge                   # uses configured judge
make smoke-judge-openrouter        # force OpenRouter
make smoke-judge-glm               # force GLM (needs zai_api_key)
```

### GLM judge (optional)

Per [Z.ai Chat Completion API](https://docs.z.ai/api-reference/llm/chat-completion), supported text models include `glm-5.2`, `glm-5-turbo`, `glm-4.7`, etc.

### Important: Two API endpoints

| Key type | Base URL | Where to get key |
|----------|----------|------------------|
| **GLM Coding Plan** (subscription) | `https://api.z.ai/api/coding/paas/v4` | Coding Plan subscription |
| Developer API (pay-per-token) | `https://api.z.ai/api/paas/v4` | [z.ai/manage-apikey](https://z.ai) |
| Mainland China | `https://open.bigmodel.cn/api/paas/v4` | bigmodel.cn |

**Wrong endpoint → 429 "Insufficient balance"** even with a valid Coding Plan key.

Set in `.env`:

```bash
GLM_BASE_URL=https://api.z.ai/api/coding/paas/v4   # Coding Plan
GLM_MODEL=glm-5.2                                  # or glm-5-turbo, glm-4.7
GLM_THINKING=disabled                              # recommended for judge
```

| Model | Best for |
|-------|----------|
| `glm-5.2` | Highest quality judge (Coding Plan quota) |
| `glm-5-turbo` | Faster judge, many eval calls |
| `glm-4.7` / `glm-4.7-flash` | Lighter fallback |

Set `JUDGE_PROVIDER=glm` and `JUDGE_MODEL=glm-5.2` (or `GLM_MODEL=glm-5.2`).

## LinkedIn showcase (SciQ + Bonsai)

Primary demo dataset: [allenai/sciq](https://huggingface.co/datasets/allenai/sciq) — science QA with evidence (`support` → context). Runs all three frameworks.

```bash
# Prepare SciQ (optional; make lab downloads it)
make prepare-sciq

# Full showcase run (~30 samples × 3 frameworks, Bonsai only)
EVAL_DATASET=sciq PROMPTFOO_LIMIT=30 DEEPEVAL_LIMIT=30 RAGAS_LIMIT=30 make lab MODEL=bonsai

# Optional instruction-following wing (Promptfoo)
IFEVAL_LIMIT=10 make eval-promptfoo-ifeval
```

Set in `.env`:

```bash
EVAL_DATASET=sciq
HF_TOKEN=hf_...          # or HF_FULL_ACCESS — higher HF rate limits
```

## Add your own dataset (drop-in CSV/JSONL)

Datasets live in `datasets/{id}/` with a `dataset.yaml` manifest. No Python changes needed.

```bash
cp -r datasets/_template datasets/my_task
# put files in datasets/my_task/raw/
# edit dataset.yaml (column mapping)

make datasets-list
make prepare-dataset DATASET=my_task LIMIT=50
EVAL_DATASET=my_task make lab MODEL=bonsai
```

Example: `datasets/bitext_retail/` reads the local CSV at repo root and prepares intent-classification samples.

See `datasets/_template/README.md` and `docs/superpowers/specs/2026-07-15-flexible-datasets-design.md`.

## Quick Start

```bash
# 1. Setup
cp .env.example .env   # add API keys + optional HF_TOKEN
make setup

# 2. Download & prepare samples
make prepare-sciq      # SciQ showcase (recommended)
# make prepare         # UDA-QA feta+nq (hard RAG)

# 3. Start local model (separate terminal)
make server-bonsai     # or: make server  (Gemma)

# 4. Smoke test judge
make smoke-judge

# 5. Run evals
make eval-promptfoo              # EVAL_DATASET samples
make eval-promptfoo-ifeval       # IFEval mini-track
make eval-all                    # prepare + promptfoo + deepeval + ragas × models
make lab MODEL=bonsai            # ↑ + serve dashboard on :3100

# 6. Dashboard
make dashboard          # export JSON → results/dashboard/
make dashboard-serve    # live HTMX UI on :3100
```

### One command (recommended)

```bash
make lab MODEL=bonsai           # SciQ default dataset + Bonsai + dashboard
make lab MODEL=gemma
./scripts/run_lab.sh --model bonsai
```

This will:
1. Download/prepare `EVAL_DATASET` (default: `sciq`)
2. Start model servers if not running
3. Run Promptfoo, DeepEval, and RAGAS
4. Build & serve the dashboard

**URLs (live UI on :3100):**
- http://127.0.0.1:3100/ — overview, filters, progress bar
- http://127.0.0.1:3100/exports/combined_report.json — export for external tools
- http://127.0.0.1:3100/exports/combined_report.md — LinkedIn / Notion friendly
- http://127.0.0.1:15500/ — full Promptfoo interactive UI (iframe on Promptfoo tab)

Export without serving:

```bash
make export-report   # → results/report/combined_report.{json,md}
make dashboard       # copies exports into results/dashboard/ for /exports/*
```

(Default dashboard port is **3100** because `:3000` is often taken. Override: `DASHBOARD_PORT=3000 make dashboard-serve`.)

For a quick dev run (shorter eval time):

```bash
EVAL_DATASET=sciq PROMPTFOO_LIMIT=5 DEEPEVAL_LIMIT=3 RAGAS_LIMIT=5 make lab MODEL=bonsai
```

Hard RAG (UDA-QA) instead of SciQ:

```bash
EVAL_DATASET=feta make lab MODEL=bonsai
```

## Shareable run profiles

Export a secret-free recipe (dataset, temperature, limits, model HF refs):

```bash
make profile-export NAME=my-run
# → profiles/my-run.yaml (gitignored unless under profiles/examples/)
```

Import on another clone:

```bash
make profile-import PROFILE=profiles/examples/bonsai-sciq-t07.yaml
# writes .env.profile — does not touch API keys in .env
make download-bonsai   # or use Dashboard → Download model (from profile)
make lab MODEL=bonsai
```

## Update eval tools

```bash
make tools-update   # uv pip -U + promptfoo@latest; prints versions
```

Scores can change when frameworks update — record printed versions with your profile when comparing runs.

## Project Structure

```
data/
  raw/sciq/            # HF SciQ downloads
  raw/uda-qa/          # HF UDA-QA parquet
  raw/ifeval/          # IFEval selection
  processed/sciq/      # SciQ EvalSample JSONL
  processed/uda-qa/    # UDA-QA EvalSample JSONL
shared/
  adapters/            # target_model, judge, dataset_loader, hf_auth
eval/
  promptfoo/           # YAML-driven A/B + IFEval
  deepeval/            # pytest-style eval
  ragas/               # RAG metrics
models/
  start-server.sh      # Gemma CPU server
  start-bonsai-server.sh
results/               # eval outputs (gitignored)
docs/superpowers/      # design specs + plans
```

## Docs

- Design spec: `docs/superpowers/specs/2026-07-15-llm-testing-lab-design.md`
- Bonsai showcase dataset: `docs/superpowers/specs/2026-07-15-bonsai-showcase-dataset-design.md`
- Implementation plan: `docs/superpowers/plans/2026-07-15-llm-testing-lab.md`
