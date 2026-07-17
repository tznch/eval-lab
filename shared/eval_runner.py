"""Dashboard eval launcher — selective frameworks, auto server, progress hooks."""

from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from shared.datasets.prepare import prepare_dataset
from shared.datasets.registry import samples_path
from shared.env_files import load_project_env
from shared.reporting.run_status import (
    complete_step,
    finish_run,
    init_run,
    is_cancel_requested,
    read_status,
    start_step,
)
from shared.setup.model_endpoint import resolve_model_endpoint
from shared.setup.model_server import (
    can_auto_start_server,
    find_legacy_start_script,
    start_model_server,
)

ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "results" / "logs"
VALID_FRAMEWORKS = frozenset({"promptfoo", "deepeval", "ragas"})


def temp_tag(temperature: float) -> str:
    text = f"{temperature:g}"
    return f"t{text}"


def is_run_in_progress() -> bool:
    status = read_status()
    return bool(status and status.get("status") == "running")


def _server_reachable(base_url: str, timeout: float = 2.0) -> bool:
    url = base_url.rstrip("/") + "/models"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, OSError, TimeoutError):
        return False


def wait_for_server(base_url: str, *, tries: int = 120, sleep_s: float = 5.0) -> bool:
    for _ in range(tries):
        if _server_reachable(base_url):
            return True
        time.sleep(sleep_s)
    return False


def ensure_server(model_id: str, base_url: str) -> None:
    if _server_reachable(base_url):
        return

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"{model_id}-server.log"
    env = dict(os.environ)

    if can_auto_start_server(model_id, env):
        start_model_server(model_id, base_url, log_path=log_path, env=env)
    else:
        script = find_legacy_start_script(model_id)
        if not script:
            raise RuntimeError(
                f"Model server not reachable at {base_url}. "
                f"Start any OpenAI-compatible server there, or set "
                f"{model_id.upper()}_MODEL_PATH + LLAMA_SERVER for auto-start."
            )
        with log_path.open("ab") as log_file:
            subprocess.Popen(
                ["bash", str(script)],
                cwd=ROOT,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )

    if not wait_for_server(base_url):
        raise RuntimeError(f"Server failed to start for {model_id!r}. See {log_path}")


def prepare_dataset_if_needed(dataset_id: str, limit: int | None = None) -> None:
    sp = samples_path(dataset_id)
    if sp.is_file():
        return
    prepare_dataset(dataset_id, limit)


def apply_run_env(
    *,
    model_id: str,
    dataset_id: str,
    temperature: float,
) -> tuple[str, str]:
    load_project_env()
    os.environ["MODEL"] = model_id
    os.environ["EVAL_MODEL_ID"] = model_id
    os.environ["EVAL_DATASET"] = dataset_id
    os.environ["RAGAS_CONFIG"] = dataset_id
    os.environ["TARGET_TEMPERATURE"] = str(temperature)

    base_url, model_name = resolve_model_endpoint(model_id, dict(os.environ))
    if not base_url or not model_name:
        raise RuntimeError(f"Model endpoint not configured for {model_id!r}")
    os.environ["TARGET_MODEL_BASE_URL"] = base_url
    os.environ["TARGET_MODEL_NAME"] = model_name

    tag = temp_tag(temperature)
    os.environ["PROMPTFOO_OUTPUT"] = str(
        ROOT / "results" / "promptfoo" / model_id / tag / dataset_id / "output.json"
    )
    os.environ["DEEPEVAL_OUTPUT"] = str(
        ROOT / "results" / "deepeval" / model_id / tag / dataset_id / "junit.xml"
    )
    os.environ["RAGAS_OUTPUT_TAG"] = tag
    return base_url, tag


def _run_cmd(
    args: list[str],
    *,
    log_name: str,
    env: dict[str, str] | None = None,
) -> bool:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / log_name
    with log_path.open("ab") as log_file:
        proc = subprocess.run(
            args,
            cwd=ROOT,
            env=env or os.environ.copy(),
            stdout=log_file,
            stderr=subprocess.STDOUT,
            check=False,
        )
    return proc.returncode == 0


def _artifact_for(framework: str, model_id: str, tag: str, dataset_id: str) -> str:
    if framework == "promptfoo":
        return str(ROOT / "results" / "promptfoo" / model_id / tag / dataset_id / "output.json")
    if framework == "deepeval":
        return str(ROOT / "results" / "deepeval" / model_id / tag / dataset_id / "junit.xml")
    return str(ROOT / "results" / "ragas" / model_id / tag / f"{dataset_id}_scores.csv")


def run_framework(
    framework: str,
    *,
    model_id: str,
    dataset_id: str,
    tag: str,
) -> bool:
    start_step(dataset_id, framework)
    t0 = time.monotonic()
    ok = False
    artifact = _artifact_for(framework, model_id, tag, dataset_id)

    if framework == "promptfoo":
        ok = _run_cmd(
            [sys.executable, str(ROOT / "scripts" / "run_promptfoo_eval.py")],
            log_name=f"{model_id}-promptfoo.log",
        )
    elif framework == "deepeval":
        ok = _run_cmd(
            [sys.executable, str(ROOT / "scripts" / "run_deepeval.py")],
            log_name=f"{model_id}-deepeval.log",
        )
    elif framework == "ragas":
        limit = os.environ.get("RAGAS_LIMIT", "25")
        ok = _run_cmd(
            [
                sys.executable,
                str(ROOT / "eval" / "ragas" / "run.py"),
                "--config",
                dataset_id,
                "--limit",
                str(limit),
                "--model-id",
                model_id,
            ],
            log_name=f"{model_id}-ragas.log",
        )
    else:
        raise ValueError(f"Unknown framework: {framework}")

    duration = time.monotonic() - t0
    complete_step(dataset_id, framework, ok=ok, duration_s=duration, artifact=artifact)
    return ok


def run_eval(
    *,
    model_id: str,
    dataset_id: str | None = None,
    dataset_ids: list[str] | None = None,
    temperature: float,
    frameworks: list[str],
    prepare_limit: int | None = None,
) -> None:
    fw = [f for f in frameworks if f in VALID_FRAMEWORKS]
    if not fw:
        raise ValueError("At least one framework is required")

    tracks = [d for d in (dataset_ids or []) if d]
    if not tracks and dataset_id:
        tracks = [dataset_id]
    if not tracks:
        raise ValueError("At least one dataset is required")

    if is_run_in_progress():
        raise RuntimeError("An eval is already running")

    tag = temp_tag(temperature)
    init_run(model_id, tag, tracks, fw, pid=os.getpid())

    try:
        load_project_env()
        for ds in tracks:
            prepare_dataset_if_needed(ds, prepare_limit)
        if is_cancel_requested():
            finish_run("cancelled")
            return

        # Resolve endpoint once; apply_run_env updates paths per dataset below.
        base_url, tag = apply_run_env(
            model_id=model_id,
            dataset_id=tracks[0],
            temperature=temperature,
        )
        ensure_server(model_id, base_url)

        LOG_DIR.mkdir(parents=True, exist_ok=True)
        errors: list[str] = []
        for ds in tracks:
            if is_cancel_requested():
                finish_run("cancelled")
                return
            apply_run_env(
                model_id=model_id,
                dataset_id=ds,
                temperature=temperature,
            )
            for framework in fw:
                if is_cancel_requested():
                    finish_run("cancelled")
                    return
                if not run_framework(
                    framework,
                    model_id=model_id,
                    dataset_id=ds,
                    tag=tag,
                ):
                    errors.append(f"{ds}/{framework}")

        if is_cancel_requested():
            finish_run("cancelled")
            return

        _run_cmd(
            [sys.executable, str(ROOT / "scripts" / "build_dashboard.py")],
            log_name="dashboard-eval-build.log",
        )
        finish_run("error" if errors else "complete")
    except Exception:
        if is_cancel_requested():
            finish_run("cancelled")
            return
        finish_run("error")
        raise
