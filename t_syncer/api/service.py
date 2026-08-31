from datetime import date

from fastapi import HTTPException
from zoneinfo import ZoneInfo

from api.db import db
from api.comments import format_jira_comment, to_adf
from api.duration import format_jira_started
from api.jira import JiraAuthError, JiraError, JiraIssueMissing
from api.logging import logger
from api.models import Worklog, Workspace
from api.parse import norm_issue
from api.periods import period_bounds
from api.serialize import (
    apply_duration,
    apply_tag,
    day_status,
    day_total,
    fill_line_fields,
    parse_clock,
    worklog_public,
)

EMPTY_ISSUE_KEY = "(empty)"


def get_workspace(workspace_id: int) -> Workspace:
    workspace = Workspace.get_or_none(Workspace.id == workspace_id)
    if workspace is None:
        raise HTTPException(status_code=404, detail="Workspace not found")

    return workspace


def get_worklog(workspace_id: int, worklog_id: int) -> Worklog:
    worklog = Worklog.get_or_none(Worklog.id == worklog_id)
    if worklog is None or worklog.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Worklog not found")

    return worklog


def require_editable(worklog: Worklog) -> None:
    if worklog.status == "synced":
        raise HTTPException(status_code=409, detail="Synced line cannot be changed locally")


def normalize_base_url(url: str) -> str:
    return url.strip().rstrip("/")


def validate_timezone(name: str) -> str:
    try:
        ZoneInfo(name)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Unknown timezone") from exc

    return name


def probe_jira(jira_factory, base_url: str, email: str, token: str) -> str:
    client = jira_factory(base_url, email, token)
    try:
        data = client.myself()
    except JiraAuthError as exc:
        logger.warning("jira probe rejected base_url=%s reason=%s", base_url, exc.message)
        raise HTTPException(status_code=400, detail=exc.message) from exc
    except JiraError as exc:
        logger.warning("jira probe unreachable base_url=%s reason=%s", base_url, exc.message)
        raise HTTPException(status_code=502, detail="Jira is unreachable") from exc
    finally:
        close = getattr(client, "close", None)
        if close:
            close()

    return data.get("displayName") or ""


def day_lines(workspace_id: int, work_date: date) -> list[Worklog]:
    return list(
        Worklog.select()
        .where(Worklog.workspace == workspace_id, Worklog.work_date == work_date)
        .order_by(Worklog.id)
    )


def range_lines(workspace_id: int, start: date, end: date) -> list[Worklog]:
    return list(
        Worklog.select()
        .where(
            Worklog.workspace == workspace_id,
            Worklog.work_date >= start,
            Worklog.work_date <= end,
        )
        .order_by(Worklog.work_date, Worklog.id)
    )


def create_line(workspace: Workspace, work_date: date, payload) -> Worklog:
    worklog = Worklog(
        workspace=workspace,
        work_date=work_date,
        issue_key=norm_issue(payload.issue_key or ""),
        message=payload.message or "",
        start_time=parse_clock(payload.start),
        end_time=parse_clock(payload.end),
        status="draft",
    )
    apply_tag(worklog, payload.tag)
    try:
        apply_duration(worklog)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    worklog.save()

    return worklog


def create_days(workspace: Workspace, days: list) -> list[dict]:
    result = []
    # One rejected line must not leave half of the payload behind.
    with db.atomic():
        for day in days:
            for line in day.lines:
                create_line(workspace, day.date, line)
            lines = day_lines(workspace.id, day.date)
            result.append(
                {
                    "date": day.date.isoformat(),
                    "total_minutes": day_total(lines),
                    "lines": [worklog_public(row) for row in lines],
                }
            )

    return result


def patch_line(worklog: Worklog, payload) -> Worklog:
    require_editable(worklog)
    try:
        fill_line_fields(worklog, payload, fields_set=payload.model_fields_set)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    worklog.save()

    return worklog


def delete_line(worklog: Worklog) -> None:
    require_editable(worklog)
    worklog.delete_instance()


def _fail(worklog: Worklog, message: str) -> Worklog:
    worklog.status = "error"
    worklog.last_error = message
    worklog.save()

    return worklog


def push_line(worklog: Worklog, workspace: Workspace, jira) -> dict:
    if worklog.status == "synced":

        return worklog_public(worklog, skipped=True)
    if worklog.start_time is None or worklog.end_time is None or worklog.duration_minutes <= 0:
        logger.warning("push skipped line=%s reason=incomplete time range", worklog.id)
        _fail(worklog, "Incomplete time range")

        return worklog_public(worklog)
    tag = worklog.tag or None
    comment = format_jira_comment(worklog.issue_key, tag, worklog.message or "")
    try:
        jira.get_issue(worklog.issue_key)
        result = jira.create_worklog(
            worklog.issue_key,
            started=format_jira_started(
                worklog.work_date,
                worklog.start_time,
                workspace.timezone,
            ),
            time_spent_seconds=worklog.duration_minutes * 60,
            comment=to_adf(comment),
        )
    except JiraIssueMissing as exc:
        logger.warning(
            "push failed line=%s issue=%s reason=%s", worklog.id, worklog.issue_key, exc.message
        )
        _fail(worklog, exc.message)

        return worklog_public(worklog)
    except JiraError as exc:
        logger.warning(
            "push failed line=%s issue=%s reason=%s", worklog.id, worklog.issue_key, exc.message
        )
        _fail(worklog, exc.message)

        return worklog_public(worklog)
    # Jira has accepted the write. Commit before anything else can fail, or a
    # rollback would leave a draft that the next push sends to Jira again.
    worklog.status = "synced"
    worklog.jira_worklog_id = str(result.get("id") or "")
    worklog.last_error = ""
    worklog.save()
    logger.info(
        "pushed line=%s issue=%s date=%s minutes=%s jira_worklog=%s",
        worklog.id,
        worklog.issue_key,
        worklog.work_date.isoformat(),
        worklog.duration_minutes,
        worklog.jira_worklog_id or "-",
    )

    return worklog_public(worklog)


def bulk_push(worklogs: list[Worklog], workspace: Workspace, jira_factory) -> list[dict]:
    jira = jira_factory(
        workspace.jira_base_url,
        workspace.jira_email,
        workspace.jira_api_token,
    )
    results = []
    try:
        for worklog in worklogs:
            try:
                pushed = push_line(worklog, workspace, jira)
            except Exception as exc:  # one broken line must not abort the card
                logger.exception("push crashed line=%s issue=%s", worklog.id, worklog.issue_key)
                _fail(worklog, f"Push failed: {exc}")
                pushed = worklog_public(worklog)
            results.append(
                {
                    "id": worklog.id,
                    "status": "skipped" if pushed.get("skipped") else pushed["status"],
                    "last_error": pushed.get("last_error"),
                }
            )
    finally:
        close = getattr(jira, "close", None)
        if close:
            close()

    return results


def delete_in_jira(worklog: Worklog, workspace: Workspace, jira_factory) -> Worklog:
    if worklog.status != "synced" or not worklog.jira_worklog_id:
        raise HTTPException(status_code=409, detail="Line is not synced")
    jira = jira_factory(
        workspace.jira_base_url,
        workspace.jira_email,
        workspace.jira_api_token,
    )
    jira_worklog_id = worklog.jira_worklog_id
    try:
        jira.delete_worklog(worklog.issue_key, jira_worklog_id)
    except JiraError as exc:
        logger.warning(
            "delete in jira failed line=%s issue=%s jira_worklog=%s reason=%s",
            worklog.id,
            worklog.issue_key,
            jira_worklog_id,
            exc.message,
        )
        raise HTTPException(status_code=502, detail=exc.message) from exc
    finally:
        close = getattr(jira, "close", None)
        if close:
            close()
    reset_to_draft(worklog)
    logger.info(
        "deleted in jira line=%s issue=%s jira_worklog=%s",
        worklog.id,
        worklog.issue_key,
        jira_worklog_id,
    )

    return worklog


def reset_to_draft(worklog: Worklog) -> Worklog:
    if worklog.status != "synced":
        raise HTTPException(status_code=409, detail="Line is not synced")
    worklog.status = "draft"
    worklog.jira_worklog_id = ""
    worklog.last_error = ""
    worklog.save()

    return worklog


def summarize_days(worklogs: list[Worklog]) -> list[dict]:
    grouped: dict[date, list[Worklog]] = {}
    for worklog in worklogs:
        grouped.setdefault(worklog.work_date, []).append(worklog)
    days = []
    for work_date in sorted(grouped):
        rows = grouped[work_date]
        pending = sum(item.duration_minutes for item in rows if item.status != "synced")
        days.append(
            {
                "date": work_date.isoformat(),
                "total_minutes": day_total(rows),
                "pending_minutes": pending,
                "status": day_status(rows),
            }
        )

    return days


def build_report(worklogs: list[Worklog], period: str, start: date, end: date) -> dict:
    by_key: dict[str, list[Worklog]] = {}
    for worklog in worklogs:
        by_key.setdefault(worklog.issue_key or EMPTY_ISSUE_KEY, []).append(worklog)
    total = day_total(worklogs)
    days_with_work = {item.work_date for item in worklogs}
    tasks = []
    for issue_key, rows in by_key.items():
        minutes = day_total(rows)
        dates = sorted(item.work_date for item in rows)
        share = (minutes / total) if total else 0
        tasks.append(
            {
                "issue_key": issue_key,
                "total_minutes": minutes,
                "days": len(set(dates)),
                "first_date": dates[0].isoformat(),
                "last_date": dates[-1].isoformat(),
                "share": share,
            }
        )
    tasks.sort(key=lambda row: (-row["total_minutes"], row["issue_key"]))
    task_count = sum(1 for issue_key in by_key if issue_key != EMPTY_ISSUE_KEY)

    return {
        "period": period,
        "from": start.isoformat(),
        "to": end.isoformat(),
        "total_minutes": total,
        "task_count": task_count,
        "days_with_work": len(days_with_work),
        "tasks": tasks,
    }


def report_bounds(period: str, anchor: date) -> tuple[date, date]:
    if period not in ("month", "week"):
        raise HTTPException(status_code=400, detail="period must be month or week")

    return period_bounds(period, anchor)
