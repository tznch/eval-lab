# Dashboard HTMX + Alpine.js — Design Spec

**Date:** 2026-07-16  
**Status:** Approved

## Goal

Replace static HTML generation in `scripts/build_dashboard.py` with a **separated web layer** (HTMX + Alpine.js templates) and a **thin Python API** that serves HTML partials and JSON. Add a **live eval progress bar** that updates while portfolio runs execute.

## Motivation

| Problem today | Target |
|---------------|--------|
| ~1000 lines mix data + HTML + CSS in Python | Python = data/reporting only; web = templates |
| Static pages require `make dashboard` rebuild | Live partial refresh during eval |
| DeepEval tab shows flat cards — run/model unclear | Grouped by model + temperature run |
| No visibility into long portfolio progress | Progress bar: step N/M, current track/framework |
| Filters in vanilla JS duplicating logic | Alpine state + HTMX partial reload |

## Constraints

| Constraint | Value |
|------------|-------|
| Deployment | Local only (`127.0.0.1`) |
| Default port | `3100` (dashboard), `15500` (Promptfoo view, unchanged) |
| No SPA framework | HTMX 2.x + Alpine.js 3.x via CDN |
| Python API | FastAPI + Jinja2 (add to project deps) |
| Data layer | Keep `shared/reporting/*` unchanged in spirit |
| Backward compat | `make dashboard` continues exporting JSON artifacts |
| Eval scripts | Must not break existing portfolio/Makefile targets |

## Architecture

```
llmtesting/
├── web/                          # NEW — presentation layer
│   ├── index.html                # App shell, tabs, Alpine filter bar
│   ├── static/
│   │   └── app.css               # Extracted from build_dashboard STYLES
│   └── partials/                 # Jinja templates (HTMX swap targets)
│       ├── progress.html
│       ├── report.html
│       ├── deepeval.html
│       ├── promptfoo.html
│       ├── ragas.html
│       ├── performance.html
│       └── failures.html
├── scripts/
│   ├── dashboard_api.py          # NEW — FastAPI app
│   ├── serve_dashboard.sh        # MOD — uvicorn instead of http.server
│   └── build_dashboard.py        # SHRINK — export JSON only (Phase 3)
├── shared/reporting/
│   ├── run_status.py             # NEW — read/write results/run_status.json
│   ├── dashboard_catalog.py      # KEEP
│   └── (existing report builders)  # KEEP
└── results/
    ├── run_status.json           # NEW — live eval state
    ├── report/                   # combined_report.json, etc.
    └── dashboard/                # DEPRECATE static .html (Phase 3)
```

### Request Flow

```mermaid
flowchart LR
  Browser -->|GET /| index.html
  Browser -->|hx-get /partials/progress every 3s| FastAPI
  Browser -->|hx-get /partials/deepeval?models=...| FastAPI
  FastAPI --> shared/reporting
  FastAPI --> Jinja partials
  run_all_evals.sh -->|write| run_status.json
```

1. Browser loads `web/index.html` (Alpine initializes filter state from `localStorage`).
2. HTMX loads tab content from `/partials/{tab}` with query params for filters.
3. While `run_status.json.status == "running"`, progress partial polls every 3s.
4. On `status == "complete"`, HTMX triggers refresh of active results partial.

## Live Progress — `run_status.json`

Written atomically by eval scripts at each step boundary.

```json
{
  "status": "running",
  "model": "bonsai",
  "temp_tag": "t0.7",
  "started_at": "2026-07-16T01:00:00+00:00",
  "updated_at": "2026-07-16T01:22:43+00:00",
  "tracks": ["bitext_intent", "bitext_retail", "ecommerce_faq", "financial_qa", "sciq"],
  "frameworks_per_track": ["promptfoo", "deepeval", "ragas"],
  "step": 7,
  "total_steps": 15,
  "current": {
    "track": "sciq",
    "framework": "deepeval"
  },
  "completed": [
    {
      "track": "bitext_intent",
      "framework": "promptfoo",
      "ok": true,
      "duration_s": 42.1,
      "artifact": "results/promptfoo/bonsai/t0.7/bitext_intent/output.json"
    }
  ],
  "errors": []
}
```

**Status values:** `idle` | `running` | `complete` | `failed`

**Step calculation:** `len(tracks) × len(frameworks_per_track)` (default 5×3=15)

**Writers:**
- `run_portfolio_evals.sh` — init at start, finalize at end
- `run_all_evals.sh` — update before/after each framework step

**Readers:**
- `GET /partials/progress` — HTML fragment
- `GET /api/run-status` — raw JSON (optional debug)

## Unified Filter Bar

Alpine.js manages client state; HTMX sends as query params on partial reload.

| Control | Type | Query param | Default |
|---------|------|-------------|---------|
| Model | multi pill | `models=bonsai,qwen27` | all available |
| Temperature | multi pill | `temps=t0.2,t0.7` | all available |
| Track | select | `dataset=all\|sciq` | `all` |
| Framework | multi pill | `frameworks=promptfoo,...` | all |

Persist in `localStorage` key `llmLabFilters`.

Partial endpoints accept these params and filter data server-side before render.

## Tab Partials

| Tab | Partial route | Data source |
|-----|---------------|-------------|
| Overview | `/partials/overview` | catalog + framework counts |
| Report | `/partials/report` | `build_combined_report()` comparison matrix |
| DeepEval | `/partials/deepeval` | junit summaries **grouped by run** |
| Promptfoo | `/partials/promptfoo` | output.json cards + iframe block |
| RAGAS | `/partials/ragas` | scores.csv summaries |
| Performance | `/partials/performance` | `build_performance_report()` |
| Failures | `/partials/failures` | failure stratification |

### DeepEval Grouping (fixes current UX)

Render structure:

```
## bonsai · t=0.7 · 5/5 tracks · 96% pass
[grid of dataset cards]

## bonsai · t=0.2 · ...
## qwen27 · t=0.2 · ...
```

Each group header shows: model, temp, completed track count, aggregate pass rate.

## Promptfoo Embed

Keep iframe to `http://127.0.0.1:15500/` inside `partials/promptfoo.html`.  
`serve_dashboard.sh` still auto-starts `promptfoo view` when available.

## API Endpoints

| Method | Path | Returns |
|--------|------|---------|
| GET | `/` | `web/index.html` |
| GET | `/static/*` | CSS, future assets |
| GET | `/partials/{name}` | HTML fragment (Jinja) |
| GET | `/api/catalog` | `dashboard_catalog.json` |
| GET | `/api/run-status` | `run_status.json` |

Filter query params apply to all `/partials/*` except `progress`.

## Migration Phases

### Phase 1 — Progress + shell (MVP)
- `run_status.py` + eval script hooks
- FastAPI app with `/`, `/partials/progress`
- `web/index.html` shell + progress bar polling
- `make dashboard-serve` runs uvicorn
- Static HTML dashboard still works in parallel

### Phase 2 — Results partials + filters
- `/partials/report`, `/partials/deepeval` (grouped), `/partials/overview`
- Alpine filter bar + HTMX tab switching
- Server-side filter application

### Phase 3 — Full migration + cleanup
- Remaining partials (promptfoo, ragas, performance, failures)
- `build_dashboard.py` → export JSON/catalog only
- Remove generated `results/dashboard/*.html`
- Update README

## Testing

| Layer | Tests |
|-------|-------|
| `run_status.py` | unit: init, step advance, complete, atomic write |
| `dashboard_api.py` | pytest + httpx TestClient: partial routes return 200 |
| Templates | snapshot or assert key strings in HTML response |
| Eval hooks | integration: mock portfolio step writes status file |

## Non-Goals (v1)

- WebSockets / SSE (HTMX polling is sufficient)
- Auth / multi-user
- Editing eval config from UI
- Replacing Promptfoo's own UI

## Success Criteria

1. `make dashboard-serve` opens shell with live progress during `make portfolio`.
2. Progress shows step N/M and current track/framework without reading log files.
3. DeepEval tab groups results by model+temp run.
4. Filter bar persists across tabs and partial reloads.
5. Python contains no inline HTML string building for dashboard pages.
6. Existing JSON exports (`combined_report.json`) still generated.

## Dependencies to Add

```
fastapi>=0.115
uvicorn[standard]>=0.32
jinja2>=3.1
```

HTMX and Alpine loaded from CDN in `index.html` (no npm build step).
