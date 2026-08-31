# T-Syncer

Local-first timesheet for one developer. Fill a day here, push worklogs to Jira Cloud.
SQLite is the source of truth. Jira is write-only — we never import existing worklogs.

This file is the short contract for working sessions. How to run: [`README.md`](README.md).
Domain, HTTP API, and Jira Cloud calls: [`docs/`](docs/README.md).
Where this file and `docs/` disagree, **`docs/` wins**.

## Language

Discussion with the user may be in Russian. **All code, comments, commit messages,
documentation, and UI text are in English.**

## Stack

- Python **3.12** (`requires-python = ">=3.12,<3.13"`), FastAPI, peewee, SQLite, Pydantic v2, httpx
- Vanilla JS + HTML + CSS, no build step, static files in `t_syncer/web/` served at `/web`
- JSON API under `/api` (the web UI uses this API; there is no second backend)
- pytest + FastAPI TestClient; fake Jira in tests — do not call a live Jira site from tests
- One operator. HTTP Basic Auth on **both** `/web` and `/api` from env
 (`TSYNCER_BASIC_USER`, `TSYNCER_BASIC_PASSWORD`). Not the Jira token.
 Swagger and OpenAPI (`/docs`, `/redoc`, `/openapi.json`) use the same Basic Auth.
 `/health` is public for the Compose healthcheck only.
- Dependencies pinned with `==` in `pyproject.toml`; full freeze in `uv.lock`. Use **uv**, not pip.
- Compose (`compose.yaml`) interpolates every runtime value from `.env`.

When implementing, use official docs (FastAPI, Jira Cloud REST API v3, peewee). Do not invent
REST paths, ADF comment shape, or `started` timestamp format.

## Domain rules (do not weaken)

- **Workspace** = one Jira Cloud site (name, base URL, email, API token, timezone).
  No Jira `accountId` field. `GET /rest/api/3/myself` only probes the token.
- **Day card** = one date in a workspace: lines + live total. Save, edit, sync the card.
- Sidebar **+** creates a workspace (same settings sheet, title New workspace).
- **Reports tab** = local aggregation for the current workspace. Default **calendar month**;
  ISO week is the other option. Totals: hours + distinct issue keys. Per task: hours,
  days with work, first–last date in the period. Not a Jira report; not CSV.
- **Worklog line** = issue key + optional tag + message + same-day start–end.
  Duration is computed (integer minutes). Display `2h 20m`.
  Time steppers: ±1h / ±30m / ±15m. Overlaps allowed. `qbo 120` → `QBO-120`;
  `930` → `09:00`.
- **Jira comment** is assembled, never typed with brackets:
  `[QBO-120] [DEV] Text message` or `[QBO-120] Text message` if no tag.
  Sent as Atlassian Document Format (API v3).
- **Tags:** seven codes `DEV`, `SUP`, `QA`, `DOC`, `REL`, `INT`, `DEM`.
  The code string (`"dev"`) is the identity everywhere, including `worklogs.tag`.
  Unknown code → empty tag,
  line still saved. Support is `SUP`, not `SUB`. `INT` = internal communications.
- **External write API:** `POST /api/workspace/{id}/worklogs` (JSON array of `{date, lines}`). One line: `POST /api/workspace/{id}/days/{date}/worklogs`.
  Reports: `GET /api/workspace/{id}/reports?period=month|week&date=…` (for `/web`).
- **Jira HTTP** lives in `t_syncer/api/jira.py`. Routes do not call httpx.
  Basic auth (email + token), `GET myself` on workspace save, `GET issue` before POST,
  `notifyUsers=false`, `adjustEstimate=leave`, `started` via `%Y-%m-%dT%H:%M:%S.000%z`,
  GET 404/400 = missing issue.
- **Push-only.** Missing issue → that line errors on push, others continue.
  Bulk push skips `synced` lines (no duplicate POSTs).
- **Synced line:** local delete blocked. Unsync via Delete-in-Jira (404 = already gone)
  or Reset-to-draft (local unlink, no Jira call). Then edit / local-delete / push again.
- **Always send `started`** (`YYYY-MM-DDTHH:MM:SS.000±HHMM` from date + start + workspace TZ).
  Omitting it makes Jira stamp "now" and breaks backfill.

## Conventions

- TDD: failing test first, then minimal implementation.
- `return` in Python functions always comes after a blank line.
- API token is never returned in full; blank on update means keep stored token.
- peewee: models subclass `BaseModel`, queries are `Model.select().where(…)` and
  `Model.get_or_none(…)`. Every mutation ends in an explicit `.save()` /
  `.create()` / `.delete_instance()`.
- **Every `/api` handler carries `@db_request`** (from `api.db`), directly under the
  route decorator. peewee keeps the connection in a thread local and FastAPI may run
  the parts of one request on different threadpool threads, so the connection must
  open and close inside a single handler call. Never move this into a `Depends(...)`
  generator — that reintroduces cross-thread corruption and lost commits.
- Statements commit as they run. That is what keeps a pushed worklog durable: the row
  is saved the moment Jira accepts it. Wrap several writes in `db.atomic()` only when
  they must land together (see `create_days`).
- No SPA framework, no build step, no extra deps without a docs change.
- Do not commit `.env`.

## Layout

```
t_syncer/api/     FastAPI app, peewee models, Jira client, tag catalog
t_syncer/web/     static UI at /web (index.html, app.js, app.css)
t_syncer/Dockerfile
tests/            pytest
scripts/          local and Docker wrappers
docs/             design, HTTP API, Jira Cloud calls
compose.yaml      Compose v2 (env from .env)
README.md         how to run
```

## Run

See [`README.md`](README.md). Short version:

```bash
./scripts/local-setup.sh
./scripts/local-run.sh

./scripts/docker-run.sh
./scripts/docker-logs.sh
./scripts/docker-stop.sh
```

UI: `http://127.0.0.1:7100/web` (HTTP Basic). Unauthenticated `GET /health` is for the compose healthcheck only.
