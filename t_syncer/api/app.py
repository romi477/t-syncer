from __future__ import annotations

import base64
import secrets
from contextlib import asynccontextmanager
from datetime import date as date_type
from pathlib import Path

import uvicorn
from fastapi import APIRouter, Depends, FastAPI, Query, Request
from fastapi.responses import RedirectResponse, Response
from fastapi.security import HTTPBasic
from fastapi.staticfiles import StaticFiles

from api import __version__
from api.config import Settings
from api.db import close_db, db_request, init_db
from api.jira import default_jira_factory
from api.logging import configure_logging
from api.models import Workspace
from api.schemas import DayLinesIn, LineIn, LinePatch, WorkspaceIn, WorkspaceUpdate
from api.serialize import day_total, worklog_metadata, worklog_public, workspace_public
from api.service import (
    bulk_push,
    build_report,
    create_days,
    create_line,
    day_lines,
    delete_in_jira,
    delete_line,
    get_worklog,
    get_workspace,
    normalize_base_url,
    patch_line,
    probe_jira,
    push_line,
    range_lines,
    report_bounds,
    reset_to_draft,
    summarize_days,
    validate_day_start,
    validate_timezone,
)

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
_HTTP_BASIC = HTTPBasic(
    realm="T-Syncer",
    description="App login: TSYNCER_BASIC_USER / TSYNCER_BASIC_PASSWORD. Not the Jira token.",
)
_OPENAPI_TAGS = [
    {
        "name": "Workspace",
        "description": "One Jira Cloud site. The API token is never returned in full.",
    },
    {
        "name": "Days",
        "description": "Day cards: calendar summaries and the lines for one date.",
    },
    {
        "name": "Lines",
        "description": "Create and edit worklog lines in SQLite. This is not a Jira push.",
    },
    {
        "name": "Push",
        "description": (
            "Write worklogs to Jira Cloud. Sync the whole card or a date range in one "
            "request; push one line with a different path."
        ),
    },
    {
        "name": "Reports",
        "description": "Local aggregation for the current workspace. Not a Jira report.",
    },
]


class WebStaticFiles(StaticFiles):
    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-store"

        return response


def _is_public(path: str) -> bool:
    return path == "/health"


def _authorized(request: Request) -> bool:
    header = request.headers.get("authorization")
    if not header or not header.lower().startswith("basic "):
        return False
    try:
        decoded = base64.b64decode(header.split(" ", 1)[1]).decode("utf-8")
    except Exception:
        return False
    username, separator, password = decoded.partition(":")
    if not separator:
        return False
    user_ok = secrets.compare_digest(
        username.encode("utf-8").ljust(256, b"\0"),
        request.app.state.basic_user.encode("utf-8").ljust(256, b"\0"),
    )
    pass_ok = secrets.compare_digest(
        password.encode("utf-8").ljust(256, b"\0"),
        request.app.state.basic_password.encode("utf-8").ljust(256, b"\0"),
    )

    return user_ok and pass_ok


def _jira(request: Request, workspace: Workspace):
    return request.app.state.jira_factory(
        workspace.jira_base_url,
        workspace.jira_email,
        workspace.jira_api_token,
    )


def _close(client) -> None:
    closer = getattr(client, "close", None)
    if closer:
        closer()


def create_app(
    *,
    sqlite_db_path: str,
    basic_user: str,
    basic_password: str,
    jira_factory=None,
    log_level: str = "INFO",
) -> FastAPI:
    configure_logging(log_level)
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        init_db(sqlite_db_path)
        yield
        close_db()

    app = FastAPI(
        title="T-Syncer",
        description=(
            "Local-first Jira timesheet. SQLite is the source of truth; Jira Cloud is write-only.\n\n"
            "Click **Authorize** and use `TSYNCER_BASIC_USER` / `TSYNCER_BASIC_PASSWORD` "
            "(not the Jira API token)."
        ),
        version=__version__,
        openapi_tags=_OPENAPI_TAGS,
        swagger_ui_parameters={"persistAuthorization": True},
        lifespan=lifespan,
    )
    app.state.basic_user = basic_user
    app.state.basic_password = basic_password
    app.state.jira_factory = jira_factory or default_jira_factory

    @app.middleware("http")
    async def require_basic(request: Request, call_next):
        if _is_public(request.url.path) or _authorized(request):
            return await call_next(request)

        return Response(
            content=b"Unauthorized",
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="T-Syncer"'},
        )

    @app.get("/", include_in_schema=False)
    def root():
        return RedirectResponse("/web", status_code=307)

    @app.get("/health", include_in_schema=False)
    def health():
        return {"status": "ok"}

    api = APIRouter(prefix="/api", dependencies=[Depends(_HTTP_BASIC)])

    @api.get("/workspace", tags=["Workspace"], summary="List workspaces")
    @db_request
    def list_workspaces():
        rows = Workspace.select().order_by(Workspace.id)

        return [workspace_public(row) for row in rows]

    @api.post("/workspace", status_code=201, tags=["Workspace"], summary="Create workspace")
    @db_request
    def create_workspace(payload: WorkspaceIn, request: Request):
        url = normalize_base_url(payload.jira_base_url)
        timezone = validate_timezone(payload.timezone)
        day_start = validate_day_start(payload.day_start)
        display_name = probe_jira(
            request.app.state.jira_factory,
            url,
            payload.jira_email,
            payload.jira_api_token,
        )
        workspace = Workspace.create(
            name=payload.name.strip(),
            jira_base_url=url,
            jira_email=payload.jira_email.strip(),
            jira_api_token=payload.jira_api_token,
            timezone=timezone,
            day_start=day_start,
            jira_display_name=display_name,
        )

        return workspace_public(workspace)

    @api.get("/workspace/{workspace_id}", tags=["Workspace"], summary="Get workspace")
    @db_request
    def read_workspace(workspace_id: int):
        return workspace_public(get_workspace(workspace_id))

    @api.patch("/workspace/{workspace_id}", tags=["Workspace"], summary="Update workspace")
    @db_request
    def update_workspace(workspace_id: int, payload: WorkspaceUpdate, request: Request):
        workspace = get_workspace(workspace_id)
        if payload.name is not None:
            workspace.name = payload.name.strip()
        if payload.jira_base_url is not None:
            workspace.jira_base_url = normalize_base_url(payload.jira_base_url)
        if payload.jira_email is not None:
            workspace.jira_email = payload.jira_email.strip()
        if payload.jira_api_token:
            workspace.jira_api_token = payload.jira_api_token
        if payload.timezone is not None:
            workspace.timezone = validate_timezone(payload.timezone)
        if payload.day_start is not None:
            workspace.day_start = validate_day_start(payload.day_start)
        workspace.jira_display_name = probe_jira(
            request.app.state.jira_factory,
            workspace.jira_base_url,
            workspace.jira_email,
            workspace.jira_api_token,
        )
        workspace.save()

        return workspace_public(workspace)

    @api.delete("/workspace/{workspace_id}", status_code=204, tags=["Workspace"], summary="Delete workspace")
    @db_request
    def remove_workspace(workspace_id: int):
        workspace = get_workspace(workspace_id)
        workspace.delete_instance(recursive=True)

        return Response(status_code=204)

    @api.get("/workspace/{workspace_id}/days", tags=["Days"], summary="List day summaries")
    @db_request
    def list_days(
        workspace_id: int,
        date_from: date_type = Query(..., alias="from"),
        date_to: date_type = Query(..., alias="to"),
    ):
        get_workspace(workspace_id)

        return {"days": summarize_days(range_lines(workspace_id, date_from, date_to))}

    @api.get("/workspace/{workspace_id}/days/{work_date}", tags=["Days"], summary="Get day card")
    @db_request
    def read_day(workspace_id: int, work_date: date_type):
        get_workspace(workspace_id)
        lines = day_lines(workspace_id, work_date)

        return {
            "work_date": work_date.isoformat(),
            "total_minutes": day_total(lines),
            "lines": [worklog_public(line) for line in lines],
        }

    @api.post(
        "/workspace/{workspace_id}/worklogs",
        status_code=201,
        tags=["Lines"],
        summary="Create lines for several days",
    )
    @db_request
    def add_lines(workspace_id: int, payload: list[DayLinesIn]):
        """JSON array of `{date, lines}`. One request for many days. Does not push to Jira."""
        workspace = get_workspace(workspace_id)

        return create_days(workspace, payload)

    @api.post(
        "/workspace/{workspace_id}/days/{work_date}/worklogs",
        status_code=201,
        tags=["Lines"],
        summary="Create one line",
    )
    @db_request
    def add_line(workspace_id: int, work_date: date_type, payload: LineIn):
        workspace = get_workspace(workspace_id)
        worklog = create_line(workspace, work_date, payload)
        total = day_total(day_lines(workspace_id, work_date))

        return worklog_public(worklog, total_minutes=total)

    @api.get(
        "/workspace/{workspace_id}/worklogs/{worklog_id}",
        tags=["Lines"],
        summary="Get worklog metadata",
    )
    @db_request
    def get_line(workspace_id: int, worklog_id: int):
        """SQLite row plus the related workspace. Token is masked."""
        worklog = get_worklog(workspace_id, worklog_id)

        return worklog_metadata(worklog)

    @api.patch(
        "/workspace/{workspace_id}/worklogs/{worklog_id}",
        tags=["Lines"],
        summary="Edit a draft or error line",
    )
    @db_request
    def edit_line(workspace_id: int, worklog_id: int, payload: LinePatch):
        worklog = get_worklog(workspace_id, worklog_id)
        patch_line(worklog, payload)
        total = day_total(day_lines(workspace_id, worklog.work_date))

        return worklog_public(worklog, total_minutes=total)

    @api.delete(
        "/workspace/{workspace_id}/worklogs/{worklog_id}",
        status_code=204,
        tags=["Lines"],
        summary="Delete a draft or error line",
    )
    @db_request
    def remove_line(workspace_id: int, worklog_id: int):
        worklog = get_worklog(workspace_id, worklog_id)
        delete_line(worklog)

        return Response(status_code=204)

    @api.post(
        "/workspace/{workspace_id}/worklogs/{worklog_id}/push",
        tags=["Push"],
        summary="Push one line to Jira",
    )
    @db_request
    def push_one(workspace_id: int, worklog_id: int, request: Request):
        """Already `synced` returns the line with `skipped: true`."""
        workspace = get_workspace(workspace_id)
        worklog = get_worklog(workspace_id, worklog_id)
        jira = _jira(request, workspace)
        try:
            result = push_line(worklog, workspace, jira)
        finally:
            _close(jira)

        return result

    @api.post(
        "/workspace/{workspace_id}/worklogs/{worklog_id}/delete-in-jira",
        tags=["Push"],
        summary="Delete the Jira worklog and unlink",
    )
    @db_request
    def unsync_line(workspace_id: int, worklog_id: int, request: Request):
        workspace = get_workspace(workspace_id)
        worklog = get_worklog(workspace_id, worklog_id)
        delete_in_jira(worklog, workspace, request.app.state.jira_factory)

        return worklog_public(worklog)

    @api.post(
        "/workspace/{workspace_id}/worklogs/{worklog_id}/reset-to-draft",
        tags=["Push"],
        summary="Unlink locally without calling Jira",
    )
    @db_request
    def reset_line(workspace_id: int, worklog_id: int):
        worklog = get_worklog(workspace_id, worklog_id)
        reset_to_draft(worklog)

        return worklog_public(worklog)

    @api.post(
        "/workspace/{workspace_id}/days/{work_date}/push",
        tags=["Push"],
        summary="Sync card: push all draft and error lines that day",
    )
    @db_request
    def push_day(workspace_id: int, work_date: date_type, request: Request):
        """One request for the whole card. Skips synced lines. One failure does not abort the rest."""
        workspace = get_workspace(workspace_id)
        lines = day_lines(workspace_id, work_date)
        results = bulk_push(lines, workspace, request.app.state.jira_factory)

        return {"results": results}

    @api.post(
        "/workspace/{workspace_id}/push",
        tags=["Push"],
        summary="Push all draft and error lines in a date range",
    )
    @db_request
    def push_range(
        workspace_id: int,
        request: Request,
        date_from: date_type = Query(..., alias="from"),
        date_to: date_type = Query(..., alias="to"),
    ):
        workspace = get_workspace(workspace_id)
        lines = range_lines(workspace_id, date_from, date_to)
        results = bulk_push(lines, workspace, request.app.state.jira_factory)

        return {"results": results}

    @api.get(
        "/workspace/{workspace_id}/reports",
        tags=["Reports"],
        summary="Local hours and tasks for a month or week",
    )
    @db_request
    def reports(
        workspace_id: int,
        period: str = "month",
        anchor: date_type | None = Query(default=None, alias="date"),
    ):
        get_workspace(workspace_id)
        start, end = report_bounds(period, anchor or date_type.today())
        lines = range_lines(workspace_id, start, end)

        return build_report(lines, period, start, end)

    app.include_router(api)

    if WEB_DIR.exists():
        app.mount("/web", WebStaticFiles(directory=WEB_DIR, html=True), name="web")

    return app


def create_app_from_settings() -> FastAPI:
    settings = Settings()

    return create_app(
        sqlite_db_path=settings.sqlite_db_path,
        basic_user=settings.basic_user,
        basic_password=settings.basic_password,
        log_level=settings.log_level,
    )


def main() -> None:
    settings = Settings()
    uvicorn.run(
        "api.app:create_app_from_settings",
        factory=True,
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
    )
