"""Live eval progress state for dashboard polling."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATUS_PATH = ROOT / "results" / "run_status.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_status() -> dict | None:
    if not STATUS_PATH.exists():
        return None
    try:
        return json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def write_status(data: dict) -> None:
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = _now_iso()
    tmp = STATUS_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(STATUS_PATH)


def init_run(
    model: str,
    temp_tag: str,
    tracks: list[str],
    frameworks: list[str],
) -> dict:
    data = {
        "status": "running",
        "model": model,
        "temp_tag": temp_tag,
        "started_at": _now_iso(),
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


def start_step(track: str, framework: str) -> dict:
    data = read_status() or init_run("unknown", "t0.2", [track], [framework])
    data["status"] = "running"
    data["current"] = {"track": track, "framework": framework}
    write_status(data)
    return data


def complete_step(
    track: str,
    framework: str,
    *,
    ok: bool,
    duration_s: float = 0.0,
    artifact: str | None = None,
) -> dict:
    data = read_status() or init_run("unknown", "t0.2", [track], [framework])
    data["step"] = int(data.get("step", 0)) + 1
    entry = {
        "track": track,
        "framework": framework,
        "ok": ok,
        "duration_s": round(duration_s, 1),
    }
    if artifact:
        entry["artifact"] = artifact
    data.setdefault("completed", []).append(entry)
    if not ok:
        data.setdefault("errors", []).append(entry)
    data["current"] = None
    write_status(data)
    return data


def finish_run(status: str = "complete") -> dict:
    data = read_status() or {"status": status}
    data["status"] = status
    data["current"] = None
    write_status(data)
    return data


def set_idle() -> dict:
    data = {"status": "idle", "current": None, "completed": [], "errors": []}
    write_status(data)
    return data
