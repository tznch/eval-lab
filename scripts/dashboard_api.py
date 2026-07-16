"""FastAPI dashboard server — HTMX partials + JSON API."""

from __future__ import annotations

from pathlib import Path

from fastapi import Body, FastAPI, Request
from pydantic import BaseModel, ConfigDict, ValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from shared.env_files import load_project_env
from shared.profiles import SECRET_KEYS
from shared.profiles.download import download_profile_model
from shared.profiles.io import (
    export_profile_from_env,
    load_profile,
    load_profile_yaml,
    profile_to_yaml,
    write_env_profile,
)
from shared.reporting.dashboard_filters import parse_filter_params
from shared.reporting.dashboard_views import (
    build_deepeval_groups,
    build_failures_view,
    build_overview_view,
    build_performance_view,
    build_promptfoo_view,
    build_ragas_view,
    build_report_view,
    load_catalog,
)
from shared.reporting.run_status import read_status

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
PARTIALS = WEB / "partials"
EXPORTS = ROOT / "results" / "dashboard"


def _secret_keys_in(value: object) -> set[str]:
    if isinstance(value, dict):
        found = set(value) & SECRET_KEYS
        for nested_value in value.values():
            found.update(_secret_keys_in(nested_value))
        return found
    if isinstance(value, list):
        found = set()
        for item in value:
            found.update(_secret_keys_in(item))
        return found
    return set()


def _filters_from_request(request: Request) -> tuple[dict, object]:
    catalog = load_catalog()
    filters = parse_filter_params(dict(request.query_params), catalog)
    return catalog, filters


def _panel(request: Request) -> str | None:
    return request.query_params.get("panel")


class ModelDownloadPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    profile: str | None = None
    model_id: str | None = None


class ProfileImportPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    yaml: str


class ProfileExportPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    dataset: str | None = None
    temperature: float | None = None
    models: list[str] | None = None


def _safe_profile_filename(name: str) -> str:
    cleaned = "".join(
        ch if ch.isalnum() or ch in "._-" else "-" for ch in name.strip()
    ).strip("-._")
    return (cleaned or "run-profile")[:80] + ".yaml"


def create_app() -> FastAPI:
    app = FastAPI(title="LLM Eval Lab Dashboard")
    templates = Jinja2Templates(directory=PARTIALS)

    static_dir = WEB / "static"
    if static_dir.is_dir():
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

    if EXPORTS.is_dir():
        app.mount("/exports", StaticFiles(directory=EXPORTS), name="exports")

    @app.get("/", response_class=HTMLResponse)
    def index() -> FileResponse:
        return FileResponse(WEB / "index.html")

    @app.get("/api/catalog")
    def api_catalog() -> JSONResponse:
        return JSONResponse(load_catalog())

    @app.get("/api/run-status")
    def api_run_status() -> JSONResponse:
        return JSONResponse(read_status() or {"status": "idle"})

    @app.post("/api/models/download")
    def api_models_download(payload: dict = Body(...)) -> JSONResponse:
        bad_keys = sorted(_secret_keys_in(payload))
        if bad_keys:
            return JSONResponse(
                {
                    "ok": False,
                    "message": (
                        "Secret keys not allowed in body: "
                        + ", ".join(bad_keys)
                    ),
                    "path": None,
                },
                status_code=400,
            )

        try:
            body = ModelDownloadPayload.model_validate(payload)
        except ValidationError:
            return JSONResponse(
                {
                    "ok": False,
                    "message": (
                        "Invalid request body: profile must be a string "
                        "and model_id must be a string or null"
                    ),
                    "path": None,
                },
                status_code=400,
            )

        relative_path = (
            body.profile or "profiles/examples/bonsai-sciq-t07.yaml"
        )
        profile_path = (ROOT / relative_path).resolve()
        if (
            not profile_path.is_relative_to(ROOT.resolve())
            or not profile_path.is_file()
        ):
            return JSONResponse(
                {
                    "ok": False,
                    "message": f"Profile not found: {relative_path}",
                    "path": None,
                },
                status_code=404,
            )

        try:
            profile = load_profile(profile_path)
            output_path = download_profile_model(profile, body.model_id)
        except ValueError as exc:
            return JSONResponse(
                {"ok": False, "message": str(exc), "path": None},
                status_code=400,
            )
        except Exception as exc:
            return JSONResponse(
                {"ok": False, "message": str(exc), "path": None},
                status_code=500,
            )

        return JSONResponse(
            {
                "ok": True,
                "message": "Download complete",
                "path": str(output_path),
            }
        )

    @app.post("/api/profiles/import")
    def api_profiles_import(payload: dict = Body(...)) -> JSONResponse:
        bad_keys = sorted(_secret_keys_in(payload))
        if bad_keys:
            return JSONResponse(
                {
                    "ok": False,
                    "message": (
                        "Secret keys not allowed in body: "
                        + ", ".join(bad_keys)
                    ),
                },
                status_code=400,
            )

        try:
            body = ProfileImportPayload.model_validate(payload)
        except ValidationError:
            return JSONResponse(
                {
                    "ok": False,
                    "message": "Invalid request body: yaml must be a string",
                },
                status_code=400,
            )

        text = body.yaml.strip()
        if not text:
            return JSONResponse(
                {"ok": False, "message": "Empty profile YAML"},
                status_code=400,
            )
        if len(text) > 200_000:
            return JSONResponse(
                {"ok": False, "message": "Profile YAML too large"},
                status_code=400,
            )

        try:
            profile = load_profile_yaml(text)
            # Also reject secrets that appear as YAML keys after parse
            write_env_profile(profile, ROOT / ".env.profile")
        except ValueError as exc:
            return JSONResponse(
                {"ok": False, "message": str(exc)},
                status_code=400,
            )
        except Exception as exc:
            return JSONResponse(
                {"ok": False, "message": str(exc)},
                status_code=500,
            )

        return JSONResponse(
            {
                "ok": True,
                "message": (
                    f"Imported profile {profile.name!r} "
                    f"(dataset={profile.dataset}, models="
                    f"{','.join(m.id for m in profile.models)}). "
                    "Wrote .env.profile — API keys unchanged."
                ),
                "name": profile.name,
                "dataset": profile.dataset,
                "models": [m.id for m in profile.models],
            }
        )

    @app.post("/api/profiles/export")
    def api_profiles_export(payload: dict | None = Body(default=None)) -> JSONResponse:
        payload = payload if isinstance(payload, dict) else {}
        bad_keys = sorted(_secret_keys_in(payload))
        if bad_keys:
            return JSONResponse(
                {
                    "ok": False,
                    "message": (
                        "Secret keys not allowed in body: "
                        + ", ".join(bad_keys)
                    ),
                },
                status_code=400,
            )

        try:
            body = ProfileExportPayload.model_validate(payload)
        except ValidationError:
            return JSONResponse(
                {
                    "ok": False,
                    "message": (
                        "Invalid request body: name/dataset must be strings, "
                        "temperature a number, models a list of strings"
                    ),
                },
                status_code=400,
            )

        load_project_env()
        name = (body.name or "").strip() or "run-profile"
        try:
            profile = export_profile_from_env(
                name,
                dataset=body.dataset,
                temperature=body.temperature,
                model_ids=body.models,
            )
            yaml_text = profile_to_yaml(profile)
        except ValueError as exc:
            return JSONResponse(
                {"ok": False, "message": str(exc)},
                status_code=400,
            )
        except Exception as exc:
            return JSONResponse(
                {"ok": False, "message": str(exc)},
                status_code=500,
            )

        return JSONResponse(
            {
                "ok": True,
                "message": (
                    f"Exported profile {profile.name!r} "
                    f"(dataset={profile.dataset}, models="
                    f"{','.join(m.id for m in profile.models)})"
                ),
                "filename": _safe_profile_filename(profile.name),
                "yaml": yaml_text,
                "name": profile.name,
                "dataset": profile.dataset,
                "models": [m.id for m in profile.models],
            }
        )

    @app.get("/partials/progress", response_class=HTMLResponse)
    def partial_progress(request: Request) -> HTMLResponse:
        status = read_status() or {"status": "idle"}
        return templates.TemplateResponse(request, "progress.html", {"status": status})

    @app.get("/partials/overview", response_class=HTMLResponse)
    def partial_overview(request: Request) -> HTMLResponse:
        catalog, filters = _filters_from_request(request)
        view = build_overview_view(catalog, filters)
        return templates.TemplateResponse(request, "overview.html", {"view": view, "filters": filters})

    @app.get("/partials/report", response_class=HTMLResponse)
    def partial_report(request: Request) -> HTMLResponse:
        catalog, filters = _filters_from_request(request)
        view = build_report_view(filters, catalog)
        return templates.TemplateResponse(
            request,
            "report.html",
            {"view": view, "filters": filters},
        )

    @app.get("/partials/deepeval", response_class=HTMLResponse)
    def partial_deepeval(request: Request) -> HTMLResponse:
        _, filters = _filters_from_request(request)
        groups = build_deepeval_groups(filters)
        return templates.TemplateResponse(request, "deepeval.html", {"groups": groups, "filters": filters})

    @app.get("/partials/promptfoo", response_class=HTMLResponse)
    def partial_promptfoo(request: Request) -> HTMLResponse:
        _, filters = _filters_from_request(request)
        view = build_promptfoo_view(filters)
        panel = _panel(request) or "ui"
        if panel not in ("ui", "summaries"):
            panel = "ui"
        return templates.TemplateResponse(
            request,
            "promptfoo.html",
            {"view": view, "filters": filters, "panel": panel},
        )

    @app.get("/partials/ragas", response_class=HTMLResponse)
    def partial_ragas(request: Request) -> HTMLResponse:
        _, filters = _filters_from_request(request)
        view = build_ragas_view(filters)
        return templates.TemplateResponse(request, "ragas.html", {"view": view, "filters": filters})

    @app.get("/partials/performance", response_class=HTMLResponse)
    def partial_performance(request: Request) -> HTMLResponse:
        _, filters = _filters_from_request(request)
        view = build_performance_view(filters)
        return templates.TemplateResponse(
            request,
            "performance.html",
            {"view": view, "filters": filters, "panel": _panel(request)},
        )

    @app.get("/partials/failures", response_class=HTMLResponse)
    def partial_failures(request: Request) -> HTMLResponse:
        _, filters = _filters_from_request(request)
        view = build_failures_view(filters)
        return templates.TemplateResponse(request, "failures.html", {"view": view, "filters": filters})

    return app


app = create_app()
