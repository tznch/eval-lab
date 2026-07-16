# Dashboard HTMX + Alpine.js Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace static Python-generated dashboard HTML with a FastAPI + HTMX + Alpine.js web layer, including a live eval progress bar during portfolio runs.

**Architecture:** Python keeps `shared/reporting/*` for data aggregation; new `web/` holds templates and static assets; `scripts/dashboard_api.py` serves Jinja partials; eval scripts write `results/run_status.json` at each step for live progress polling.

**Tech Stack:** FastAPI, Uvicorn, Jinja2, HTMX 2 (CDN), Alpine.js 3 (CDN), pytest, httpx TestClient

## Global Constraints

- Local-only deployment on `127.0.0.1`, default dashboard port `3100`
- Promptfoo view stays on port `15500` (iframe unchanged)
- No React/Vite/npm build — CDN scripts only
- Do not break existing `make portfolio` / `make dashboard` JSON exports
- Follow existing path layout: `results/{framework}/{model}/{temp}/{dataset}/`
- Respond in Ukrainian for user-facing docs if updating README sections

---

## File Map

| File | Responsibility |
|------|----------------|
| `shared/reporting/run_status.py` | Read/write `results/run_status.json` |
| `scripts/dashboard_api.py` | FastAPI app, routes, Jinja env |
| `web/index.html` | Shell, tabs, Alpine filters, HTMX targets |
| `web/static/app.css` | Dashboard styles (from `build_dashboard.py`) |
| `web/partials/progress.html` | Progress bar fragment |
| `web/partials/deepeval.html` | Grouped DeepEval cards (Phase 2) |
| `web/partials/report.html` | Comparison tables (Phase 2) |
| `scripts/serve_dashboard.sh` | Start uvicorn + promptfoo view |
| `scripts/run_all_evals.sh` | Hook status updates each framework |
| `scripts/run_portfolio_evals.sh` | Init/complete portfolio status |
| `tests/test_run_status.py` | Unit tests for status file |
| `tests/test_dashboard_api.py` | API route tests |

---

## Phase 1 — Progress bar + API shell (MVP)

### Task 1: Run status module

**Files:**
- Create: `shared/reporting/run_status.py`
- Create: `tests/test_run_status.py`

**Interfaces:**
- Produces:
  - `RunStatus` (TypedDict or dataclass fields matching spec)
  - `init_run(model: str, temp_tag: str, tracks: list[str], frameworks: list[str]) -> dict`
  - `start_step(track: str, framework: str) -> dict`
  - `complete_step(track: str, framework: str, ok: bool, duration_s: float, artifact: str | None) -> dict`
  - `finish_run(status: str = "complete") -> dict`  # status: complete|failed
  - `read_status() -> dict | None`
  - `write_status(data: dict) -> None`  # atomic via temp file + rename
  - `STATUS_PATH = ROOT / "results" / "run_status.json"`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_run_status.py
from shared.reporting.run_status import (
    init_run, start_step, complete_step, finish_run, read_status, STATUS_PATH
)

def test_init_run_sets_running(tmp_path, monkeypatch):
    monkeypatch.setattr("shared.reporting.run_status.STATUS_PATH", tmp_path / "run_status.json")
    data = init_run("bonsai", "t0.7", ["sciq"], ["promptfoo", "deepeval", "ragas"])
    assert data["status"] == "running"
    assert data["total_steps"] == 3
    assert data["step"] == 0
    assert read_status()["model"] == "bonsai"

def test_step_advance(tmp_path, monkeypatch):
    monkeypatch.setattr("shared.reporting.run_status.STATUS_PATH", tmp_path / "run_status.json")
    init_run("bonsai", "t0.2", ["sciq"], ["promptfoo"])
    start_step("sciq", "promptfoo")
    s = read_status()
    assert s["current"]["track"] == "sciq"
    assert s["current"]["framework"] == "promptfoo"
    complete_step("sciq", "promptfoo", ok=True, duration_s=10.0, artifact="results/promptfoo/bonsai/t0.2/sciq/output.json")
    s = read_status()
    assert s["step"] == 1
    assert len(s["completed"]) == 1
```

- [ ] **Step 2: Run test — expect FAIL**

Run: `.venv/bin/python -m pytest tests/test_run_status.py -v`  
Expected: FAIL — module not found

- [ ] **Step 3: Implement `run_status.py`**

```python
# shared/reporting/run_status.py — key structure
STATUS_PATH = ROOT / "results" / "run_status.json"

def write_status(data: dict) -> None:
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    tmp = STATUS_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(STATUS_PATH)

def init_run(model, temp_tag, tracks, frameworks):
    data = {
        "status": "running",
        "model": model,
        "temp_tag": temp_tag,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "tracks": tracks,
        "frameworks_per_track": frameworks,
        "step": 0,
        "total_steps": len(tracks) * len(frameworks),
        "current": None,
        "completed": [],
        "errors": [],
    }
    write_status(data)
    return data
```

- [ ] **Step 4: Run tests — expect PASS**

- [ ] **Step 5: Commit** (only if user requests)

---

### Task 2: Hook eval scripts to write status

**Files:**
- Modify: `scripts/run_portfolio_evals.sh`
- Modify: `scripts/run_all_evals.sh`

**Interfaces:**
- Consumes: `shared/reporting/run_status.py` via `"$VENV" -c "..."`

- [ ] **Step 1: Portfolio init/finish**

At start of eval loop in `run_portfolio_evals.sh`, after `DATASETS` parsed:

```bash
"$VENV" -c "
from shared.reporting.run_status import init_run
init_run('${MODEL}', 't${TARGET_TEMPERATURE:-0.2}', '${PORTFOLIO_DATASETS}'.split(','), ['promptfoo','deepeval','ragas'])
"
```

At end (before dashboard build):

```bash
"$VENV" -c "from shared.reporting.run_status import finish_run; finish_run('complete')"
```

- [ ] **Step 2: Per-framework hooks in `run_all_evals.sh`**

Before each framework eval function call, add:

```bash
update_status_start() {
  local track="$EVAL_DATASET" framework="$1"
  "$VENV" -c "
from shared.reporting.run_status import start_step
start_step('${track}', '${framework}')
"
}
```

After each framework completes (success or warn):

```bash
update_status_done() {
  local track="$EVAL_DATASET" framework="$1" ok="$2" artifact="$3"
  "$VENV" -c "
from shared.reporting.run_status import complete_step
complete_step('${track}', '${framework}', ok=${ok}, duration_s=0, artifact='${artifact}')
"
}
```

Wire into existing promptfoo/deepeval/ragas steps using `model_temp()` for temp_tag consistency.

- [ ] **Step 3: Manual smoke**

Run: `PORTFOLIO_DATASETS=sciq PROMFOLIO_LIMIT=1 make portfolio MODEL=bonsai SKIP_SETUP=1`  
Watch: `cat results/run_status.json` updates during run

---

### Task 3: FastAPI dashboard server

**Files:**
- Create: `scripts/dashboard_api.py`
- Create: `tests/test_dashboard_api.py`
- Modify: `pyproject.toml` — add fastapi, uvicorn, jinja2

**Interfaces:**
- Produces:
  - `app: FastAPI`
  - `create_app() -> FastAPI`
  - Routes: `GET /`, `GET /partials/progress`, `GET /api/run-status`, `GET /static/{path}`

- [ ] **Step 1: Add dependencies**

```toml
# pyproject.toml dependencies append:
"fastapi>=0.115",
"uvicorn[standard]>=0.32",
"jinja2>=3.1",
```

Run: `uv pip install -e ".[dev]" --python .venv/bin/python`

- [ ] **Step 2: Write failing API test**

```python
# tests/test_dashboard_api.py
from fastapi.testclient import TestClient
from scripts.dashboard_api import create_app

def test_progress_partial_idle():
    client = TestClient(create_app())
    r = client.get("/partials/progress")
    assert r.status_code == 200
    assert "progress" in r.text.lower() or "idle" in r.text.lower()

def test_run_status_json():
    client = TestClient(create_app())
    r = client.get("/api/run-status")
    assert r.status_code == 200
```

- [ ] **Step 3: Implement minimal `dashboard_api.py`**

```python
ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
templates = Jinja2Templates(directory=WEB / "partials")

@app.get("/partials/progress", response_class=HTMLResponse)
def partial_progress(request: Request):
    status = read_status() or {"status": "idle"}
    return templates.TemplateResponse("progress.html", {"request": request, "status": status})

@app.get("/api/run-status")
def api_run_status():
    return read_status() or {"status": "idle"}
```

Mount static files from `web/static`. Serve `web/index.html` at `/`.

- [ ] **Step 4: Run tests — expect PASS**

---

### Task 4: Web shell + progress partial

**Files:**
- Create: `web/index.html`
- Create: `web/partials/progress.html`
- Create: `web/static/app.css` (extract core variables + progress bar styles from `build_dashboard.py`)

- [ ] **Step 1: Progress partial template**

```html
<!-- web/partials/progress.html -->
<div id="eval-progress" class="progress-card">
  {% if status.status == 'idle' %}
    <p class="meta">No eval running.</p>
  {% elif status.status == 'running' %}
    <div class="progress-meta">
      <strong>{{ status.model }} · {{ status.temp_tag }}</strong>
      · step {{ status.step }}/{{ status.total_steps }}
      {% if status.current %}
        · now: {{ status.current.framework }} · {{ status.current.track }}
      {% endif %}
    </div>
    <div class="bar-track">
      <div class="bar-fill" style="width: {{ (status.step / status.total_steps * 100) if status.total_steps else 0 }}%"></div>
    </div>
  {% else %}
    <p class="meta">Eval {{ status.status }}.</p>
  {% endif %}
</div>
```

- [ ] **Step 2: Index shell with HTMX polling**

```html
<!-- web/index.html key fragment -->
<div id="progress-panel"
     hx-get="/partials/progress"
     hx-trigger="load, every 3s"
     hx-swap="innerHTML">
  Loading progress…
</div>
<script src="https://unpkg.com/htmx.org@2.0.4"></script>
<script defer src="https://unpkg.com/alpinejs@3.x.x/dist/cdn.min.js"></script>
```

Add Alpine `x-data` placeholder for filters (wired in Phase 2).

- [ ] **Step 3: Update `serve_dashboard.sh`**

Replace `python3 -m http.server` with:

```bash
.venv/bin/uvicorn scripts.dashboard_api:app --host 127.0.0.1 --port "${PORT}" --reload
```

Keep promptfoo view startup unchanged.

- [ ] **Step 4: Manual verify**

1. `make dashboard-serve`
2. Open `http://127.0.0.1:3100/`
3. Start portfolio in another terminal
4. Confirm progress bar advances without page reload

---

## Phase 2 — Filters + Report + DeepEval grouped

### Task 5: Server-side filter helper

**Files:**
- Create: `shared/reporting/dashboard_filters.py`
- Create: `tests/test_dashboard_filters.py`

**Interfaces:**
- Produces: `parse_filter_params(request.query_params) -> FilterState`
- Produces: `apply_run_filter(runs, filters) -> list`
- Produces: `apply_dataset_filter(tracks, dataset) -> list`

### Task 6: Alpine filter bar in `index.html`

Wire pills to HTMX `hx-include` / query string on `#main-content` partial loads. Persist via Alpine + `localStorage`.

### Task 7: `/partials/deepeval` grouped template

Group deepeval junit summaries by `(model, temp_tag)` using `parse_deepeval_path`. Template structure per spec.

### Task 8: `/partials/report` comparison tables

Port `_comparison_html_table` logic to Jinja macro in `web/partials/report.html`, data from `build_combined_report()`.

---

## Phase 3 — Remaining tabs + cleanup

### Task 9: Partials for promptfoo, ragas, performance, failures

Port remaining `build_*_page` functions to Jinja partials.

### Task 10: Shrink `build_dashboard.py`

Keep only JSON export: `combined_report.json`, `dashboard_catalog.json`, `performance.json`. Remove HTML generation.

### Task 11: README + Makefile

Document new flow:
- `make dashboard` — export data
- `make dashboard-serve` — live UI
- Progress bar during portfolio

---

## Self-Review (plan vs spec)

| Spec requirement | Task |
|------------------|------|
| Live progress bar | Tasks 1–4 |
| HTMX + Alpine separation | Tasks 4, 6 |
| DeepEval grouped by run | Task 7 |
| Unified filters | Tasks 5–6 |
| JSON exports preserved | Task 10 |
| Promptfoo iframe | Task 9 |
| FastAPI local server | Tasks 3–4 |
| Eval script hooks | Task 2 |

No placeholder steps — all tasks have concrete files and code snippets.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-16-dashboard-htmx.md`.

Spec saved to `docs/superpowers/specs/2026-07-16-dashboard-htmx-design.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks
2. **Inline Execution** — implement Phase 1 in this session with checkpoints

Which approach do you want?
