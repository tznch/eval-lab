# Reproduce a run locally

Checklist to repeat the same eval stack: models, datasets, judge, commands, and what to keep fixed so results are comparable.

## What this lab measures

The same fixed samples go through three frameworks:

| Framework | What it scores |
|-----------|----------------|
| [Promptfoo](https://www.promptfoo.dev/) | Deterministic asserts (keyword / format / intent label) |
| [DeepEval](https://docs.confident-ai.com/) | LLM-as-judge pass rate (pytest) |
| [RAGAS](https://docs.ragas.io/) | Faithfulness + answer relevancy |

One comparable export: `results/report/combined_report.{json,md}` plus the live dashboard on `:3100`.

External leaderboard numbers (vendor benchmarks, different harnesses) are **not** comparable to this lab. Compare only runs produced with the same dataset, judge, temperature, and framework versions here.

---

## Models

Point eval runners at any OpenAI-compatible `/v1` endpoint:

```bash
TARGET_MODEL_BASE_URL=http://127.0.0.1:8080/v1
TARGET_MODEL_NAME=<served-model-name>
```

Optional: register extra endpoints per model id in `.env` (see `.env.example`). Convenience `make download-*` / `make server-*` targets exist for a few bundled GGUFs — use them only if helpful.

`MODEL=<id>` in Make selects which configured endpoint the lab uses.

---

## Datasets

Any folder `datasets/{id}/` with a `dataset.yaml` is a first-class track.

```bash
make datasets-list
make prepare-dataset DATASET=<id> LIMIT=25
```

Portfolio mode runs every dataset with `eval.portfolio: true` in its manifest:

```bash
PORTFOLIO_DATASETS=<id1>,<id2> PORTFOLIO_LIMIT=25 make portfolio MODEL=<model_id>
```

---

## Judge (keep fixed across comparable runs)

| Setting | Example |
|---------|---------|
| Provider | OpenRouter |
| Model | `tencent/hy3:free` (or any chat model you pin) |
| Used by | DeepEval + RAGAS |

```bash
cp .env.example .env
# JUDGE_PROVIDER=openrouter
# JUDGE_MODEL=<openrouter-model-id>
# OPENROUTER_API_KEY=sk-or-v1-...
make smoke-judge
```

If you change the judge, do not compare scores to runs that used a different judge.

---

## Keep these constant for a comparable run

1. Same `samples.jsonl` (same prepare limit / seed if you re-prepare)
2. Same judge model + provider
3. Same `TARGET_TEMPERATURE` for each model you compare
4. Same framework package versions (`make tools-update` — record printed versions)

### Align runs with shared profiles

Prefer a secret-free YAML profile to align dataset, temperature, limits, and model ids across clones:

```bash
make profile-export NAME=my-run          # from your .env / .env.profile
make profile-import PROFILE=profiles/examples/<example>.yaml
make lab MODEL=<model_id>
```

Or use the dashboard: **Report → Export profile YAML** on a run card, or **Import profile YAML** on Overview. After import (or when `.env.profile` already exists), use **Run eval** on Overview — pick temperature, dataset, and frameworks; the lab validates readiness (model endpoint, samples, judge when needed) and runs the pipeline in the background while the progress panel polls live status.

Overview can also import models and datasets from HuggingFace. Set the required `HF_TOKEN` in `.env` or **Setup secrets**, then use **Add from HuggingFace** to list a repository's GGUF files and download one in the background, or import a dataset split by mapping its question, answer, and optional context columns; the model's local endpoint settings are saved, while the dataset manifest and prepared samples are created automatically.

---

## Reproduce step by step

```bash
# 0. Prerequisites: Python 3.11+, Node 20+, llama-server (or compatible server)
cp .env.example .env
make setup

# 1. Data
make prepare-dataset DATASET=<id> LIMIT=25
# or portfolio:
# make prepare-portfolio

# 2. Start your model server (separate terminal)
# llama-server ...  OR  make server-<id>  if you use a bundled helper

# 3. Single-track smoke
EVAL_DATASET=<id> PROMPTFOO_LIMIT=25 DEEPEVAL_LIMIT=25 RAGAS_LIMIT=25 \
  make lab MODEL=<model_id>

# 4. Multi-track portfolio
TARGET_TEMPERATURE=0.7 make portfolio MODEL=<model_id>

# 5. Report + UI
make dashboard
make dashboard-serve    # http://127.0.0.1:3100/
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

Dashboard: **Report** lists one card per `(model, temperature)` with Promptfoo / DeepEval / RAGAS tabs.

---

## Suggested run card (paste into a post)

```text
Lab: LLM Testing Lab (local)
Model: <model_id> @ <endpoint>
Judge: OpenRouter <judge-model-id>
Dataset(s): <id>[, ...]
n per track: <limit>
Temperature: <t>
Frameworks: Promptfoo + DeepEval + RAGAS
Report: results/report/combined_report.md
Tool versions: (output of make tools-update)
```

---

## Caveats

- Scores depend on judge choice, sample limits, and framework versions — pin all three when sharing.
- Promptfoo can look harsh vs DeepEval when answers are right but phrased differently.
- Free API tiers and quotas can change; note the date of your run.
- Local CPU latency is for relative lab comparison, not GPU throughput claims.
