# LLM Testing Lab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scaffold a unified LLM eval lab practicing RAGAS, DeepEval, and Promptfoo on UDA-QA with local Gemma-4-12B (CPU) and GLM API judge.

**Architecture:** Framework-first folders under `eval/`, shared adapters in `shared/adapters/` for target model (OpenAI-compatible llama-server) and judge (Z.ai GLM). UDA-QA converted to JSONL via `dataset_loader.py`. Learning path: Promptfoo → DeepEval → RAGAS.

**Tech Stack:** Python 3.12+, Node 20+ (promptfoo), llama.cpp llama-server, huggingface_hub, ragas, deepeval, promptfoo, httpx, pydantic, python-dotenv

## Global Constraints

- Hardware: Ryzen HX, 32 GB RAM, no dGPU — CPU inference only
- Default target: `unsloth/gemma-4-12b-it-GGUF:UD-Q4_K_XL` via llama-server port 8080
- Judge: GLM via Z.ai API, key from `.env` as `zai_api_key`
- Primary dataset: UDA-QA `feta` (dev 50), then `nq` (50 for RAGAS)
- Bitext, fin, tat sub-datasets: out of scope v1
- Results go to `results/{ragas,deepeval,promptfoo}/`
- Do not commit `.env`

---

### Task 1: Project Foundation

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `README.md`
- Create: directory scaffold under `data/`, `shared/`, `eval/`, `models/`, `results/`, `scripts/`

**Interfaces:**
- Produces: installable Python package `llmtesting` with deps ragas, deepeval, httpx, pydantic, python-dotenv, datasets, pandas

- [ ] **Step 1: Create pyproject.toml**

```toml
[project]
name = "llmtesting"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "httpx>=0.27",
    "pydantic>=2.0",
    "python-dotenv>=1.0",
    "datasets>=3.0",
    "pandas>=2.0",
    "ragas>=0.2",
    "deepeval>=2.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "ruff>=0.8"]

[tool.setuptools.packages.find]
where = ["."]
include = ["shared*"]
```

- [ ] **Step 2: Create .gitignore**

```
.env
__pycache__/
*.pyc
.venv/
results/
data/raw/
data/processed/
*.egg-info/
.pytest_cache/
node_modules/
.promptfoo/
```

- [ ] **Step 3: Create .env.example**

```
zai_api_key=your_zai_api_key_here
TARGET_MODEL_BASE_URL=http://127.0.0.1:8080/v1
TARGET_MODEL_NAME=gemma-4-12b
GLM_MODEL=glm-4-flash
```

- [ ] **Step 4: Install Python deps**

Run: `cd /home/tznch/projects/llmtesting && python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"`
Expected: successful install

- [ ] **Step 5: Install promptfoo globally**

Run: `npm install -g promptfoo`
Expected: `promptfoo --version` prints version

---

### Task 2: Shared Schemas and Config

**Files:**
- Create: `shared/__init__.py`
- Create: `shared/schemas/__init__.py`
- Create: `shared/schemas/eval_sample.py`
- Create: `shared/config.py`

**Interfaces:**
- Produces: `EvalSample` pydantic model, `load_settings()` reading `.env`

- [ ] **Step 1: Write eval_sample.py**

```python
from pydantic import BaseModel, Field

class EvalSample(BaseModel):
    id: str
    question: str
    ground_truth: str
    context: str = ""
    doc_name: str = ""
    source: str = ""
```

- [ ] **Step 2: Write config.py**

```python
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Settings:
    zai_api_key: str
    target_base_url: str
    target_model_name: str
    glm_model: str

def load_settings() -> Settings:
    key = os.getenv("zai_api_key", "")
    if not key:
        raise ValueError("zai_api_key not set in .env")
    return Settings(
        zai_api_key=key,
        target_base_url=os.getenv("TARGET_MODEL_BASE_URL", "http://127.0.0.1:8080/v1"),
        target_model_name=os.getenv("TARGET_MODEL_NAME", "gemma-4-12b"),
        glm_model=os.getenv("GLM_MODEL", "glm-4-flash"),
    )
```

- [ ] **Step 3: Write test**

Create `tests/test_config.py` asserting `load_settings()` raises without key.

Run: `.venv/bin/pytest tests/test_config.py -v`

---

### Task 3: Target Model Adapter (llama-server)

**Files:**
- Create: `shared/adapters/__init__.py`
- Create: `shared/adapters/target_model.py`
- Create: `models/start-server.sh`

**Interfaces:**
- Produces: `TargetModelClient.complete(prompt: str) -> str`
- Consumes: `Settings.target_base_url`, `Settings.target_model_name`

- [ ] **Step 1: Implement TargetModelClient**

```python
import httpx
from shared.config import Settings

class TargetModelClient:
    def __init__(self, settings: Settings):
        self.base_url = settings.target_base_url.rstrip("/")
        self.model = settings.target_model_name

    def complete(self, prompt: str, system: str = "You are a helpful assistant.") -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.7,
        }
        r = httpx.post(f"{self.base_url}/chat/completions", json=payload, timeout=120.0)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
```

- [ ] **Step 2: Create models/start-server.sh**

```bash
#!/usr/bin/env bash
set -euo pipefail
THREADS="${LLAMA_THREADS:-16}"
exec llama-server \
  -hf unsloth/gemma-4-12b-it-GGUF:UD-Q4_K_XL \
  --spec-type draft-mtp --spec-draft-n-max 2 \
  -t "$THREADS" \
  --port 8080 \
  --host 127.0.0.1
```

- [ ] **Step 3: Smoke test** (requires llama-server installed and model downloaded)

Run: `chmod +x models/start-server.sh && models/start-server.sh` (background)
Run: `.venv/bin/python -c "from shared.config import load_settings; from shared.adapters.target_model import TargetModelClient; print(TargetModelClient(load_settings()).complete('Say hi in 3 words'))"`

---

### Task 4: GLM Judge Adapter

**Files:**
- Create: `shared/adapters/judge_glm.py`

**Interfaces:**
- Produces: `GLMJudge.evaluate(question, answer, ground_truth) -> dict` with score 0-1 and reason

- [ ] **Step 1: Implement GLMJudge using Z.ai OpenAI-compatible API**

```python
import httpx
from shared.config import Settings

JUDGE_SYSTEM = """You are an evaluation judge. Score the answer against the ground truth.
Reply in JSON only: {"score": 0.0-1.0, "reason": "brief explanation"}"""

class GLMJudge:
    ZAI_BASE = "https://api.z.ai/api/paas/v4"

    def __init__(self, settings: Settings):
        self.api_key = settings.zai_api_key
        self.model = settings.glm_model

    def evaluate(self, question: str, answer: str, ground_truth: str) -> dict:
        user_msg = f"Question: {question}\nAnswer: {answer}\nGround truth: {ground_truth}"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": JUDGE_SYSTEM},
                {"role": "user", "content": user_msg},
            ],
            "temperature": 0.0,
        }
        r = httpx.post(
            f"{self.ZAI_BASE}/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=60.0,
        )
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"]
        import json
        return json.loads(content)
```

- [ ] **Step 2: Smoke test**

Run: `.venv/bin/python scripts/smoke_judge.py` (create minimal script)
Expected: JSON with score and reason

---

### Task 5: UDA-QA Dataset Loader

**Files:**
- Create: `shared/adapters/dataset_loader.py`
- Create: `scripts/download_uda_qa.py`
- Create: `scripts/prepare_samples.py`

**Interfaces:**
- Produces: `load_uda_qa(config: str, limit: int) -> list[EvalSample]`
- Produces: `data/processed/uda-qa/feta/samples.jsonl`

- [ ] **Step 1: Create download script**

Downloads `feta` test parquet from HuggingFace `qinchuanhui/UDA-QA` and wiki docs zip from `src_doc_files`.

- [ ] **Step 2: Implement loader**

Reads parquet, loads matching doc text from extracted PDFs/HTML (v1: use extended_qa_info or plain text fallback from HF fields), writes JSONL.

- [ ] **Step 3: Generate 50-sample dev set**

Run: `.venv/bin/python scripts/prepare_samples.py --config feta --limit 50`
Expected: `data/processed/uda-qa/feta/samples.jsonl` with 50 lines

---

### Task 6: Promptfoo Eval (first framework)

**Files:**
- Create: `eval/promptfoo/promptfooconfig.yaml`
- Create: `eval/promptfoo/prompts/qa.txt`
- Create: `eval/promptfoo/README.md`

**Interfaces:**
- Consumes: `data/processed/uda-qa/feta/samples.jsonl`
- Consumes: llama-server at :8080, GLM for llm-rubric assertions

- [ ] **Step 1: Create promptfooconfig.yaml**

```yaml
description: UDA-QA feta QA eval
prompts:
  - file://prompts/qa.txt
providers:
  - id: openai:chat:gemma-4-12b
    config:
      apiBaseUrl: http://127.0.0.1:8080/v1
      apiKey: local
tests:
  - vars:
      question: ...
      context: ...
    assert:
      - type: llm-rubric
        value: Answer matches ground truth
        provider: file://providers/glm-judge.yaml
outputPath: ../../results/promptfoo/output.json
```

- [ ] **Step 2: Generate tests from JSONL**

Script `scripts/jsonl_to_promptfoo.py` converts samples to promptfoo test cases.

- [ ] **Step 3: Run eval**

Run: `cd eval/promptfoo && promptfoo eval`
Expected: results in `results/promptfoo/`

---

### Task 7: DeepEval Eval (second framework)

**Files:**
- Create: `eval/deepeval/test_uda_qa.py`
- Create: `eval/deepeval/conftest.py`
- Create: `shared/adapters/deepeval_glm_model.py`

**Interfaces:**
- Consumes: JSONL samples, TargetModelClient, GLMJudge wrapped as DeepEval model

- [ ] **Step 1: Wrap GLM as DeepEval DeepEvalBaseLLM**

- [ ] **Step 2: Write parametrized pytest**

```python
@pytest.mark.parametrize("sample", load_samples("feta", 50))
def test_answer_quality(sample, target_model, judge):
    answer = target_model.complete(format_prompt(sample))
    result = judge.evaluate(sample.question, answer, sample.ground_truth)
    assert result["score"] >= 0.5
```

- [ ] **Step 3: Run**

Run: `.venv/bin/pytest eval/deepeval/test_uda_qa.py -v --tb=short`

---

### Task 8: RAGAS Eval (third framework)

**Files:**
- Create: `eval/ragas/run.py`
- Create: `shared/adapters/ragas_glm_llm.py`

**Interfaces:**
- Consumes: `nq` JSONL (50 samples), TargetModelClient for generation, GLM for RAGAS judge LLM

- [ ] **Step 1: Build RAGAS dataset from JSONL**

Columns: question, answer, contexts (list), ground_truth

- [ ] **Step 2: Run faithfulness + answer_relevancy**

```python
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy
result = evaluate(dataset, metrics=[faithfulness, answer_relevancy], llm=glm_llm)
result.to_pandas().to_csv("results/ragas/nq_scores.csv")
```

- [ ] **Step 3: Run**

Run: `.venv/bin/python eval/ragas/run.py --config nq --limit 50`

---

### Task 9: Documentation and Makefile

**Files:**
- Modify: `README.md` with full workflow
- Create: `Makefile` with targets: `setup`, `download-data`, `prepare`, `server`, `eval-promptfoo`, `eval-deepeval`, `eval-ragas`

- [ ] **Step 1: Document prerequisites** (llama.cpp build, npm promptfoo, HF login optional)

- [ ] **Step 2: Add Makefile shortcuts**

```makefile
setup:
	python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
	npm install -g promptfoo
```

---

## Plan Self-Review

- Spec coverage: all 6 success criteria mapped to Tasks 3–8 ✓
- No TBD placeholders ✓
- Type consistency: EvalSample used across all loaders and eval tasks ✓
- llama-server install documented in Task 1 README and Task 9 ✓

## Execution Handoff

Plan saved. Choose execution mode when ready.
