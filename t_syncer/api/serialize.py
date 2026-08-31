from datetime import time

from api.duration import duration_minutes
from api.models import Worklog, Workspace
from api.parse import norm_issue, norm_time
from api.tags import resolve_tag


def parse_clock(value: str | None) -> time | None:
    if value is None or str(value).strip() == "":
        return None
    normalized = norm_time(str(value))
    if not normalized:
        return None
    hours, minutes = normalized.split(":")

    return time(int(hours), int(minutes))


def fmt_clock(value: time | None) -> str | None:
    if value is None:
        return None

    return value.strftime("%H:%M")


def apply_duration(worklog: Worklog) -> None:
    if worklog.start_time and worklog.end_time:
        worklog.duration_minutes = duration_minutes(
            worklog.start_time,
            worklog.end_time,
            strict=True,
        )
        return
    worklog.duration_minutes = 0


def apply_tag(worklog: Worklog, code: str | None) -> None:
    tag = resolve_tag(code)
    worklog.tag = tag.code if tag else ""


def workspace_public(workspace: Workspace) -> dict:
    return {
        "id": workspace.id,
        "name": workspace.name,
        "jira_base_url": workspace.jira_base_url,
        "jira_email": workspace.jira_email,
        "jira_api_token": "****",
        "timezone": workspace.timezone,
        "jira_display_name": workspace.jira_display_name,
    }


def worklog_public(
    worklog: Worklog,
    *,
    total_minutes: int | None = None,
    skipped: bool = False,
) -> dict:
    payload = {
        "id": worklog.id,
        "work_date": worklog.work_date.isoformat(),
        "start": fmt_clock(worklog.start_time),
        "end": fmt_clock(worklog.end_time),
        "duration_minutes": worklog.duration_minutes,
        "issue_key": worklog.issue_key or "",
        "tag": worklog.tag or None,
        "message": worklog.message or "",
        "status": worklog.status,
        "jira_worklog_id": worklog.jira_worklog_id or None,
        "last_error": worklog.last_error or None,
    }
    if total_minutes is not None:
        payload["total_minutes"] = total_minutes
    if skipped:
        payload["skipped"] = True

    return payload


def worklog_metadata(worklog: Worklog) -> dict:

    return {
        "id": worklog.id,
        "workspace_id": worklog.workspace.id,
        "workspace": workspace_public(worklog.workspace),
        "work_date": worklog.work_date.isoformat(),
        "start_time": fmt_clock(worklog.start_time),
        "end_time": fmt_clock(worklog.end_time),
        "duration_minutes": worklog.duration_minutes,
        "issue_key": worklog.issue_key or "",
        "tag": worklog.tag or None,
        "message": worklog.message or "",
        "status": worklog.status,
        "jira_worklog_id": worklog.jira_worklog_id or None,
        "last_error": worklog.last_error or None,
    }


def day_total(worklogs: list[Worklog]) -> int:
    return sum(item.duration_minutes for item in worklogs)


def fill_line_fields(worklog: Worklog, payload, *, fields_set: set[str] | None = None) -> None:
    names = fields_set if fields_set is not None else payload.model_fields_set
    if "issue_key" in names:
        worklog.issue_key = norm_issue(payload.issue_key or "")
    if "message" in names:
        worklog.message = payload.message or ""
    if "tag" in names:
        apply_tag(worklog, payload.tag)
    if "start" in names:
        worklog.start_time = parse_clock(payload.start)
    if "end" in names:
        worklog.end_time = parse_clock(payload.end)
    apply_duration(worklog)


def day_status(worklogs: list[Worklog]) -> str:
    statuses = {item.status for item in worklogs}
    if "error" in statuses:
        return "error"
    if "draft" in statuses:
        return "draft"

    return "synced"
