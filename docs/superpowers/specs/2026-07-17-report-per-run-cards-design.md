# Report per-run cards + profile export

**Date:** 2026-07-17  
**Status:** Approved for planning (brainstorming complete)

## Goal

Replace the Report tab’s cross-model comparison matrix with a **per-run** layout: one card per `(model, temperature)`, with in-card eval tabs (Promptfoo / DeepEval / RAGAS) showing dataset pass/fail for that run only. Move **Export profile YAML** from Overview Setup onto each run card; remove the Overview export button.

## Decisions (locked)

| Topic | Choice |
|-------|--------|
| Run identity | `(model, temperature)` / `temp_tag` (e.g. `bonsai` + `t0.7`) |
| Report layout | List of run cards; no tracks×models comparison matrix |
| In-card tabs | Promptfoo · DeepEval · RAGAS → dataset rows with pass/fail (or `—`) |
| Export | Profile YAML recipe only (not results snapshot) |
| Overview Export | Removed; Import + Download model remain in Setup |
| Implementation | Server-rendered cards + Alpine `x-show` for in-card tabs (approach 1) |

## Non-goals

- Exporting results JSON / artifact bundles per run
- Keeping a Compare mode on the Report tab
- New profile schema fields
- Changing CLI `make profile-export` behavior (still env-based)
- Redesigning DeepEval / RAGAS / Promptfoo dedicated tabs (they stay as-is)

## UX

### Report

1. Filters (header) still apply: models, temps, dataset, frameworks.
2. Main content is a vertical list of **run cards**, sorted stably (model, then temp).
3. Each card shows:
   - Title: `{model} · t={temp}` (humanized from `temp_tag`)
   - Short meta: e.g. track count / which frameworks have data
   - Button: **Export profile YAML**
   - `panel-seg`: Promptfoo | DeepEval | RAGAS (same visual language as other in-page panels)
   - Active tab body: table of datasets for that framework:
     - Promptfoo / DeepEval: pass / fail / total / rate (or `—` if missing)
     - RAGAS: existing score summary (faithfulness · relevancy via current formatters), or `—` if missing
4. Empty filters result: single empty state — “No runs for current filters.”
5. All three framework tabs are **always** shown on every card for a predictable UI. Dataset/framework filters only change which rows have data (may be empty / all `—`).

### Overview Setup

- Remove **Export profile YAML** button and its JS wiring from the Overview Setup row.
- Keep **Import profile YAML** and **Download model (example profile)**.
- Copy may say that run recipes are exported from the Report tab.

## Data model

`build_report_view(filters, catalog) -> view` returns roughly:

```text
{
  runs: [
    {
      model: str,
      temp_tag: str,          # e.g. "t0.7"
      temperature: float,     # e.g. 0.7
      label: str,             # "bonsai · t=0.7"
      frameworks: {
        promptfoo: [ { dataset, pass, fail, total, rate, missing } ],
        deepeval:  [ ... ],
        ragas:     [ ... ],
      }
    },
    ...
  ]
}
```

### Derivation rules

- Scan the same on-disk artifacts used today (`results/promptfoo|deepeval|ragas/...` via existing parsers / combined report helpers).
- Group by `run_key(model, temp_tag)` (existing helper).
- Apply `FilterState.matches_run` for model/temp; apply dataset filter to track rows; framework filter does not remove the run card, only affects whether that framework’s rows have data (tabs remain).
- Prefer reusing cell formatters from `combined_report` / score helpers so rates match other views.
- Do **not** build the old `tables` comparison matrices for this view. Callers/tests that asserted matrix shape must be updated.

### Profile export from a card

Reuse `POST /api/profiles/export` (no new endpoint required).

Request body from the card:

- `name`: derived, e.g. `{model}-{temp_tag}-{date}` (sanitized server-side as today)
- `models`: `[model]` for that card only
- `temperature`: card’s float temperature
- `dataset`: current Track filter if not `all`; otherwise omit (limits / judge still come from `.env` / `.env.profile` via `export_profile_from_env`)

Secrets remain forbidden in the body (existing checks).

## Frontend

- Rewrite `web/partials/report.html` for run cards.
- Per card: `x-data="{ fw: 'promptfoo' }"` (or equivalent) + `panel-seg` buttons setting `fw`; tab panels use `x-show` / `x-cloak` as needed.
- Wire Export to existing `exportProfileYaml` **or** a thin variant that accepts explicit `{ models, temperature, dataset }` from `data-*` attributes on the button (do not use the global multi-select filter models list for this action).
- After HTMX swap, Alpine `initTree` on `#main-content` already runs — card `x-data` must work under that.

## Testing

- Unit/view: `build_report_view` returns `runs` with framework track lists; filtered model/temp reduces cards; dataset filter reduces rows.
- API/HTML: `/partials/report` contains run-card markup and per-card Export control; no comparison `panel-seg` for frameworks-as-global-nav.
- Overview: no “Export profile YAML” on `/partials/overview`.
- Existing `/api/profiles/export` tests remain; add one test that override `models` + `temperature` match a single-run export (if not already covered).

## Docs

- README: one sentence — Report lists per-run cards with eval tabs; export profile from a run card.

## Out of scope follow-ups (explicit)

- Per-run results download
- Restoring a portfolio compare matrix elsewhere
- Unifying DeepEval tab UI with this new Report card pattern
