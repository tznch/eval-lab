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
