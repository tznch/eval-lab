# Reproduce a portfolio run locally

Short checklist if you want to repeat the same eval stack locally: models, datasets, judge, commands, and what to keep fixed so results are comparable.

## What this lab measures

Same fixed samples go through three frameworks:

| Framework | What it scores |
|-----------|----------------|
| [Promptfoo](https://www.promptfoo.dev/) | Deterministic asserts (keyword / format / intent label) |
| [DeepEval](https://docs.confident-ai.com/) | LLM-as-judge pass rate (pytest) |
| [RAGAS](https://docs.ragas.io/) | Faithfulness + answer relevancy |

One comparable export: `results/report/combined_report.{json,md}` + live dashboard on `:3100`.

Whitepaper numbers (EvalScope / vLLM) are **not** the same harness. For apples-to-apples, compare **our** bonsai vs qwen27 runs only. See [comparable-baseline.md](benchmarks/comparable-baseline.md).

---

## Models (GGUF)

| Lab ID | Quant | Size | Port | Env | Download |
|--------|-------|------|------|-----|----------|
| `bonsai` | Q1_0 (1.125 bpw) | ~3.6 GB | `8081` | `BONSAI_*` | `make download-bonsai` |
| `qwen27` | UD-IQ2_XXS (~2.8 bpw) | ~9.4 GB | `8082` | `QWEN_*` | `make download-qwen27` |
| `gemma` (optional) | A4B / local | varies | `8080` | `TARGET_*` | own GGUF |

### Links

- Bonsai GGUF: [prism-ml/Bonsai-27B-gguf](https://huggingface.co/prism-ml/Bonsai-27B-gguf)
- Qwen GGUF (IQ2): [unsloth/Qwen3.6-27B-GGUF](https://huggingface.co/unsloth/Qwen3.6-27B-GGUF) (`UD-IQ2_XXS`)
- Upstream FP8 reference: [Qwen/Qwen3.6-27B-FP8](https://huggingface.co/Qwen/Qwen3.6-27B-FP8)
- Lab notes: [docs/bonsai/bonsai-27b-whitepaper-summary.md](bonsai/bonsai-27b-whitepaper-summary.md)

### Local paths (after download)

```text
data/models/bonsai-27b-q1/Bonsai-27B-Q1_0.gguf
data/models/qwen3.6-27b-iq2/Qwen3.6-27B-UD-IQ2_XXS.gguf
```

Server scripts: `models/start-bonsai-server.sh`, `models/start-qwen27-server.sh`
Flags used: `--reasoning off`, host `127.0.0.1`, threads = `nproc`.

---

## Datasets (portfolio tracks)

Default portfolio = every dataset with `eval.portfolio: true` in `datasets/*/dataset.yaml`.

| Track ID | Task | Source | HF / file |
|----------|------|--------|-----------|
| `sciq` | extractive QA | SciQ validation | [allenai/sciq](https://huggingface.co/datasets/allenai/sciq) |
| `financial_qa` | RAG / 10-K | Financial QA | [virattt/financial-qa-10K](https://huggingface.co/datasets/virattt/financial-qa-10K) |
| `ecommerce_faq` | FAQ + policy context | E-Commerce FAQs | [NebulaByte/E-Commerce_FAQs](https://huggingface.co/datasets/NebulaByte/E-Commerce_FAQs) |
| `bitext_intent` | intent classify | Bitext support | [bitext/Bitext-customer-support-llm-chatbot-training-dataset](https://huggingface.co/datasets/bitext/Bitext-customer-support-llm-chatbot-training-dataset) |
| `bitext_retail` | intent classify | local CSV | repo file `bitext-retail-ecommerce-llm-chatbot-training-dataset.csv` |

Optional (not in default portfolio): UDA-QA `feta` / `nq` via `make prepare`.

### Prepare samples (25 per track, matching our portfolio runs)

```bash
make prepare-portfolio
# bitext_retail (if you want that track too):
make prepare-dataset DATASET=bitext_retail LIMIT=25
```

Or override:

```bash
PORTFOLIO_DATASETS=sciq,financial_qa,ecommerce_faq,bitext_intent,bitext_retail \
PORTFOLIO_LIMIT=25 make portfolio MODEL=bonsai
```

---

## Judge (must stay fixed across comparable runs)

Default in this lab:

| Setting | Value |
|---------|-------|
| Provider | OpenRouter |
| Model | [`tencent/hy3:free`](https://openrouter.ai/tencent/hy3:free) |
| Used by | DeepEval + RAGAS |

Copy `.env.example` → `.env`:

```bash
JUDGE_PROVIDER=openrouter
JUDGE_MODEL=tencent/hy3:free
OPENROUTER_API_KEY=sk-or-v1-...
# optional HF rate limits:
HF_TOKEN=hf_...
```

Smoke:

```bash
make smoke-judge
```

If you change the judge, **do not** compare scores to our published bonsai/qwen numbers.

---

## Keep these constant for a comparable run

1. Same `samples.jsonl` (same prepare limit / seed if you re-prepare)
2. Same judge model + provider
3. Same temperature tag (`TARGET_TEMPERATURE=0.2` or `0.7`) for each model you compare
4. Same recorded framework versions

### Align runs with shared profiles

Prefer a shared profile to align the dataset, temperature, limits, and model references across clones:

```bash
make profile-import PROFILE=profiles/examples/bonsai-sciq-t07.yaml
```

Before publishing comparable results, run `make tools-update` and record the printed package versions with the profile. Framework updates can change scores.

---

## Reproduce step by step

```bash
# 0. Prerequisites: Python 3.11+, Node 20+, llama-server on PATH
cp .env.example .env   # fill API keys
make setup

# 1. Models
make download-bonsai
# make download-qwen27   # if you want the baseline too

# 2. Data
make prepare-portfolio
make prepare-dataset DATASET=bitext_retail LIMIT=25   # optional 5th track

# 3. Bonsai portfolio @ t=0.2
make stop-servers
make server-bonsai          # separate terminal, or let portfolio start it
TARGET_TEMPERATURE=0.2 make portfolio MODEL=bonsai

# 4. Bonsai @ t=0.7 (optional second run)
TARGET_TEMPERATURE=0.7 make portfolio MODEL=bonsai SKIP_SETUP=1

# 5. Qwen comparable baseline @ t=0.2 (stops other servers)
TARGET_TEMPERATURE=0.2 make portfolio-qwen27

# 6. Report + UI
make dashboard
make dashboard-serve        # http://127.0.0.1:3100/
```

Single-dataset smoke (faster):

```bash
EVAL_DATASET=sciq PROMPTFOO_LIMIT=25 DEEPEVAL_LIMIT=25 RAGAS_LIMIT=25 \
  make lab MODEL=bonsai
```

---

## Outputs to share / compare

| Artifact | Path |
|----------|------|
| Combined report | `results/report/combined_report.json` |
| Markdown export | `results/report/combined_report.md` |
| Performance | `results/report/performance.json` |
| Per-run Promptfoo | `results/promptfoo/{model}/{temp}/{dataset}/output.json` |
| Per-run DeepEval | `results/deepeval/{model}/{temp}/{dataset}/junit.xml` |
| Per-run RAGAS | `results/ragas/{model}/{temp}/{dataset}*_scores.csv` |

Dashboard: Compare → Report for side-by-side tables.

---

## Suggested “run card” (paste into a post)

```text
Lab: LLM Testing Lab (local)
Models: bonsai Q1_0 (:8081) · qwen27 UD-IQ2_XXS (:8082)
Runtime: llama-server CPU, --reasoning off
Judge: OpenRouter tencent/hy3:free
Tracks: sciq, financial_qa, ecommerce_faq, bitext_intent[, bitext_retail]
n per track: 25
Temps: bonsai t=0.2 and t=0.7 · qwen27 t=0.2
Frameworks: Promptfoo + DeepEval + RAGAS
Report: results/report/combined_report.md
```

---

## Caveats

- Scores are **not** whitepaper leaderboard scores.
- Promptfoo can look harsh vs DeepEval when answers are right but phrased differently.
- Free OpenRouter models / quotas can change. Pin `JUDGE_MODEL` and note the date of your run.
- CPU latency is for relative lab comparison, not GPU throughput claims.
