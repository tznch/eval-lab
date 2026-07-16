# Publish-ready repo + share profiles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the repo safe to publish publicly (ignore, MIT, README) and add secret-free YAML run profiles with CLI export/import, package-based eval tool updates, and a dashboard button to download a model from a profile.

**Architecture:** Expand packaging files first. Add `shared/profiles/` for YAML load/validate/export plus a small model→download registry that reuses existing `scripts/download_*.py`. Import writes gitignored `.env.profile` (non-secrets only); `shared/config.py` loads `.env` then `.env.profile`. Dashboard `POST /api/models/download` calls the same download dispatcher. `make tools-update` upgrades pip/npm packages and prints versions.

**Tech Stack:** Python 3.11+, PyYAML, FastAPI TestClient, Make, uv pip, npm (promptfoo), existing HuggingFace download scripts.

## Global Constraints

- Public open-source; MIT license with copyright placeholder `YOUR_NAME`.
- Profiles must never contain secrets (`OPENROUTER_API_KEY`, `zai_api_key`, `HF_TOKEN`, `HF_FULL_ACCESS`, `HUGGING_FACE_HUB_TOKEN`).
- No hardware / minipc / host-specific docs in README.
- Eval tool updates via packages only — not git pull of upstream tool repos.
- Dashboard download uses HF token from `.env` only — never from request body.
- User-created `profiles/*.yaml` gitignored; `profiles/examples/` tracked.
- Do not commit `.env`, `results/`, GGUF weights, root CSV, or screenshot clutter.
- Only commit when a plan step says to commit (or the user asks).

## File structure

| Path | Responsibility |
|------|----------------|
| `.gitignore` | Keep secrets, caches, data, weights, local profiles out of git |
| `LICENSE` | MIT text with `YOUR_NAME` |
| `README.md` / `pyproject.toml` / `docs/reproduce-run.md` / `.env.example` | Public docs + metadata |
| `shared/env_files.py` | Load `.env` then `.env.profile` |
| `shared/profiles/__init__.py` | Public exports |
| `shared/profiles/schema.py` | Dataclasses + secret key set + validate |
| `shared/profiles/io.py` | Load/save YAML, export from env, write `.env.profile` |
| `shared/profiles/registry.py` | Known model id → HF repo / download callable |
| `shared/profiles/download.py` | Dispatch download for profile model |
| `scripts/profile_cli.py` | argparse export/import |
| `scripts/tools_update.sh` | uv pip + npm upgrade + print versions |
| `profiles/examples/bonsai-sciq-t07.yaml` | Example shareable profile |
| `Makefile` | `profile-export`, `profile-import`, `tools-update` |
| `scripts/dashboard_api.py` | `POST /api/models/download` |
| `web/partials/overview.html` + `web/static/app.js` | Download button + status |
| `tests/test_profiles.py` | Profile validate/export/secrets |
| `tests/test_dashboard_api.py` | Download endpoint safety |

---

### Task 1: Publish-ready ignore + LICENSE

**Files:**
- Modify: `.gitignore`
- Create: `LICENSE`
- Test: manual `git status` / `git check-ignore`

**Interfaces:**
- Consumes: none
- Produces: ignore rules that exclude `.env`, `.venv/`, `results/`, `data/raw/`, `data/processed/`, `data/models/`, `*.gguf`, `.playwright-mcp/`, `.deepeval/`, `.superpowers/`, `datasets/*/samples.jsonl`, `profiles/*.yaml` (not `profiles/examples/`), root `*.png`, `bitext-retail-*.csv`, IDE/OS junk

- [ ] **Step 1: Replace `.gitignore` with:**

```gitignore
# Secrets
.env
.env.profile

# Python / tooling
__pycache__/
*.pyc
.venv/
*.egg-info/
.pytest_cache/
.ruff_cache/
dist/

# Eval / agent caches
results/
.promptfoo/
.deepeval/
.playwright-mcp/
.superpowers/

# Data & weights
data/raw/
data/processed/
data/models/
*.gguf

# Generated samples (manifests stay tracked)
datasets/*/samples.jsonl

# Local profiles (examples/ stay tracked)
profiles/*
!profiles/examples/
!profiles/examples/**

# Root clutter
bitext-retail-*.csv
/*.png

# IDE / OS
.idea/
.vscode/
.DS_Store
Thumbs.db
node_modules/
```

- [ ] **Step 2: Create `LICENSE` (MIT) with copyright line `Copyright (c) 2026 YOUR_NAME`.**

Use the standard MIT license body from https://opensource.org/licenses/MIT (full permission notice + warranty disclaimer).

- [ ] **Step 3: Verify ignores**

Run:

```bash
git check-ignore -v .env results/.gitkeep data/models/x.gguf .playwright-mcp/foo profiles/my.yaml profiles/examples/bonsai-sciq-t07.yaml 2>/dev/null || true
mkdir -p profiles/examples
touch profiles/examples/bonsai-sciq-t07.yaml profiles/local.yaml
git check-ignore -v profiles/local.yaml
git check-ignore -v profiles/examples/bonsai-sciq-t07.yaml || echo "examples NOT ignored (expected)"
```

Expected: `.env`, local profile ignored; `profiles/examples/...` not ignored (or only parent rule negated).

- [ ] **Step 4: Commit**

```bash
git add .gitignore LICENSE
git commit -m "$(cat <<'EOF'
Add MIT license and tighten gitignore for public publish.

EOF
)"
```

---

### Task 2: Profile schema + validation (TDD)

**Files:**
- Create: `shared/profiles/__init__.py`
- Create: `shared/profiles/schema.py`
- Create: `tests/test_profiles.py`
- Modify: `pyproject.toml` (ensure `pyyaml` already listed — it is)

**Interfaces:**
- Consumes: none
- Produces:
  - `SECRET_KEYS: frozenset[str]`
  - `@dataclass ProfileModelSpec` with fields `id: str`, `hf_repo: str | None = None`, `quant: str | None = None`, `gguf_hint: str | None = None`
  - `@dataclass ProfileLimits` with `promptfoo: int = 25`, `deepeval: int = 25`, `ragas: int = 25`
  - `@dataclass RunProfile` with `name: str`, `dataset: str`, `temperature: float = 0.7`, `models: list[ProfileModelSpec]`, `limits: ProfileLimits`, `judge_model: str | None = None`
  - `def profile_from_dict(data: dict) -> RunProfile` — validates required fields; raises `ValueError` if any top-level or nested key name is in `SECRET_KEYS` (case-sensitive match on key names); warns once per unknown top-level field via `warnings.warn`, then ignores
  - `SECRET_KEYS` includes at least: `OPENROUTER_API_KEY`, `zai_api_key`, `HF_TOKEN`, `HF_FULL_ACCESS`, `HUGGING_FACE_HUB_TOKEN`

- [ ] **Step 1: Write failing tests in `tests/test_profiles.py`**

```python
import warnings

import pytest

from shared.profiles.schema import profile_from_dict


def test_profile_from_dict_minimal():
    p = profile_from_dict(
        {
            "name": "demo",
            "dataset": "sciq",
            "models": [{"id": "bonsai"}],
        }
    )
    assert p.name == "demo"
    assert p.dataset == "sciq"
    assert p.models[0].id == "bonsai"
    assert p.temperature == 0.7
    assert p.limits.promptfoo == 25


def test_profile_rejects_secret_keys():
    with pytest.raises(ValueError, match="secret"):
        profile_from_dict(
            {
                "name": "bad",
                "dataset": "sciq",
                "models": [{"id": "bonsai"}],
                "HF_TOKEN": "hf_xxx",
            }
        )


def test_profile_requires_name_dataset_model():
    with pytest.raises(ValueError):
        profile_from_dict({"dataset": "sciq", "models": [{"id": "bonsai"}]})
    with pytest.raises(ValueError):
        profile_from_dict({"name": "x", "models": [{"id": "bonsai"}]})
    with pytest.raises(ValueError):
        profile_from_dict({"name": "x", "dataset": "sciq", "models": []})


def test_profile_warns_on_unknown_fields():
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        profile_from_dict(
            {
                "name": "demo",
                "dataset": "sciq",
                "models": [{"id": "bonsai"}],
                "extra_thing": 1,
            }
        )
    assert any("extra_thing" in str(x.message) for x in w)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_profiles.py -v`  
Expected: FAIL (import error or missing symbol)

- [ ] **Step 3: Implement `shared/profiles/schema.py` and `__init__.py`**

```python
# shared/profiles/__init__.py
from shared.profiles.schema import (
    ProfileLimits,
    ProfileModelSpec,
    RunProfile,
    profile_from_dict,
)

__all__ = [
    "ProfileLimits",
    "ProfileModelSpec",
    "RunProfile",
    "profile_from_dict",
]
```

Implement `schema.py` per Interfaces above (full dataclasses + `profile_from_dict`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_profiles.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add shared/profiles/tests/test_profiles.py shared/profiles/ __init__ 2>/dev/null
git add shared/profiles tests/test_profiles.py
git commit -m "$(cat <<'EOF'
Add run profile schema validation without secrets.

EOF
)"
```

---

### Task 3: Profile I/O, env overlay, registry, download dispatch

**Files:**
- Create: `shared/env_files.py`
- Create: `shared/profiles/io.py`
- Create: `shared/profiles/registry.py`
- Create: `shared/profiles/download.py`
- Modify: `shared/config.py` — use `load_project_env()` instead of bare `load_dotenv()`
- Modify: `tests/test_profiles.py` — add I/O / export / download-dispatch tests
- Create: `profiles/examples/bonsai-sciq-t07.yaml`

**Interfaces:**
- Consumes: `profile_from_dict`, `RunProfile`
- Produces:
  - `def load_project_env() -> None` — `load_dotenv(".env")` then `load_dotenv(".env.profile", override=True)` if file exists
  - `def load_profile(path: Path) -> RunProfile`
  - `def save_profile(path: Path, profile: RunProfile) -> None`
  - `def export_profile_from_env(name: str) -> RunProfile` — reads `EVAL_DATASET`, `TARGET_TEMPERATURE`, `PROMPTFOO_LIMIT`, `DEEPEVAL_LIMIT`, `RAGAS_LIMIT`, `MODEL`/`MODELS`, `JUDGE_MODEL`; fills `hf_repo`/`quant`/`gguf_hint` from registry for known ids
  - `def write_env_profile(profile: RunProfile, path: Path = Path(".env.profile")) -> None` — writes only non-secret keys: `EVAL_DATASET`, `TARGET_TEMPERATURE`, `PROMPTFOO_LIMIT`, `DEEPEVAL_LIMIT`, `RAGAS_LIMIT`, `MODEL`, `JUDGE_MODEL` (if set)
  - `MODEL_DOWNLOADERS: dict[str, Callable[[], Path]]` mapping `bonsai` → `scripts.download_bonsai.download`, `qwen27` → `scripts.download_qwen27.download` (lazy import inside functions to avoid heavy imports at module load)
  - `def download_profile_model(profile: RunProfile, model_id: str | None = None) -> Path` — if `model_id` is None and len(models)==1 use that id; else require `model_id`; if id not in `MODEL_DOWNLOADERS` raise `ValueError` listing supported ids

- [ ] **Step 1: Extend `tests/test_profiles.py` with failing I/O tests**

```python
from pathlib import Path

from shared.profiles.io import (
    export_profile_from_env,
    load_profile,
    save_profile,
    write_env_profile,
)
from shared.profiles.download import download_profile_model


def test_roundtrip_yaml(tmp_path: Path):
    from shared.profiles.schema import profile_from_dict

    p = profile_from_dict(
        {
            "name": "demo",
            "dataset": "sciq",
            "temperature": 0.7,
            "models": [{"id": "bonsai", "hf_repo": "prism-ml/Bonsai-27B-gguf", "quant": "Q1_0"}],
            "limits": {"promptfoo": 10, "deepeval": 5, "ragas": 5},
        }
    )
    path = tmp_path / "p.yaml"
    save_profile(path, p)
    loaded = load_profile(path)
    assert loaded.name == "demo"
    assert loaded.limits.promptfoo == 10


def test_write_env_profile_omits_secrets(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-secret")
    from shared.profiles.schema import profile_from_dict

    p = profile_from_dict(
        {"name": "demo", "dataset": "sciq", "models": [{"id": "bonsai"}], "judge_model": "tencent/hy3:free"}
    )
    out = tmp_path / ".env.profile"
    write_env_profile(p, out)
    text = out.read_text()
    assert "OPENROUTER" not in text
    assert "EVAL_DATASET=sciq" in text
    assert "JUDGE_MODEL=tencent/hy3:free" in text


def test_export_profile_from_env(monkeypatch):
    monkeypatch.setenv("EVAL_DATASET", "sciq")
    monkeypatch.setenv("TARGET_TEMPERATURE", "0.7")
    monkeypatch.setenv("MODEL", "bonsai")
    monkeypatch.setenv("PROMPTFOO_LIMIT", "30")
    p = export_profile_from_env("bonsai-sciq-t07")
    assert p.dataset == "sciq"
    assert p.temperature == 0.7
    assert p.models[0].id == "bonsai"
    assert p.models[0].hf_repo  # filled from registry
    assert p.limits.promptfoo == 30


def test_download_unknown_model_lists_supported():
    from shared.profiles.schema import profile_from_dict

    p = profile_from_dict(
        {"name": "demo", "dataset": "sciq", "models": [{"id": "nope"}]}
    )
    with pytest.raises(ValueError, match="bonsai"):
        download_profile_model(p, "nope")
```

- [ ] **Step 2: Run new tests — expect FAIL**

Run: `.venv/bin/pytest tests/test_profiles.py -v`  
Expected: FAIL on missing io/download modules

- [ ] **Step 3: Implement modules**

`shared/env_files.py`:

```python
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


def load_project_env() -> None:
    load_dotenv(ROOT / ".env")
    overlay = ROOT / ".env.profile"
    if overlay.is_file():
        load_dotenv(overlay, override=True)
```

Update `shared/config.py` to call `load_project_env()` instead of `load_dotenv()`.

`shared/profiles/registry.py` — defaults for `bonsai` and `qwen27` matching existing download scripts (`hf_repo`, `quant`, `gguf_hint`, optional `filename`).

`shared/profiles/io.py` — YAML via `yaml.safe_load` / `safe_dump`; `export_profile_from_env`; `write_env_profile`.

`shared/profiles/download.py` — dispatch to `download_bonsai.download` / `download_qwen27.download`.

Example file `profiles/examples/bonsai-sciq-t07.yaml`:

```yaml
name: bonsai-sciq-t07
dataset: sciq
temperature: 0.7
models:
  - id: bonsai
    hf_repo: prism-ml/Bonsai-27B-gguf
    quant: Q1_0
    gguf_hint: data/models/bonsai-27b-q1/
limits:
  promptfoo: 25
  deepeval: 25
  ragas: 25
judge_model: tencent/hy3:free
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `.venv/bin/pytest tests/test_profiles.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add shared/env_files.py shared/config.py shared/profiles profiles/examples/bonsai-sciq-t07.yaml tests/test_profiles.py
git commit -m "$(cat <<'EOF'
Add profile I/O, env overlay, and model download dispatch.

EOF
)"
```

---

### Task 4: Profile CLI + Make targets

**Files:**
- Create: `scripts/profile_cli.py`
- Modify: `Makefile` — add `profile-export`, `profile-import` to `.PHONY` and targets

**Interfaces:**
- Consumes: `export_profile_from_env`, `save_profile`, `load_profile`, `write_env_profile`, `download_profile_model` (print only on import)
- Produces: CLI subcommands `export` and `import`

- [ ] **Step 1: Implement `scripts/profile_cli.py`**

```python
#!/usr/bin/env python3
"""Export/import secret-free run profiles."""

from __future__ import annotations

import argparse
from pathlib import Path

from shared.profiles.download import download_profile_model
from shared.profiles.io import (
    export_profile_from_env,
    load_profile,
    save_profile,
    write_env_profile,
)
from shared.profiles.registry import MODEL_REGISTRY


def cmd_export(args: argparse.Namespace) -> None:
    profile = export_profile_from_env(args.name)
    out = Path(args.out) if args.out else Path("profiles") / f"{args.name}.yaml"
    out.parent.mkdir(parents=True, exist_ok=True)
    save_profile(out, profile)
    print(f"Wrote {out}")


def cmd_import(args: argparse.Namespace) -> None:
    path = Path(args.profile)
    profile = load_profile(path)
    write_env_profile(profile)
    print(f"Loaded profile {profile.name!r} from {path}")
    print("Wrote .env.profile (gitignored). Non-secret overrides active for subsequent commands.")
    print("Suggested downloads:")
    for m in profile.models:
        if m.id in MODEL_REGISTRY:
            print(f"  make download-{m.id}" if m.id in {"bonsai", "qwen27"} else f"  # download helper for {m.id}")
        else:
            print(f"  # unsupported id {m.id}; known: {', '.join(sorted(MODEL_REGISTRY))}")
    print(
        f"Example run: EVAL_DATASET={profile.dataset} TARGET_TEMPERATURE={profile.temperature} "
        f"PROMPTFOO_LIMIT={profile.limits.promptfoo} make lab MODEL={profile.models[0].id}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_ex = sub.add_parser("export", help="Write YAML from current env/defaults")
    p_ex.add_argument("--name", required=True)
    p_ex.add_argument("--out", default=None)
    p_ex.set_defaults(func=cmd_export)

    p_im = sub.add_parser("import", help="Apply YAML to .env.profile")
    p_im.add_argument("--profile", required=True)
    p_im.set_defaults(func=cmd_import)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
```

Adapt Make download hint names to existing targets (`download-bonsai`, `download-qwen27`). Export `MODEL_REGISTRY` from `registry.py` as the metadata dict used by export.

- [ ] **Step 2: Add Makefile targets**

```makefile
profile-export:
	$(VENV)/python scripts/profile_cli.py export --name $(NAME) $(if $(OUT),--out $(OUT),)

profile-import:
	$(VENV)/python scripts/profile_cli.py import --profile $(PROFILE)
```

Add both to `.PHONY`. Document required vars: `NAME=...`, `PROFILE=profiles/examples/bonsai-sciq-t07.yaml`.

- [ ] **Step 3: Smoke the CLI**

Run:

```bash
NAME=cli-smoke .venv/bin/python scripts/profile_cli.py export --name cli-smoke --out /tmp/cli-smoke.yaml
.venv/bin/python scripts/profile_cli.py import --profile profiles/examples/bonsai-sciq-t07.yaml
test -f .env.profile && grep EVAL_DATASET .env.profile
```

Expected: YAML written; `.env.profile` contains `EVAL_DATASET=sciq` and no API keys.

- [ ] **Step 4: Commit**

```bash
git add scripts/profile_cli.py Makefile
git commit -m "$(cat <<'EOF'
Add profile export/import CLI and Make targets.

EOF
)"
```

---

### Task 5: Dashboard download API + button

**Files:**
- Modify: `scripts/dashboard_api.py`
- Modify: `web/partials/overview.html`
- Modify: `web/static/app.js` (or inline Alpine/`fetch` in overview if that matches existing patterns)
- Modify: `tests/test_dashboard_api.py`

**Interfaces:**
- Consumes: `load_profile`, `download_profile_model`
- Produces: `POST /api/models/download` JSON body `{ "profile": str, "model_id": str | null }`; response `{ "ok": bool, "message": str, "path": str | null }`; reject if body contains any `SECRET_KEYS` field names with HTTP 400

- [ ] **Step 1: Write failing API tests**

```python
def test_download_rejects_token_in_body(tmp_path):
    client = TestClient(create_app())
    r = client.post(
        "/api/models/download",
        json={
            "profile": "profiles/examples/bonsai-sciq-t07.yaml",
            "model_id": "bonsai",
            "HF_TOKEN": "hf_should_reject",
        },
    )
    assert r.status_code == 400
    assert r.json()["ok"] is False


def test_download_missing_profile():
    client = TestClient(create_app())
    r = client.post(
        "/api/models/download",
        json={"profile": "profiles/examples/does-not-exist.yaml", "model_id": "bonsai"},
    )
    assert r.status_code in (400, 404)
    assert r.json()["ok"] is False


def test_download_calls_dispatcher(monkeypatch):
    from pathlib import Path

    called = {}

    def fake_download(profile, model_id=None):
        called["id"] = model_id or profile.models[0].id
        return Path("/tmp/fake.gguf")

    monkeypatch.setattr(
        "scripts.dashboard_api.download_profile_model", fake_download
    )
    client = TestClient(create_app())
    r = client.post(
        "/api/models/download",
        json={
            "profile": "profiles/examples/bonsai-sciq-t07.yaml",
            "model_id": "bonsai",
        },
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert called["id"] == "bonsai"
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `.venv/bin/pytest tests/test_dashboard_api.py::test_download_rejects_token_in_body tests/test_dashboard_api.py::test_download_missing_profile tests/test_dashboard_api.py::test_download_calls_dispatcher -v`  
Expected: FAIL (404 route missing)

- [ ] **Step 3: Implement route in `create_app()`**

```python
from pathlib import Path
from shared.profiles.schema import SECRET_KEYS
from shared.profiles.io import load_profile
from shared.profiles.download import download_profile_model

@app.post("/api/models/download")
def api_models_download(payload: dict) -> JSONResponse:
    if not isinstance(payload, dict):
        return JSONResponse({"ok": False, "message": "JSON object required"}, status_code=400)
    bad = sorted(set(payload) & SECRET_KEYS)
    if bad:
        return JSONResponse(
            {"ok": False, "message": f"Secret keys not allowed in body: {', '.join(bad)}"},
            status_code=400,
        )
    rel = payload.get("profile") or "profiles/examples/bonsai-sciq-t07.yaml"
    path = (ROOT / rel).resolve()
    if not str(path).startswith(str(ROOT.resolve())) or not path.is_file():
        return JSONResponse({"ok": False, "message": f"Profile not found: {rel}"}, status_code=404)
    try:
        profile = load_profile(path)
        out = download_profile_model(profile, payload.get("model_id"))
    except ValueError as exc:
        return JSONResponse({"ok": False, "message": str(exc)}, status_code=400)
    except Exception as exc:  # download / HF errors
        return JSONResponse({"ok": False, "message": str(exc)}, status_code=500)
    return JSONResponse({"ok": True, "message": "Download complete", "path": str(out)})
```

Prefer FastAPI `Body` embedding; keep path traversal check.

- [ ] **Step 4: Add UI on overview**

In `web/partials/overview.html` add a small action (not a heavy card grid addition beyond one control):

```html
<p class="meta action-row" id="profile-download-row">
  <button class="btn secondary" type="button" id="btn-download-profile-model"
          data-profile="profiles/examples/bonsai-sciq-t07.yaml"
          data-model-id="bonsai">
    Download model (from profile)
  </button>
  <span id="profile-download-status" class="meta" aria-live="polite"></span>
</p>
```

In `web/static/app.js`, wire click → `fetch('/api/models/download', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({profile, model_id}) })` → update `#profile-download-status` with `message` / errors.

- [ ] **Step 5: Run API tests — expect PASS**

Run: `.venv/bin/pytest tests/test_dashboard_api.py -v`  
Expected: PASS (including new download tests)

- [ ] **Step 6: Commit**

```bash
git add scripts/dashboard_api.py web/partials/overview.html web/static/app.js tests/test_dashboard_api.py
git commit -m "$(cat <<'EOF'
Add dashboard profile model download endpoint and button.

EOF
)"
```

---

### Task 6: `make tools-update`

**Files:**
- Create: `scripts/tools_update.sh`
- Modify: `Makefile`

**Interfaces:**
- Consumes: existing `.venv`, `pyproject.toml`, global npm promptfoo
- Produces: upgraded packages + printed versions

- [ ] **Step 1: Create `scripts/tools_update.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
VENV_PY="${ROOT}/.venv/bin/python"

echo "==> Upgrading Python package (editable + deps)"
uv pip install -U -e ".[dev]" --python "$VENV_PY"

echo "==> Upgrading Promptfoo (npm global)"
npm install -g promptfoo@latest || true

echo "==> Versions"
"$VENV_PY" - <<'PY'
import importlib.metadata as m
for name in ("ragas", "deepeval", "datasets", "huggingface_hub"):
    try:
        print(f"{name}=={m.version(name)}")
    except m.PackageNotFoundError:
        print(f"{name}=(not installed)")
PY
command -v promptfoo >/dev/null && promptfoo --version || echo "promptfoo=(not found on PATH)"
echo "Note: tools-update moves to latest releases and may change eval scores. Record versions with shared profiles for comparison."
```

- [ ] **Step 2: Make executable + Makefile target**

```bash
chmod +x scripts/tools_update.sh
```

```makefile
tools-update:
	bash scripts/tools_update.sh
```

Add `tools-update` to `.PHONY`.

- [ ] **Step 3: Dry-run syntax check (optional full upgrade if network OK)**

Run: `bash -n scripts/tools_update.sh`  
Expected: exit 0

If network available: `make tools-update` and confirm version lines print.

- [ ] **Step 4: Commit**

```bash
git add scripts/tools_update.sh Makefile
git commit -m "$(cat <<'EOF'
Add make tools-update for package-based eval tool sync.

EOF
)"
```

---

### Task 7: README, pyproject, reproduce-run, .env.example polish

**Files:**
- Modify: `README.md`
- Modify: `pyproject.toml` — `description`
- Modify: `docs/reproduce-run.md`
- Modify: `.env.example`

**Interfaces:**
- Consumes: features from Tasks 1–6
- Produces: stranger-friendly docs with no hardware section

- [ ] **Step 1: Update `pyproject.toml` description**

```toml
description = "LLM eval lab: RAGAS, DeepEval, and Promptfoo with shareable run profiles"
```

- [ ] **Step 2: Edit README**

- Delete the entire **Minipc setup** section and any host-specific paths / CPU / RAM tables.
- Delete or rewrite **Hardware Notes** so there is **no** hardware sizing guidance.
- Keep judge/setup/quick start; add sections:

```markdown
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
```

- Ensure Quick Start still: `cp .env.example .env` → `make setup` → prepare → server → lab.

- [ ] **Step 3: Touch `docs/reproduce-run.md`**

Add a short subsection: prefer shared profiles for aligning dataset/temp/models; run `make tools-update` and record package versions when publishing comparable results.

- [ ] **Step 4: Touch `.env.example`**

Add comment near top:

```bash
# Secrets stay here. Shareable run recipes use profiles/*.yaml + .env.profile (never put API keys in profiles).
```

- [ ] **Step 5: Sanity grep**

Run:

```bash
rg -n "Minipc|Ryzen|59 GB|~/.unsloth|this machine" README.md || echo "clean"
```

Expected: `clean` (no matches)

- [ ] **Step 6: Run full unit suite**

Run: `.venv/bin/pytest tests/ -v`  
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add README.md pyproject.toml docs/reproduce-run.md .env.example
git commit -m "$(cat <<'EOF'
Polish public docs for profiles and tools-update.

EOF
)"
```

---

## Spec coverage checklist

| Spec item | Task |
|-----------|------|
| `.gitignore` expansion | Task 1 |
| MIT `LICENSE` + `YOUR_NAME` | Task 1 |
| README without hardware | Task 7 |
| `pyproject.toml` description | Task 7 |
| Profile YAML schema + no secrets | Task 2 |
| `profiles/examples/` | Task 3 |
| Export / import CLI + `.env.profile` | Tasks 3–4 |
| Download reuse `download_*.py` | Task 3 |
| Dashboard download button + API | Task 5 |
| `make tools-update` | Task 6 |
| Docs / `.env.example` / reproduce-run | Task 7 |
| Tests for profiles + download API | Tasks 2, 3, 5 |

## Plan self-review

- No TBD/placeholder steps; concrete code and commands included.
- Types: `RunProfile` / `profile_from_dict` / `download_profile_model` names consistent across tasks.
- `SECRET_KEYS` defined in Task 2 and reused in Tasks 3 and 5.
- Git bootstrap already done; remote creation remains out of band per spec.
