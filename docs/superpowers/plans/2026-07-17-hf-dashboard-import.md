# HuggingFace Dashboard Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let Overview download any HF GGUF model and import any HF dataset (with column mapping) using local `HF_TOKEN`, so Run eval works without bundled model/dataset scripts.

**Architecture:** Sync metadata APIs + background jobs (`results/hf_jobs.json`, separate from eval `run_status.json`). Model path uses `huggingface_hub`; dataset path uses `datasets.load_dataset` → `datasets/{id}/` + `prepare_dataset`. Overview forms poll job status.

**Tech Stack:** FastAPI, Alpine/HTMX Overview, `huggingface_hub`, HuggingFace `datasets`, existing `shared/env_files.upsert_env_file`, pytest with mocks (no live HF in CI).

## Global Constraints

- Never accept `HF_TOKEN` / `OPENROUTER_API_KEY` (or other `SECRET_KEYS`) in HF request bodies; use env via `get_hf_token()`.
- Single active HF job at a time; concurrent start → `409`.
- HF jobs must not write `results/run_status.json`.
- Paths only under repo `data/models/` and `datasets/`.
- UI defaults: dataset split `train`, import limit `200`.
- Model ports: probe `8080–8090` for first free; if none free, job errors.
- Respond / commit messages in English for code; user-facing UI copy in English (existing dashboard language).

## File map

| File | Responsibility |
|------|----------------|
| `shared/hf_jobs.py` | Read/write `results/hf_jobs.json` job state |
| `shared/hf_import/ids.py` | Sanitize model/dataset local ids |
| `shared/hf_import/models.py` | List GGUF files, download, wire `.env` |
| `shared/hf_import/datasets.py` | Import HF dataset → raw + yaml + prepare |
| `shared/hf_import/ports.py` | Find free localhost port in 8080–8090 |
| `scripts/run_hf_job.py` | CLI entry for background Popen |
| `scripts/dashboard_api.py` | `/api/hf/*` routes |
| `web/partials/overview.html` | Forms + job status |
| `web/static/app.js` / `app.css` | Client logic / styles |
| `tests/test_hf_*.py` | Unit + API tests with mocks |

---

### Task 1: HF job state machine

**Files:**
- Create: `shared/hf_jobs.py`
- Test: `tests/test_hf_jobs.py`

**Interfaces:**
- Produces:
  - `JOBS_PATH: Path`
  - `read_job() -> dict | None`
  - `write_job(data: dict) -> dict`
  - `start_job(*, kind: str, message: str = "") -> dict`  # sets status running, raises if already running
  - `finish_job(*, status: str, message: str = "", result: dict | None = None) -> dict`
  - `is_job_running() -> bool`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_hf_jobs.py
from shared import hf_jobs as hj

def test_start_job_sets_running(tmp_path, monkeypatch):
    monkeypatch.setattr(hj, "JOBS_PATH", tmp_path / "hf_jobs.json")
    data = hj.start_job(kind="model_download", message="starting")
    assert data["status"] == "running"
    assert data["kind"] == "model_download"
    assert data["id"]
    assert hj.is_job_running() is True

def test_start_job_rejects_when_running(tmp_path, monkeypatch):
    monkeypatch.setattr(hj, "JOBS_PATH", tmp_path / "hf_jobs.json")
    hj.start_job(kind="model_download")
    try:
        hj.start_job(kind="dataset_import")
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "already" in str(exc).lower()

def test_finish_job_complete(tmp_path, monkeypatch):
    monkeypatch.setattr(hj, "JOBS_PATH", tmp_path / "hf_jobs.json")
    hj.start_job(kind="model_download")
    done = hj.finish_job(status="complete", message="ok", result={"path": "x"})
    assert done["status"] == "complete"
    assert done["result"]["path"] == "x"
    assert hj.is_job_running() is False
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `.venv/bin/python -m pytest tests/test_hf_jobs.py -q --tb=line`  
Expected: FAIL (module missing)

- [ ] **Step 3: Implement `shared/hf_jobs.py`**

```python
"""Background HuggingFace import/download job status (separate from eval run_status)."""
from __future__ import annotations
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JOBS_PATH = ROOT / "results" / "hf_jobs.json"

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def read_job() -> dict | None:
    if not JOBS_PATH.exists():
        return None
    try:
        return json.loads(JOBS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

def write_job(data: dict) -> dict:
    JOBS_PATH.parent.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = _now()
    tmp = JOBS_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(JOBS_PATH)
    return data

def is_job_running() -> bool:
    data = read_job()
    return bool(data and data.get("status") == "running")

def start_job(*, kind: str, message: str = "") -> dict:
    if is_job_running():
        raise RuntimeError("An HF job is already running")
    data = {
        "id": str(uuid.uuid4()),
        "kind": kind,
        "status": "running",
        "message": message,
        "progress": None,
        "started_at": _now(),
        "result": {},
    }
    return write_job(data)

def finish_job(*, status: str, message: str = "", result: dict | None = None) -> dict:
    data = read_job() or {}
    data["status"] = status
    data["message"] = message
    if result is not None:
        data["result"] = result
    return write_job(data)
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `.venv/bin/python -m pytest tests/test_hf_jobs.py -q`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add shared/hf_jobs.py tests/test_hf_jobs.py
git commit -m "Add HF job status store separate from eval progress."
```

---

### Task 2: Id sanitization + free port helper

**Files:**
- Create: `shared/hf_import/__init__.py`
- Create: `shared/hf_import/ids.py`
- Create: `shared/hf_import/ports.py`
- Test: `tests/test_hf_import_ids.py`

**Interfaces:**
- Produces:
  - `sanitize_local_id(raw: str, *, fallback: str = "import") -> str`
  - `default_model_id_from_repo(repo_id: str) -> str`
  - `default_dataset_id_from_hf(hf_id: str) -> str`
  - `find_free_port(start: int = 8080, end: int = 8090) -> int`  # raises RuntimeError if none

- [ ] **Step 1: Write failing tests**

```python
# tests/test_hf_import_ids.py
from shared.hf_import.ids import (
    default_dataset_id_from_hf,
    default_model_id_from_repo,
    sanitize_local_id,
)

def test_sanitize_rejects_traversal():
    assert sanitize_local_id("../etc") == "etc"
    assert sanitize_local_id("") == "import"
    assert sanitize_local_id("_template") == "template"

def test_defaults_from_repo_paths():
    assert default_model_id_from_repo("org/My-Model-GGUF") == "my-model-gguf"
    assert default_dataset_id_from_hf("allenai/sciq") == "sciq"
```

- [ ] **Step 2: Run — expect FAIL**

Run: `.venv/bin/python -m pytest tests/test_hf_import_ids.py -q --tb=line`  
Expected: FAIL

- [ ] **Step 3: Implement ids + ports**

`sanitize_local_id`: lowercase, replace non `[a-z0-9_-]` with `-`, strip `-_`, strip leading `_`, forbid empty → `fallback`, map `_template` → `template`.

`find_free_port`: for each port in range, try `socket.bind(("127.0.0.1", port))`; return first success; else `RuntimeError("No free port in 8080–8090")`.

- [ ] **Step 4: Run tests PASS + small port unit test**

```python
# add to tests/test_hf_import_ids.py or tests/test_hf_ports.py
from shared.hf_import.ports import find_free_port

def test_find_free_port_in_range():
    port = find_free_port(18080, 18090)
    assert 18080 <= port <= 18090
```

Run: `.venv/bin/python -m pytest tests/test_hf_import_ids.py tests/test_hf_ports.py -q`  
Expected: PASS (create `tests/test_hf_ports.py` if split)

- [ ] **Step 5: Commit**

```bash
git add shared/hf_import tests/test_hf_import_ids.py tests/test_hf_ports.py
git commit -m "Add HF import id sanitization and port probe helpers."
```

---

### Task 3: Model list GGUF + download + env wiring

**Files:**
- Create: `shared/hf_import/models.py`
- Test: `tests/test_hf_import_models.py`
- Modify: `shared/env_files.py` only if needed to reuse `upsert_env_file`

**Interfaces:**
- Consumes: `get_hf_token()`, `sanitize_local_id`, `default_model_id_from_repo`, `find_free_port`, `upsert_env_file`
- Produces:
  - `list_gguf_files(repo_id: str) -> list[str]`
  - `download_gguf(*, repo_id: str, filename: str, model_id: str | None = None) -> dict`  
    returns `{ "model_id", "path", "base_url", "model_name", "port" }`

- [ ] **Step 1: Write failing tests with mocks**

```python
# tests/test_hf_import_models.py
from pathlib import Path
from shared.hf_import import models as m

def test_list_gguf_files_filters(monkeypatch):
    monkeypatch.setattr(m, "get_hf_token", lambda: "tok")
    monkeypatch.setattr(
        m, "list_repo_files",
        lambda repo_id, token=None: ["a.gguf", "README.md", "b/Q4.gguf"],
    )
    assert m.list_gguf_files("org/x") == ["a.gguf", "b/Q4.gguf"]

def test_download_gguf_writes_env(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "ROOT", tmp_path)
    monkeypatch.setattr(m, "get_hf_token", lambda: "tok")
    monkeypatch.setattr(m, "find_free_port", lambda: 8085)
    out = tmp_path / "data" / "models" / "mymodel" / "file.gguf"
    def fake_dl(**kwargs):
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"gguf")
        return str(out)
    monkeypatch.setattr(m, "hf_hub_download", fake_dl)
    env_path = tmp_path / ".env"
    monkeypatch.setattr(m, "ENV_PATH", env_path)
    result = m.download_gguf(repo_id="org/x", filename="file.gguf", model_id="mymodel")
    assert result["port"] == 8085
    text = env_path.read_text(encoding="utf-8")
    assert "MYMODEL_BASE_URL=http://127.0.0.1:8085/v1" in text
    assert "MYMODEL_MODEL_PATH=" in text
    assert "MYMODEL_MODEL_NAME=file" in text
```

- [ ] **Step 2: Run — expect FAIL**

Run: `.venv/bin/python -m pytest tests/test_hf_import_models.py -q --tb=line`  
Expected: FAIL

- [ ] **Step 3: Implement `shared/hf_import/models.py`**

- Import `list_repo_files`, `hf_hub_download` from `huggingface_hub` (or inject via module attrs for tests).
- `list_gguf_files`: filter `name.lower().endswith(".gguf")`, sorted.
- `download_gguf`: resolve `model_id`, download to `ROOT/data/models/{model_id}/`, upsert env keys with uppercase sanitized id (`re.sub` non-alnum → `_`). Set `os.environ` for the three keys too.
- Env key helper: `env_prefix = re.sub(r"[^A-Za-z0-9]", "_", model_id).upper()`

- [ ] **Step 4: Run — expect PASS**

Run: `.venv/bin/python -m pytest tests/test_hf_import_models.py -q`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add shared/hf_import/models.py tests/test_hf_import_models.py
git commit -m "Add generic HF GGUF list/download with env wiring."
```

---

### Task 4: Dataset HF import → yaml + prepare

**Files:**
- Create: `shared/hf_import/datasets.py`
- Test: `tests/test_hf_import_datasets.py`

**Interfaces:**
- Consumes: `sanitize_local_id`, `default_dataset_id_from_hf`, `prepare_dataset`, `discover_datasets.cache_clear`
- Produces:
  - `import_hf_dataset(*, hf_id: str, split: str, local_id: str | None, mapping: dict[str, str], limit: int = 200) -> dict`  
    mapping keys: `question`, `ground_truth`, optional `context` (values = source column names)  
    returns `{ "dataset_id", "samples_path", "rows": n }`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_hf_import_datasets.py
from pathlib import Path
from shared.hf_import import datasets as d

class FakeRow(dict):
    pass

def test_import_writes_yaml_and_raw(tmp_path, monkeypatch):
    monkeypatch.setattr(d, "ROOT", tmp_path)
    monkeypatch.setattr(d, "DATASETS_ROOT", tmp_path / "datasets")
    rows = [
        {"q": "Q1", "a": "A1", "c": "C1"},
        {"q": "Q2", "a": "A2", "c": "C2"},
    ]
    monkeypatch.setattr(d, "load_hf_rows", lambda **kw: rows)
    monkeypatch.setattr(d, "prepare_dataset", lambda dataset_id, limit=None: tmp_path / "datasets" / dataset_id / "samples.jsonl")
    monkeypatch.setattr(d, "clear_dataset_cache", lambda: None)
    result = d.import_hf_dataset(
        hf_id="org/demo",
        split="train",
        local_id="demo",
        mapping={"question": "q", "ground_truth": "a", "context": "c"},
        limit=10,
    )
    assert result["dataset_id"] == "demo"
    yaml_text = (tmp_path / "datasets" / "demo" / "dataset.yaml").read_text(encoding="utf-8")
    assert "id: demo" in yaml_text
    assert "question: q" in yaml_text
    raw = (tmp_path / "datasets" / "demo" / "raw" / "rows.jsonl").read_text(encoding="utf-8")
    assert "Q1" in raw

def test_import_fails_on_missing_columns(tmp_path, monkeypatch):
    monkeypatch.setattr(d, "ROOT", tmp_path)
    monkeypatch.setattr(d, "DATASETS_ROOT", tmp_path / "datasets")
    monkeypatch.setattr(d, "load_hf_rows", lambda **kw: [{"q": "only"}])
    try:
        d.import_hf_dataset(
            hf_id="org/demo",
            split="train",
            local_id="demo",
            mapping={"question": "q", "ground_truth": "missing"},
            limit=5,
        )
        assert False
    except ValueError as exc:
        assert "missing" in str(exc).lower() or "available" in str(exc).lower()
```

- [ ] **Step 2: Run — expect FAIL**

Run: `.venv/bin/python -m pytest tests/test_hf_import_datasets.py -q --tb=line`  
Expected: FAIL

- [ ] **Step 3: Implement `shared/hf_import/datasets.py`**

- `load_hf_rows(**)` wraps `datasets.load_dataset` with token from `get_hf_token()`, take first `limit` rows as list[dict].
- Validate mapping columns against first row keys.
- Write JSONL preserving original column names (prepare uses mapping from yaml).
- Write `dataset.yaml` exactly as in the design spec.
- Call `prepare_dataset` then `discover_datasets.cache_clear()` via thin `clear_dataset_cache()`.

- [ ] **Step 4: Run — expect PASS**

Run: `.venv/bin/python -m pytest tests/test_hf_import_datasets.py -q`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add shared/hf_import/datasets.py tests/test_hf_import_datasets.py
git commit -m "Add HF dataset import to datasets/ with yaml and prepare."
```

---

### Task 5: Background CLI `run_hf_job.py`

**Files:**
- Create: `scripts/run_hf_job.py`
- Test: `tests/test_run_hf_job_cli.py` (optional light: argparse → calls mocked functions)

**Interfaces:**
- Consumes: `start_job`/`finish_job` already called by API **or** CLI owns start/finish — **choose: API calls `start_job` then Popen; CLI only runs work and `finish_job`**. Documented below.
- CLI args:
  - `model-download --repo-id --filename [--model-id]`
  - `dataset-import --hf-id --split --local-id --question-col --answer-col [--context-col] [--limit]`

- [ ] **Step 1: Implement CLI**

```python
# scripts/run_hf_job.py (outline)
# parse subcommands → call download_gguf / import_hf_dataset
# on success: finish_job(status="complete", message=..., result=...)
# on exception: finish_job(status="error", message=str(exc)); raise SystemExit(1)
```

API will call `start_job` **before** Popen so UI shows running immediately.

- [ ] **Step 2: Manual smoke with mocks in a tiny test**

```python
def test_cli_model_download_finishes(monkeypatch, tmp_path):
    from scripts import run_hf_job as cli
    monkeypatch.setattr("shared.hf_jobs.JOBS_PATH", tmp_path / "hf_jobs.json")
    from shared.hf_jobs import start_job, read_job
    start_job(kind="model_download")
    monkeypatch.setattr(cli, "download_gguf", lambda **k: {"path": "x", "model_id": "m"})
    assert cli.main(["model-download", "--repo-id", "a/b", "--filename", "f.gguf"]) == 0
    assert read_job()["status"] == "complete"
```

- [ ] **Step 3: Run PASS + commit**

```bash
git add scripts/run_hf_job.py tests/test_run_hf_job_cli.py
git commit -m "Add HF job CLI entry for dashboard background downloads."
```

---

### Task 6: Dashboard API routes

**Files:**
- Modify: `scripts/dashboard_api.py`
- Test: `tests/test_dashboard_hf_api.py`

**Interfaces:**
- `POST /api/hf/models/list-files` → `{ok, files, message?}`
- `POST /api/hf/models/download` → `202 {ok, message, job}`
- `POST /api/hf/datasets/import` → `202 {ok, message, job}`
- `GET /api/hf/jobs/current` → job dict or `{status:"idle"}`

Payloads use lowercase fields only (`repo_id`, `filename`, `model_id`, `hf_id`, `split`, `local_id`, `question_col`, `answer_col`, `context_col`, `limit`). Reject `SECRET_KEYS` via existing `_secret_keys_in`.

- [ ] **Step 1: Write API tests (mocked)**

```python
def test_list_files_ok(monkeypatch):
    monkeypatch.setattr("scripts.dashboard_api.list_gguf_files", lambda repo_id: ["a.gguf"])
    r = TestClient(create_app()).post("/api/hf/models/list-files", json={"repo_id": "org/x"})
    assert r.status_code == 200
    assert r.json()["files"] == ["a.gguf"]

def test_download_409_when_job_running(monkeypatch):
    monkeypatch.setattr("scripts.dashboard_api.is_job_running", lambda: True)
    r = TestClient(create_app()).post(
        "/api/hf/models/download",
        json={"repo_id": "org/x", "filename": "a.gguf"},
    )
    assert r.status_code == 409

def test_download_spawns(monkeypatch):
    monkeypatch.setattr("scripts.dashboard_api.is_job_running", lambda: False)
    monkeypatch.setattr("scripts.dashboard_api.start_job", lambda **k: {"id": "1", "status": "running"})
    spawned = {}
    class P:
        def __init__(self, args, **kw):
            spawned["args"] = args
            self.pid = 1
    monkeypatch.setattr("scripts.dashboard_api.subprocess.Popen", P)
    r = TestClient(create_app()).post(
        "/api/hf/models/download",
        json={"repo_id": "org/x", "filename": "a.gguf", "model_id": "x"},
    )
    assert r.status_code == 202
    assert "run_hf_job.py" in spawned["args"][1]

def test_import_rejects_secret_key():
    r = TestClient(create_app()).post(
        "/api/hf/datasets/import",
        json={"hf_id": "a/b", "HF_TOKEN": "nope"},
    )
    assert r.status_code == 400
```

- [ ] **Step 2: Implement routes** (Pydantic models `extra=forbid`, spawn like `/api/evals/run`)

- [ ] **Step 3: Run PASS**

Run: `.venv/bin/python -m pytest tests/test_dashboard_hf_api.py -q`  
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add scripts/dashboard_api.py tests/test_dashboard_hf_api.py
git commit -m "Expose HF list/download/import and job status API."
```

---

### Task 7: Overview UI — Add from HuggingFace

**Files:**
- Modify: `web/partials/overview.html`
- Modify: `web/static/app.js`
- Modify: `web/static/app.css`
- Test: extend `tests/test_dashboard_api.py` overview assertions for new headings / ids

**UI copy (English):**
- Heading: `Add from HuggingFace`
- Model: repo input, `List GGUF files`, file select, optional model id, `Download model`
- Dataset: hf id, split, local id, question/answer/context columns, limit, `Import dataset`
- Status strip bound to polled job

- [ ] **Step 1: Add HTML block under API keys** with inputs + buttons wired to Alpine methods

- [ ] **Step 2: Add JS**

```javascript
// state: hfRepo, hfGgufFiles, hfFilename, hfModelId, hfDatasetId, hfSplit='train',
// hfLocalId, hfQuestionCol, hfAnswerCol, hfContextCol, hfLimit=200, hfJob, hfMessage
// listHfGguf(), downloadHfModel(), importHfDataset(), pollHfJob() every 2s while running
// on complete: loadSetupPanel() if profile present
```

- [ ] **Step 3: CSS** for form stack (reuse `.secret-input` / `.ctrl-row-stack`)

- [ ] **Step 4: Assert partial contains `Add from HuggingFace` and key element ids**

- [ ] **Step 5: Commit**

```bash
git add web/partials/overview.html web/static/app.js web/static/app.css tests/test_dashboard_api.py
git commit -m "Add Overview HuggingFace model and dataset import forms."
```

---

### Task 8: Docs blurb + full test suite

**Files:**
- Modify: `README.md` (short paragraph under shareable profiles / dashboard)
- Modify: `docs/reproduce-run.md` (one paragraph)

- [ ] **Step 1: Document Overview HF import + required `HF_TOKEN`**

- [ ] **Step 2: Run full suite**

Run: `.venv/bin/python -m pytest -q`  
Expected: all PASS

- [ ] **Step 3: Commit**

```bash
git add README.md docs/reproduce-run.md
git commit -m "Document dashboard HuggingFace model and dataset import."
```

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| List GGUF files sync API | 3, 6 |
| Background model download + env keys + port probe | 2, 3, 5, 6 |
| Dataset import mapping + yaml + prepare | 4, 5, 6 |
| Separate `hf_jobs.json`, single job, 409 | 1, 6 |
| Overview UI + poll | 7 |
| No secrets in body / no live HF in CI | 3, 4, 6 |
| Docs | 8 |
| No auto-start server / no cancel job | Explicitly omitted |

## Placeholder / consistency review

- Job lifecycle: API `start_job` → CLI work → CLI `finish_job` (consistent across tasks 5–6).
- Env prefix uses same sanitization idea as `model_endpoint._env_key`.
- Dataset UI `answer` maps to API `answer_col` → yaml `ground_truth` mapping value = user column name.
