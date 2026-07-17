"""Pre-flight checks before running eval from the dashboard."""

from __future__ import annotations

import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from shared.datasets.registry import discover_datasets, get_dataset, list_dataset_ids, samples_path
from shared.env_files import load_project_env
from shared.profiles.registry import MODEL_REGISTRY
from shared.setup.model_endpoint import model_weights_path, resolve_model_endpoint

FRAMEWORKS = frozenset({"promptfoo", "deepeval", "ragas"})
DEFAULT_FRAMEWORKS = ["promptfoo", "deepeval", "ragas"]
DEFAULT_TEMPERATURES = [0.2, 0.7, 1.0]


def _check(name: str, ok: bool, message: str, **extra: Any) -> dict[str, Any]:
    row = {"ok": ok, "message": message}
    row.update(extra)
    return row


def _judge_ok(env: dict[str, str]) -> tuple[bool, str]:
    provider = (env.get("JUDGE_PROVIDER") or "openrouter").lower()
    if provider == "openrouter":
        if env.get("OPENROUTER_API_KEY"):
            return True, "OpenRouter API key set"
        return False, "Set OPENROUTER_API_KEY in .env for DeepEval/RAGAS"
    if provider == "glm":
        if env.get("zai_api_key"):
            return True, "Z.ai API key set"
        return False, "Set zai_api_key in .env for DeepEval/RAGAS"
    return False, f"Unknown JUDGE_PROVIDER: {provider!r}"


def _can_auto_start_server(model_id: str, env: dict[str, str]) -> bool:
    from shared.setup.model_server import can_auto_start_server

    return can_auto_start_server(model_id, env)


def _server_ok(base_url: str, timeout: float = 2.0) -> tuple[bool, str]:
    url = base_url.rstrip("/") + "/models"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            if 200 <= resp.status < 300:
                return True, f"Server reachable at {base_url}"
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        return False, f"Server not reachable at {base_url} ({exc})"
    return False, f"Server not reachable at {base_url}"


def check_readiness(
    *,
    model_id: str,
    dataset_id: str | None = None,
    dataset_ids: list[str] | None = None,
    frameworks: list[str] | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    fw = frameworks or list(DEFAULT_FRAMEWORKS)
    fw = [f for f in fw if f in FRAMEWORKS]
    if not fw:
        fw = ["promptfoo"]

    ids = [d for d in (dataset_ids or []) if d]
    if not ids and dataset_id:
        ids = [dataset_id]
    if not ids:
        ids = ["sciq"]

    if env is None:
        load_project_env()
        env = dict(os.environ)

    blocking: list[str] = []
    checks: dict[str, dict[str, Any]] = {}
    legacy_ids = set(list_dataset_ids())

    unknown = [d for d in ids if get_dataset(d) is None and d not in legacy_ids]
    reg_ok = not unknown
    checks["dataset_registered"] = _check(
        "dataset_registered",
        reg_ok,
        (
            f"{len(ids)} dataset(s) registered"
            if reg_ok
            else f"Unknown dataset(s): {', '.join(unknown)}"
        ),
    )
    if not reg_ok:
        blocking.append(checks["dataset_registered"]["message"])

    missing_samples: list[str] = []
    sample_paths: list[str] = []
    for ds in ids:
        sp = samples_path(ds)
        sample_paths.append(str(sp))
        if not sp.is_file():
            missing_samples.append(ds)
    samples_ok = not missing_samples
    checks["dataset_samples"] = _check(
        "dataset_samples",
        samples_ok,
        (
            f"Samples ready for {len(ids)} dataset(s)"
            if samples_ok
            else f"Missing samples — prepare: {', '.join(missing_samples)}"
        ),
        path=sample_paths[0] if len(sample_paths) == 1 else "",
        paths=sample_paths,
    )
    if not samples_ok:
        blocking.append(checks["dataset_samples"]["message"])

    # Model endpoint
    base_url, model_name = resolve_model_endpoint(model_id, env)
    configured_ok = bool(base_url and model_name)
    msg = (
        f"Endpoint {base_url} ({model_name})"
        if configured_ok
        else "Set TARGET_MODEL_BASE_URL and TARGET_MODEL_NAME in .env for custom models"
    )
    checks["model_configured"] = _check(
        "model_configured",
        configured_ok,
        msg,
        url=base_url or "",
        model_name=model_name or "",
    )
    if not configured_ok:
        blocking.append(checks["model_configured"]["message"])

    # Weights (registry models only)
    if model_id in MODEL_REGISTRY:
        wp = model_weights_path(model_id)
        weights_ok = wp is not None and wp.is_file()
        checks["model_weights"] = _check(
            "model_weights",
            weights_ok,
            f"Weights found at {wp}" if weights_ok else f"Download model weights for {model_id!r}",
            path=str(wp) if wp else "",
        )
        if not weights_ok:
            blocking.append(checks["model_weights"]["message"])
    else:
        checks["model_weights"] = _check(
            "model_weights",
            True,
            "No bundled weights check for custom model id",
        )

    # Server health (offline OK when weights + start script can auto-launch)
    if configured_ok and base_url:
        srv_ok, srv_msg = _server_ok(base_url)
        if not srv_ok and _can_auto_start_server(model_id, env):
            srv_ok = True
            srv_msg = f"Server offline at {base_url} — will auto-start on Run eval"
    else:
        srv_ok, srv_msg = False, "Configure model endpoint first"
    checks["model_server"] = _check(
        "model_server",
        srv_ok,
        srv_msg,
        url=base_url or "",
    )
    if not srv_ok and configured_ok:
        blocking.append(checks["model_server"]["message"])

    # Judge
    needs_judge = any(f in fw for f in ("deepeval", "ragas"))
    if needs_judge:
        j_ok, j_msg = _judge_ok(env)
    else:
        j_ok, j_msg = True, "Judge not required for Promptfoo-only runs"
    checks["judge"] = _check("judge", j_ok, j_msg)
    if needs_judge and not j_ok:
        blocking.append(checks["judge"]["message"])

    can_run = len(blocking) == 0
    return {
        "ok": can_run,
        "model_id": model_id,
        "dataset_id": ids[0],
        "dataset_ids": ids,
        "frameworks": fw,
        "checks": checks,
        "can_run": can_run,
        "blocking": blocking,
    }


def load_profile_env_values() -> dict[str, str]:
    load_project_env()
    return dict(os.environ)


def profile_models_from_env(env: dict[str, str] | None = None) -> list[str]:
    e = env if env is not None else load_profile_env_values()
    raw = e.get("MODEL") or e.get("MODELS") or ""
    return [m.strip() for m in raw.split(",") if m.strip()]


def list_setup_datasets() -> list[dict[str, str]]:
    """Datasets from datasets/*/dataset.yaml (fresh scan each call)."""
    discover_datasets.cache_clear()
    catalog: list[dict[str, str]] = []
    for manifest in sorted(discover_datasets().values(), key=lambda m: m.name.lower()):
        catalog.append(
            {
                "id": manifest.id,
                "name": manifest.name,
                "topic": manifest.topic,
                "description": manifest.description,
            }
        )
    return catalog


def setup_options(env: dict[str, str] | None = None) -> dict[str, Any]:
    e = env if env is not None else load_profile_env_values()
    models = profile_models_from_env(e)
    dataset = e.get("EVAL_DATASET", "sciq")
    try:
        temp = float(e.get("TARGET_TEMPERATURE", "0.7"))
    except ValueError:
        temp = 0.7
    temps = list(DEFAULT_TEMPERATURES)
    if temp not in temps:
        temps.append(temp)
        temps.sort()
    catalog = list_setup_datasets()
    ids = [d["id"] for d in catalog]
    default = dataset if dataset in ids else (ids[0] if ids else "sciq")
    return {
        "has_profile": has_env_profile(),
        "datasets": ids,
        "dataset_catalog": catalog,
        "temperatures": temps,
        "frameworks": list(DEFAULT_FRAMEWORKS),
        "models": models or ["bonsai"],
        "default_dataset": default,
        "default_datasets": [default],
        "default_temperature": temp,
        "default_model": models[0] if models else "bonsai",
        "limits": {
            "promptfoo": int(e.get("PROMPTFOO_LIMIT", "25")),
            "deepeval": int(e.get("DEEPEVAL_LIMIT", "25")),
            "ragas": int(e.get("RAGAS_LIMIT", "25")),
        },
    }


def has_env_profile() -> bool:
    return (Path(__file__).resolve().parents[2] / ".env.profile").is_file()
