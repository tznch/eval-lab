# Publish-ready repo + shareable run profiles

Date: 2026-07-16  
Status: approved for planning

## Goal

Prepare this repository for **public open-source** publication (MIT) and add a **lean MVP** for sharing eval setups: YAML profiles (run recipe + Hugging Face / GGUF model refs) with CLI export/import, plus a minimal dashboard button to download a model from a profile. Also provide a simple **package sync** command to update eval tools (RAGAS, DeepEval, Promptfoo, and related Python deps). Secrets stay local; no machine-specific hardware docs.

## Non-goals

- CONTRIBUTING, CI, or GitHub Actions in this cycle
- Committing `results/`, raw/processed data, GGUF weights, or demo screenshots
- Dashboard UI to enter or store Hugging Face / API keys (keys remain in `.env` only)
- Full profile editor / picker UX on the dashboard
- Hardware recommendations or “this machine” setup sections in README
- Git clone/submodule/`git pull` of upstream eval-tool repositories (tools stay package-managed)

## Decisions (locked)

| Topic | Choice |
|-------|--------|
| Visibility | Public open-source |
| License | MIT (copyright placeholder `YOUR_NAME` until the author edits it) |
| Local artifacts | Keep out of git (large CSV, screenshots, caches, env, models, results) |
| Hardware docs | None — every user has different hardware |
| Profile content | Run recipe **plus** HF/GGUF model refs (option B) |
| Dashboard in this cycle | One **Download model (from profile)** action; HF token from `.env` only |
| Eval tool updates | Package sync only (`uv pip` / `npm`) — not git pull of tool repos |
| Approach | Lean public kit + YAML profiles + thin dashboard hook |

## 1. Publish-ready packaging

### 1.1 `.gitignore`

Expand ignore rules so a fresh `git status` after `git init` only shows source, manifests, docs, and examples. At minimum cover:

- Secrets: `.env` (keep `.env.example` tracked)
- Python / tooling: `.venv/`, `__pycache__/`, `*.pyc`, `*.egg-info/`, `.pytest_cache/`, `.ruff_cache/`, `dist/`
- Eval / agent caches: `results/`, `.promptfoo/`, `.deepeval/`, `.playwright-mcp/`, `.superpowers/` (local SDD progress only; **tracked** design specs under `docs/superpowers/` stay)
- Data & weights: `data/raw/`, `data/processed/`, `data/models/`, `*.gguf`
- Generated dataset samples when heavy/local: `datasets/*/samples.jsonl` (keep `datasets/*/dataset.yaml` and `_template/`)
- Root clutter: large training CSV(s), ad-hoc `promptfoo-summaries-*.png` (or `*.png` at repo root)
- IDE / OS: `.idea/`, `.vscode/` (optional local), `.DS_Store`, `Thumbs.db`

### 1.2 License

Add root `LICENSE` (MIT) with:

```text
Copyright (c) 2026 YOUR_NAME
```

Author replaces `YOUR_NAME` before or after the first public push.

### 1.3 README and package metadata

- Remove **Minipc setup** and any host-specific paths, CPU/RAM tables, or “this machine” language.
- Do **not** add generic hardware sizing guidance either.
- Document: clone → `.env.example` → `.env` → `make setup` → profiles → lab/dashboard.
- Point to `docs/reproduce-run.md` for reproduction without implying one fixed machine.
- Update `pyproject.toml` `description` to match the multi-dataset lab (not UDA-QA-only).

### 1.4 Git bootstrap

- Repository already has `git init` (design-spec root commit). Further commits follow implementation and user request.
- Creating a GitHub remote / `gh repo create` is **out of band** until the user provides name/org.

### 1.5 Eval tool updates (package sync)

Users need a one-command way to refresh eval frameworks without managing upstream git checkouts.

- Add `make tools-update` (and a thin script if useful) that:
  1. Upgrades project Python deps in `.venv` with `uv pip install -U -e ".[dev]"` (or equivalent: upgrade `ragas`, `deepeval`, and other declared deps from `pyproject.toml`).
  2. Upgrades Promptfoo via `npm install -g promptfoo@latest` (same channel as `make setup`).
- Print installed versions after update (e.g. `python -c` / `promptfoo --version`) so users can record them alongside a shared profile.
- Do **not** pin a lockfile in this cycle unless one already exists; document that `tools-update` moves to latest compatible releases and may change scores.
- Optional: mention in README that for bit-exact reproduction, pin versions manually after a known-good run — full lockfile workflow is a later improvement.
- Out of scope here: dashboard button for tools-update; separate git remotes for RAGAS/DeepEval/Promptfoo source trees.

## 2. Shareable run profiles

### 2.1 Purpose

A profile is a **portable, secret-free** description of “what to run and which models to fetch,” so one person can share a file and another can import it on a clone of this repo and reproduce the same eval recipe (subject to their own API keys and local `llama-server`).

### 2.2 Location and format

- Directory: `profiles/`
- Examples: `profiles/examples/*.yaml` (tracked)
- User-created profiles: gitignore `profiles/*.yaml` but keep `profiles/examples/` tracked, so personal experiments stay local unless the user force-adds a file to share in-repo.

YAML shape (MVP):

```yaml
name: bonsai-sciq-t07
dataset: sciq
temperature: 0.7
models:
  - id: bonsai
    hf_repo: prism-ml/Bonsai-27B-gguf
    quant: Q1_0
    # optional local layout hint for download scripts
    gguf_hint: data/models/bonsai-27b-q1/
limits:
  promptfoo: 25
  deepeval: 25
  ragas: 25
judge_model: tencent/hy3:free   # optional; id only, no API key
```

**Must never appear in a profile:** `OPENROUTER_API_KEY`, `zai_api_key`, `HF_TOKEN`, `HF_FULL_ACCESS`, or any other secret.

### 2.3 CLI

- `make profile-export NAME=...` — write a profile from current non-secret env/defaults (dataset, temperature, limits, model ids + known HF refs from a small registry).
- `make profile-import PROFILE=profiles/foo.yaml` — validate YAML; apply non-secret overrides for subsequent commands (documented mechanism: print exportable env block and/or write a local gitignored overlay such as `.env.profile` that scripts already honor, without merging secrets into `.env`).
- Import also prints the download command(s) implied by `models[].hf_repo` / `quant`.
- Prefer reusing existing `scripts/download_*.py` / registry mapping (`bonsai`, `qwen27`, …) rather than inventing a second download stack. Unknown `hf_repo` may call a thin generic HF download helper if one already fits; otherwise fail with a clear message listing supported ids for MVP.

### 2.4 Validation

- Required: `name`, `dataset`, at least one `models[].id`.
- Reject profiles that contain known secret key names.
- Unknown fields: warn once per field name, then ignore (do not fail the import).

## 3. Dashboard: download from profile

### 3.1 UX

- On overview (or performance): button **Download model (from profile)**.
- MVP selection: profile path/name via query/body (e.g. default `profiles/examples/...` or a single configured active profile). Full profile browser is out of scope.
- UI shows simple status: started / success / error (no log streaming required).

### 3.2 API

- `POST /api/models/download` with JSON `{ "profile": "profiles/examples/....yaml", "model_id": "bonsai" }` (model_id optional if profile has one model).
- Server reads HF credentials only from process environment / `.env` (existing `shared.hf_auth` / env loading).
- Response JSON: `{ "ok": bool, "message": str, ... }`.
- Downloads are local filesystem writes under `data/models/` (already gitignored).

### 3.3 Safety

- Do not accept raw tokens in the request body.
- Do not expose `.env` contents via any API.
- Bound work to known download helpers; do not shell out to arbitrary URLs from profile without going through the HF hub helper.

## 4. Components (summary)

| Unit | Responsibility |
|------|----------------|
| `.gitignore` / `LICENSE` / README / `pyproject.toml` | Public packaging |
| `profiles/examples/*.yaml` | Canonical shareable recipes |
| Profile load/validate/export module (under `shared/` or `scripts/`) | Schema + secret scrubbing |
| Make targets + thin scripts | User-facing CLI (`profile-*`, `tools-update`) |
| Dashboard route + button | Trigger download using profile + `.env` HF token |
| Existing download scripts | Actual weight fetch |
| `make tools-update` | Upgrade RAGAS / DeepEval / Promptfoo via packages |

## 5. Error handling

- Missing HF token when download needs auth: clear error pointing to `.env.example` (`HF_TOKEN`).
- Invalid / secret-bearing profile: refuse import and download with explicit reason.
- Unsupported model id / repo: refuse with list of MVP-supported mappings.
- Dashboard download failure: HTTP 4xx/5xx + `message` for UI.

## 6. Testing

- Unit tests: profile parse/validate; reject secret keys; export omits secrets.
- Unit/API test: download endpoint rejects body with token fields; missing profile → 404/400.
- No network-heavy download tests in CI-less MVP (optional mock of download function).

## 7. Documentation touchpoints

- README: profiles section (export, import, share file, dashboard download); `make tools-update` for eval frameworks.
- `.env.example`: unchanged secret keys; optional comment that profiles never replace keys.
- Short note in `docs/reproduce-run.md` that a shared profile is the preferred way to align dataset/temp/models, and that tool versions come from package sync (record versions after `tools-update`).

## Success criteria

1. After ignore rules are applied, secrets and large local artifacts are not candidates for commit.
2. A stranger can follow README without any host-specific hardware section.
3. Author can export a profile, share the YAML; another clone can import it and run the same recipe with their own `.env`.
4. Dashboard can start a model download for a profile model using HF token from `.env` only.
5. MIT `LICENSE` present with editable `YOUR_NAME` placeholder.
6. `make tools-update` upgrades Python eval deps and Promptfoo via packages and prints versions.
