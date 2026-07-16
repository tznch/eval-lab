# Report Per-Run Cards Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Report’s cross-model comparison matrix with one card per `(model, temperature)`, in-card Promptfoo/DeepEval/RAGAS tabs showing dataset rows, and per-card Export profile YAML (remove Overview export).

**Architecture:** Rewrite `build_report_view` to emit `runs[]` grouped by `run_key(model, temp_tag)` from the existing catalog `comparison` payload. Render cards in `web/partials/report.html` with Alpine `x-data` + `panel-seg` + `x-show`. Reuse `POST /api/profiles/export`; card buttons pass explicit `models`/`temperature` via `data-*` into a small JS helper.

**Tech Stack:** Python view builders, Jinja partials, Alpine.js, FastAPI TestClient, existing profile export API.

## Global Constraints

- Run identity is `(model, temp_tag)` only — never invent a new run-group ID.
- Report must not render the old tracks×models comparison matrix (`view.tables`).
- All three framework tabs always visible on every card.
- Export is profile YAML recipe only (no results snapshot).
- Overview must not show Export profile YAML; Import + Download model stay.
- Secrets never appear in export bodies/YAML (`SECRET_KEYS` unchanged).
- Prefer TDD: failing test → implement → pass → commit per task.
- Only commit when a plan step says to commit (or the user asks).

## File structure

| Path | Responsibility |
|------|----------------|
| `shared/reporting/dashboard_views.py` | `build_report_view` → `runs[]`; helpers for track rows |
| `tests/test_dashboard_views.py` | Unit tests for new report shape + filters |
| `web/partials/report.html` | Run cards + in-card tabs + export button |
| `web/static/app.js` | `exportRunProfile` (explicit model/temp); trim Overview-only export usage |
| `web/partials/overview.html` | Remove Export button; update Setup copy |
| `tests/test_dashboard_api.py` | HTML assertions for report/overview; keep export API tests |
| `README.md` | One sentence on Report per-run export |

---

### Task 1: `build_report_view` returns per-run cards

**Files:**
- Modify: `shared/reporting/dashboard_views.py` (`build_report_view`, replace/retire matrix helpers as needed)
- Modify: `tests/test_dashboard_views.py`
- Test: `tests/test_dashboard_views.py`

**Interfaces:**
- Consumes: `FilterState`, catalog with `comparison.runs`, `comparison.models` (labels), `comparison.tracks`; `run_key`; `_format_promptfoo_cell`, `_format_deepeval_cell`, `_format_ragas_cell`
- Produces: `build_report_view(filters, catalog) -> dict` with keys:
  - `runs: list[dict]` each: `model`, `temp_tag`, `temperature: float`, `label`, `frameworks: {promptfoo|deepeval|ragas: list[track_row]}`
  - `track_row` for promptfoo/deepeval: `{dataset, pass, fail, total, rate, missing, value, level}`
  - `track_row` for ragas: `{dataset, missing, value, rate, level}` (`value` from `_format_ragas_cell`)
  - `scope`, `generated_at`, `track_count` (unique datasets across filtered tracks)
  - **No** `tables` key

- [ ] **Step 1: Replace old report view tests with failing ones**

In `tests/test_dashboard_views.py`, replace `test_build_report_short_titles` and `test_build_report_view_filters_columns` with:

```python
def test_build_report_view_returns_runs():
    catalog = {
        "generated_at": "2026-01-01",
        "scope": {"mode": "portfolio"},
        "comparison": {
            "models": ["bonsai (t0.2)"],
            "runs": [{"model": "bonsai", "temp_tag": "t0.2"}],
            "tracks": [
                {
                    "dataset": "sciq",
                    "models": {
                        "bonsai (t0.2)": {
                            "promptfoo": {"pass": 5, "fail": 5, "total": 10, "pass_rate": 0.5},
                            "deepeval": {"pass": 9, "fail": 1, "total": 10, "pass_rate": 0.9},
                            "ragas": {"averages": {"faithfulness": 0.8, "answer_relevancy": 0.7}},
                        },
                    },
                }
            ],
        },
    }
    filters = FilterState(
        models=["bonsai"], temps=["t0.2"], dataset="all",
        frameworks=["promptfoo", "deepeval", "ragas"],
    )
    view = build_report_view(filters, catalog)
    assert "tables" not in view
    assert len(view["runs"]) == 1
    run = view["runs"][0]
    assert run["model"] == "bonsai"
    assert run["temp_tag"] == "t0.2"
    assert run["temperature"] == 0.2
    assert run["label"] == "bonsai · t=0.2"
    assert set(run["frameworks"]) == {"promptfoo", "deepeval", "ragas"}
    pf = run["frameworks"]["promptfoo"][0]
    assert pf["dataset"] == "sciq"
    assert pf["pass"] == 5
    assert pf["missing"] is False
    assert pf["rate"] == 50.0


def test_build_report_view_filters_runs_and_datasets():
    catalog = {
        "generated_at": "2026-01-01",
        "comparison": {
            "models": ["bonsai (t0.2)", "qwen27 (t0.2)", "bonsai (t0.7)"],
            "runs": [
                {"model": "bonsai", "temp_tag": "t0.2"},
                {"model": "qwen27", "temp_tag": "t0.2"},
                {"model": "bonsai", "temp_tag": "t0.7"},
            ],
            "tracks": [
                {
                    "dataset": "sciq",
                    "models": {
                        "bonsai (t0.2)": {"promptfoo": {"pass": 5, "fail": 5, "total": 10, "pass_rate": 0.5}},
                        "qwen27 (t0.2)": {"promptfoo": {"pass": 8, "fail": 2, "total": 10, "pass_rate": 0.8}},
                        "bonsai (t0.7)": {"promptfoo": {"pass": 6, "fail": 4, "total": 10, "pass_rate": 0.6}},
                    },
                },
                {
                    "dataset": "uda_qa",
                    "models": {
                        "bonsai (t0.2)": {"promptfoo": {"pass": 1, "fail": 1, "total": 2, "pass_rate": 0.5}},
                    },
                },
            ],
        },
    }
    filters = FilterState(
        models=["bonsai"], temps=["t0.2"], dataset="sciq",
        frameworks=["promptfoo", "deepeval", "ragas"],
    )
    view = build_report_view(filters, catalog)
    assert [r["label"] for r in view["runs"]] == ["bonsai · t=0.2"]
    assert [row["dataset"] for row in view["runs"][0]["frameworks"]["promptfoo"]] == ["sciq"]
    # Tabs always present even if framework filter would have dropped matrix tables before
    assert "deepeval" in view["runs"][0]["frameworks"]
    assert "ragas" in view["runs"][0]["frameworks"]
```

Keep `test_report_cell_levels` if `_report_cell` remains; if you replace it with `_framework_track_row`, update that test to call the new helper instead.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_dashboard_views.py::test_build_report_view_returns_runs tests/test_dashboard_views.py::test_build_report_view_filters_runs_and_datasets -q`

Expected: FAIL (KeyError `tables` or missing `runs` shape / assertion on `tables`)

- [ ] **Step 3: Implement `build_report_view`**

Replace `build_report_view` in `shared/reporting/dashboard_views.py` with logic equivalent to:

```python
def _temp_from_tag(temp_tag: str) -> float:
    return float(temp_tag.removeprefix("t"))


def _framework_track_row(fw_key: str, dataset: str, raw: dict | None) -> dict:
    formatted = {
        "promptfoo": _format_promptfoo_cell,
        "deepeval": _format_deepeval_cell,
        "ragas": _format_ragas_cell,
    }[fw_key](raw)
    cell = _report_cell(fw_key, raw, formatted)
    row = {
        "dataset": dataset,
        "missing": cell["missing"],
        "value": cell["value"],
        "rate": cell.get("rate"),
        "level": cell.get("level", "missing"),
    }
    if fw_key in ("promptfoo", "deepeval"):
        if raw:
            total = int(raw.get("total") or 0)
            passed = int(raw.get("pass") or 0)
            fail = int(raw["fail"]) if raw.get("fail") is not None else max(total - passed, 0)
            row.update({"pass": passed, "fail": fail, "total": total})
        else:
            row.update({"pass": None, "fail": None, "total": None})
    return row


def build_report_view(filters: FilterState, catalog: dict) -> dict:
    comparison = catalog.get("comparison") or {}
    runs_meta = comparison.get("runs") or []
    all_labels = comparison.get("models") or []
    all_tracks = comparison.get("tracks") or []
    tracks = [t for t in all_tracks if filters.matches_dataset(t["dataset"])]

    runs = []
    for meta, label in zip(runs_meta, all_labels):
        model = meta["model"]
        temp_tag = meta["temp_tag"]
        if not filters.matches_run(model, temp_tag):
            continue
        frameworks = {}
        for fw in ("promptfoo", "deepeval", "ragas"):
            rows = []
            for track in tracks:
                raw = (track.get("models") or {}).get(label, {}).get(fw)
                # Framework filter: still emit rows, but mark missing if fw filtered out
                if not filters.includes_framework(fw):
                    raw = None
                rows.append(_framework_track_row(fw, track["dataset"], raw))
            frameworks[fw] = rows
        runs.append(
            {
                "model": model,
                "temp_tag": temp_tag,
                "temperature": _temp_from_tag(temp_tag),
                "label": f"{model} · t={temp_tag.removeprefix('t')}",
                "frameworks": frameworks,
            }
        )

    runs.sort(key=lambda r: (r["model"], r["temperature"]))
    return {
        "runs": runs,
        "scope": catalog.get("scope") or {},
        "track_count": len(tracks),
        "generated_at": catalog.get("generated_at"),
    }
```

Notes:
- Do not return `tables` or column-oriented `models` list.
- Keep `_report_cell` for level/rate derivation unless you fold it into `_framework_track_row` and update `test_report_cell_levels`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_dashboard_views.py -q`

Expected: PASS (all tests in file)

- [ ] **Step 5: Commit**

```bash
git add shared/reporting/dashboard_views.py tests/test_dashboard_views.py
git commit -m "$(cat <<'EOF'
Reshape report view into per-run framework track cards.

Replace the comparison-matrix view model with (model, temp) runs so the Report UI can render one card per run.
EOF
)"
```

---

### Task 2: Report partial — run cards + in-card eval tabs

**Files:**
- Modify: `web/partials/report.html` (full rewrite)
- Modify: `tests/test_dashboard_api.py`
- Test: `tests/test_dashboard_api.py`

**Interfaces:**
- Consumes: `view.runs` from Task 1; Alpine on body already calls `Alpine.initTree` after HTMX swap
- Produces: HTML with `.run-card`, per-card `panel-seg`, Export button markup

- [ ] **Step 1: Write failing HTML assertions**

Add to `tests/test_dashboard_api.py`:

```python
def test_report_partial_has_run_cards():
    client = TestClient(create_app())
    r = client.get("/partials/report")
    assert r.status_code == 200
    html = r.text
    assert "No runs for current filters" in html or "run-card" in html
    if "run-card" in html:
        assert "Export profile YAML" in html
        assert 'x-data="{ fw:' in html or "x-data=\"{ fw:" in html
        assert "Promptfoo" in html and "DeepEval" in html and "RAGAS" in html
```

Update `test_report_panel` if it still assumes old `panel=promptfoo` matrix nav — change to assert run-card content still loads with `?panel=` ignored or unused:

```python
def test_report_partial_ignores_legacy_panel_param():
    client = TestClient(create_app())
    r = client.get("/partials/report?panel=promptfoo")
    assert r.status_code == 200
    assert "tables" not in r.text  # loose; prefer:
    assert "aria-label=\"Report frameworks\"" not in r.text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_dashboard_api.py::test_report_partial_has_run_cards -q`

Expected: FAIL (no `run-card` / Export on report)

- [ ] **Step 3: Rewrite `web/partials/report.html`**

```jinja
{% if view.runs %}
<p class="meta">
  Generated {{ view.generated_at or '—' }}
  · {{ view.runs|length }} run(s)
  · {{ view.track_count }} track(s)
</p>

{% for run in view.runs %}
<section class="card wide run-card" x-data="{ fw: 'promptfoo' }">
  <div class="run-group-header">
    <h3>{{ run.label }}</h3>
    <button class="btn secondary"
            type="button"
            data-model="{{ run.model }}"
            data-temperature="{{ run.temperature }}"
            @click="exportRunProfile($event)">
      Export profile YAML
    </button>
    <span class="meta" data-run-export-status aria-live="polite"></span>
  </div>

  <nav class="panel-seg" aria-label="Eval frameworks for {{ run.label }}">
    <button type="button" class="panel-seg-btn" :class="fw === 'promptfoo' && 'active'" @click="fw = 'promptfoo'">Promptfoo</button>
    <button type="button" class="panel-seg-btn" :class="fw === 'deepeval' && 'active'" @click="fw = 'deepeval'">DeepEval</button>
    <button type="button" class="panel-seg-btn" :class="fw === 'ragas' && 'active'" @click="fw = 'ragas'">RAGAS</button>
  </nav>

  {% for fw_key, fw_label in [('promptfoo','Promptfoo'), ('deepeval','DeepEval'), ('ragas','RAGAS')] %}
  <div x-show="fw === '{{ fw_key }}'" x-cloak>
    {% set rows = run.frameworks[fw_key] %}
    {% if rows %}
    <div class="table-scroll">
      <table class="compare-table sticky-head">
        <thead>
          <tr>
            <th>Track</th>
            {% if fw_key != 'ragas' %}
            <th>Pass</th><th>Fail</th><th>Total</th><th>Rate</th>
            {% else %}
            <th>Scores</th>
            {% endif %}
          </tr>
        </thead>
        <tbody>
          {% for row in rows %}
          <tr>
            <td class="track"><span class="tag">{{ row.dataset }}</span></td>
            {% if fw_key != 'ragas' %}
            <td class="{{ 'missing' if row.missing else 'pass' }}">{{ '—' if row.missing else row.pass }}</td>
            <td class="{{ 'missing' if row.missing else '' }}">{{ '—' if row.missing else row.fail }}</td>
            <td class="{{ 'missing' if row.missing else '' }}">{{ '—' if row.missing else row.total }}</td>
            <td class="{{ 'missing' if row.missing else '' }}">{{ '—' if row.missing else row.value }}</td>
            {% else %}
            <td class="{{ 'missing' if row.missing else '' }}">{{ row.value }}</td>
            {% endif %}
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
    {% else %}
    <p class="empty">No {{ fw_label }} tracks for this run.</p>
    {% endif %}
  </div>
  {% endfor %}
</section>
{% endfor %}
{% else %}
<p class="empty">No runs for current filters.</p>
{% endif %}
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/test_dashboard_api.py::test_report_partial_has_run_cards tests/test_dashboard_api.py::test_report_partial_ignores_legacy_panel_param tests/test_dashboard_api.py::test_report_partial -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web/partials/report.html tests/test_dashboard_api.py
git commit -m "$(cat <<'EOF'
Render Report as per-run cards with in-card eval tabs.

Show Promptfoo/DeepEval/RAGAS dataset rows inside each (model, temp) card instead of a global comparison matrix.
EOF
)"
```

---

### Task 3: Per-run export JS + remove Overview export

**Files:**
- Modify: `web/static/app.js`
- Modify: `web/partials/overview.html`
- Modify: `tests/test_dashboard_api.py`
- Modify: `README.md` (Dashboard / profiles blurb)
- Test: `tests/test_dashboard_api.py`

**Interfaces:**
- Consumes: `POST /api/profiles/export` (`ProfileExportPayload`)
- Produces: `exportRunProfile(event)` reading `data-model`, `data-temperature` from the button; optional Track filter from `this.filters.dataset`

- [ ] **Step 1: Write failing tests**

```python
def test_overview_has_no_export_profile_button():
    client = TestClient(create_app())
    r = client.get("/partials/overview")
    assert r.status_code == 200
    assert "Export profile YAML" not in r.text
    assert "Import profile YAML" in r.text


def test_export_profile_single_run_overrides(monkeypatch):
    monkeypatch.setenv("EVAL_DATASET", "sciq")
    monkeypatch.setenv("MODEL", "qwen27")
    monkeypatch.setenv("TARGET_TEMPERATURE", "0.9")
    client = TestClient(create_app())
    r = client.post(
        "/api/profiles/export",
        json={"name": "bonsai-t0.7", "models": ["bonsai"], "temperature": 0.7},
    )
    assert r.status_code == 200
    yaml_text = r.json()["yaml"]
    assert "id: bonsai" in yaml_text
    assert "temperature: 0.7" in yaml_text
    assert "qwen27" not in yaml_text
```

Remove or rewrite `test_overview_has_export_profile_button` if it still expects Export on Overview.

- [ ] **Step 2: Run tests to verify fail**

Run: `.venv/bin/python -m pytest tests/test_dashboard_api.py::test_overview_has_no_export_profile_button -q`

Expected: FAIL (`Export profile YAML` still present)

- [ ] **Step 3: Update Overview + JS**

In `web/partials/overview.html` Setup section:
- Delete the Export profile button.
- Set copy to: `Import a shareable run profile or download an example model. Export a run recipe from the Report tab.`

In `web/static/app.js`:
- Keep `exportProfileYaml` **or** replace with `exportRunProfile` used by Report cards.
- Implement:

```javascript
async exportRunProfile(event) {
  const button = event.currentTarget;
  const status =
    button.parentElement?.querySelector("[data-run-export-status]") ||
    document.getElementById("profile-action-status");
  const model = button.dataset.model;
  const temperature = Number.parseFloat(button.dataset.temperature);
  if (!status || !model || Number.isNaN(temperature)) return;

  const dataset =
    this.filters.dataset && this.filters.dataset !== "all"
      ? this.filters.dataset
      : null;
  const stamp = new Date().toISOString().slice(0, 10);
  const name = [model, `t${temperature}`, dataset, stamp].filter(Boolean).join("-");

  button.disabled = true;
  status.textContent = "Exporting…";
  try {
    const response = await fetch("/api/profiles/export", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name,
        models: [model],
        temperature,
        dataset,
      }),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.message || "Export failed");
    }
    const blob = new Blob([data.yaml], { type: "text/yaml;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = data.filename || `${name}.yaml`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    status.textContent = data.message || "Exported";
  } catch (error) {
    status.textContent = error instanceof Error ? error.message : "Export failed";
  } finally {
    button.disabled = false;
  }
},
```

- Remove Overview `@click="exportProfileYaml..."`.
- If `exportProfileYaml` is unused, delete it.

README: replace Overview export sentence with: Report shows one card per `(model, temperature)` with eval tabs; **Export profile YAML** on a card downloads that run’s recipe.

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/test_dashboard_api.py tests/test_dashboard_views.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web/static/app.js web/partials/overview.html tests/test_dashboard_api.py README.md
git commit -m "$(cat <<'EOF'
Move profile export onto Report run cards.

Remove Overview export and wire each run card to export an explicit model/temperature recipe.
EOF
)"
```

---

### Task 4: Smoke check + leftover cleanup

**Files:**
- Modify only if needed: `scripts/dashboard_api.py` (if report route still passes unused `panel`), `web/static/app.css` (`.run-card` spacing if header cramped)

**Interfaces:**
- Consumes: Tasks 1–3
- Produces: green suite; optional tiny CSS polish

- [ ] **Step 1: Grep for leftover matrix assumptions**

Run: `rg -n "view\\.tables|short_title|Report frameworks|exportProfileYaml|Export profile YAML" web tests shared/reporting/dashboard_views.py README.md`

Expected: Export only under `report.html`; no `view.tables` consumers; no Overview Export.

- [ ] **Step 2: Full related test run**

Run: `.venv/bin/python -m pytest tests/test_dashboard_api.py tests/test_dashboard_views.py tests/test_profiles.py -q`

Expected: PASS

- [ ] **Step 3: Manual smoke (if dashboard running)**

Hard-refresh → Report → confirm run cards, tab switches, Export downloads YAML with that model/temp → Overview Setup has Import/Download only.

- [ ] **Step 4: Commit only if cleanup edits were made**

```bash
git add -u
git commit -m "$(cat <<'EOF'
Polish Report per-run card leftovers.

Drop unused panel wiring and tighten run-card layout after the Report reshape.
EOF
)"
```

Skip this commit if the working tree is clean.

---

## Spec coverage (self-review)

| Spec requirement | Task |
|------------------|------|
| Run = `(model, temp)` cards | Task 1–2 |
| In-card Promptfoo/DeepEval/RAGAS tabs | Task 2 |
| Pass/fail (RAGAS scores) rows | Task 1–2 |
| Remove comparison matrix | Task 1–2 |
| Export profile on card | Task 2–3 |
| Remove Overview export | Task 3 |
| Reuse `/api/profiles/export` | Task 3 |
| Tabs always present | Task 1 (frameworks always keyed) + Task 2 |
| Filters apply | Task 1 |
| README sentence | Task 3 |
| Tests listed in spec | Tasks 1–3 |

## Placeholder scan

No TBD/TODO steps; code blocks are concrete.

## Type consistency

- View key is `runs` / `frameworks` / `temp_tag` / `temperature` throughout Tasks 1–3.
- JS uses `exportRunProfile` + `data-model` / `data-temperature`.
- API payload fields remain `name`, `models`, `temperature`, `dataset`.
