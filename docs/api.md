# HTTP API

All `/api/*`, `/web/*`, `/docs`, `/redoc`, and `/openapi.json` require HTTP Basic (`TSYNCER_BASIC_USER` / `TSYNCER_BASIC_PASSWORD`).
`GET /health` is public (Compose healthcheck).

Interactive OpenAPI: **[http://127.0.0.1:7100/docs](http://127.0.0.1:7100/docs)** (Swagger UI) and `/redoc`.
Click **Authorize** there before trying `/api` routes. That login is not the Jira token.

Tag in JSON is always the **code string**, never a numeric id. Unknown code → empty tag, line still saved (not 4xx).

Jira credentials stay on the workspace; they are not the request auth. The API never returns `jira_api_token` in full (`****`).

## Public

| Method | Path | Notes |
|--------|------|--------|
| GET | `/health` | `{"status":"ok"}` — Compose healthcheck only |

## App shell (Basic Auth)

| Method | Path | Notes |
|--------|------|--------|
| GET | `/` | 307 to `/web` |
| GET | `/web` | Static UI (`t_syncer/web/`) |
| GET | `/docs` | Swagger UI (OpenAPI) |
| GET | `/redoc` | ReDoc |
| GET | `/openapi.json` | OpenAPI spec |

## Workspaces

| Method | Path | Body |
|--------|------|------|
| GET | `/api/workspace` | — |
| POST | `/api/workspace` | `WorkspaceIn` (201). Probes Jira `myself`. Strips trailing slash on the base URL. |
| GET | `/api/workspace/{id}` | — |
| PATCH | `/api/workspace/{id}` | `WorkspaceUpdate`. Blank / omitted `jira_api_token` keeps the stored token. Re-probes `myself`. |
| DELETE | `/api/workspace/{id}` | 204. Cascades worklogs. |

`WorkspaceIn`: `name`, `jira_base_url`, `jira_email`, `jira_api_token`, `timezone` (default `Europe/Kyiv`).

Rejected Jira login → 400. Unreachable Jira → 502. Unknown timezone → 400.

## Days and lines

| Method | Path | Notes |
|--------|------|--------|
| GET | `/api/workspace/{id}/days?from=&to=` | Per-day summaries (`total_minutes`, `pending_minutes`, `status`) |
| GET | `/api/workspace/{id}/days/{YYYY-MM-DD}` | Card: lines + `total_minutes` |
| POST | `/api/workspace/{id}/worklogs` | Bulk create (201). JSON array of days. External write path. |
| POST | `/api/workspace/{id}/days/{YYYY-MM-DD}/worklogs` | Create one line (201). |
| GET | `/api/workspace/{id}/worklogs/{wid}` | SQLite row plus related workspace. Token is `****`. |
| PATCH | `/api/workspace/{id}/worklogs/{wid}` | Draft/error only. 409 if synced. |
| DELETE | `/api/workspace/{id}/worklogs/{wid}` | Draft/error only. 409 if synced. 204. |

Create / patch body (one line):

```json
{
  "issue_key": "QBO-120",
  "tag": "dev",
  "message": "Implement tags synchronization",
  "start": "09:00",
  "end": "10:00"
}
```

`tag`, `start`, `end` are optional. `start` / `end` accept shorthand (`930` → `09:00`). End after start when both are set; incomplete range stores `duration_minutes = 0`.

Create/patch response includes the line plus `total_minutes` for that day after the change.

Bulk create body is a JSON **array** (no wrapping object). Each item is one day:

```json
[
  {
    "date": "2026-08-19",
    "lines": [
      {
        "issue_key": "RDI-1",
        "tag": "int",
        "message": "Team meeting",
        "start": "09:30",
        "end": "09:45"
      }
    ]
  }
]
```

201 response is the same array shape, with `total_minutes` and saved `lines` (ids, status, duration) per day. Unknown workspace → 404. Line rules match single create (unknown tag → empty tag, still saved).

## Push and unsync

| Method | Path | Notes |
|--------|------|--------|
| POST | `/api/workspace/{id}/worklogs/{wid}/push` | One line. Already `synced` → same line with `"skipped": true`. |
| POST | `/api/workspace/{id}/days/{YYYY-MM-DD}/push` | All draft/error lines that day. Skip synced. |
| POST | `/api/workspace/{id}/push?from=&to=` | All draft/error lines in the inclusive date range. |
| POST | `/api/workspace/{id}/worklogs/{wid}/delete-in-jira` | Synced only. Jira 404 counts as success. Line becomes draft. |
| POST | `/api/workspace/{id}/worklogs/{wid}/reset-to-draft` | Synced only. No Jira call. |

Bulk response:

```json
{
  "results": [
    { "id": 1, "status": "synced", "last_error": null },
    { "id": 2, "status": "error", "last_error": "Issue QBO-999 does not exist" },
    { "id": 3, "status": "skipped", "last_error": null }
  ]
}
```

## Reports

`GET /api/workspace/{id}/reports?period=month|week&date=YYYY-MM-DD`

- `period` default `month`. Anything other than `month` or `week` → 400.
- `date` is the anchor (default today). Month = calendar month of that date. Week = Monday–Sunday containing it.

Response: `period`, `from`, `to`, `total_minutes`, `task_count`, `days_with_work`, `tasks[]` (`issue_key`, `total_minutes`, `days`, `first_date`, `last_date`, `share`).
