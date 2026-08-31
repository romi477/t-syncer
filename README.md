# T-Syncer

Local-first timesheet for one developer. Fill a day here, then push worklogs to Jira Cloud.

SQLite is the source of truth. Jira is write-only: T-Syncer never imports existing worklogs.

The web UI and the JSON API are the same app. One operator, HTTP Basic Auth on `/web`, `/api`, and OpenAPI (`/docs`, `/redoc`, `/openapi.json`). Those credentials are not the Jira token. Only `/health` is public.

## Requirements

- [uv](https://docs.astral.sh/uv/getting-started/installation/) (local run and tests)
- Python **3.12** (`requires-python = ">=3.12,<3.13"`; uv installs it)
- Docker Engine with Compose v2 (container run)

## Quick start (local)

```bash
cp .env.example .env
# set TSYNCER_BASIC_USER and TSYNCER_BASIC_PASSWORD

./scripts/local-setup.sh
./scripts/local-run.sh
```

Then open [http://127.0.0.1:7100/web](http://127.0.0.1:7100/web) and sign in with the Basic Auth user from `.env`.

`local-setup.sh` creates `.env` from the example if it is missing, then runs `uv sync --extra dev`.

`local-run.sh` always binds **127.0.0.1**, even when `TSYNCER_HOST=0.0.0.0` in `.env` (that value is for Docker). Override with `HOST` / `PORT` if needed:

```bash
HOST=127.0.0.1 PORT=7100 ./scripts/local-run.sh
```

## Docker

All Compose interpolation and container env come from `.env`. There are no credentials, ports, or database path hardcoded in `compose.yaml`.

```bash
cp .env.example .env
# set TSYNCER_BASIC_USER and TSYNCER_BASIC_PASSWORD
# keep TSYNCER_HOST=0.0.0.0 so the published port can reach the app

./scripts/docker-run.sh
./scripts/docker-logs.sh
./scripts/docker-stop.sh
```

`docker-run.sh` creates the SQLite file from `TSYNCER_SQLITE_DB_PATH` if it does not exist (a bind mount must be a file, not a directory), then `docker compose up --build --detach`.

The published port is hardcoded to `127.0.0.1` in `compose.yaml`, so the app is never reachable from outside the host. Docker writes its own DNAT rules and a `0.0.0.0` publish would bypass `ufw`, so this is not left to an environment variable. To reach it from elsewhere, put a TLS-terminating reverse proxy in front of `127.0.0.1:${TSYNCER_PORT}` — Basic Auth over plain HTTP sends the credentials with every request.

The container runs the code baked into the image; the working tree is not mounted. Rebuild to deploy a change, or use `./scripts/local-run.sh` while developing.

| Script | What it does |
|--------|----------------|
| `./scripts/docker-build.sh` | `docker compose build` |
| `./scripts/docker-run.sh` | Build, start detached, print URLs |
| `./scripts/docker-logs.sh` | Follow logs |
| `./scripts/docker-stop.sh` | `docker compose down` |

UI: `http://127.0.0.1:7100/web` (`TSYNCER_PORT` from `.env`). Compose publishes on loopback only.

## Environment

Copy `.env.example` to `.env`. Do not commit `.env`.

| Variable | Purpose |
|----------|---------|
| `TSYNCER_BASIC_USER` | HTTP Basic user for `/web` and `/api` |
| `TSYNCER_BASIC_PASSWORD` | HTTP Basic password |
| `TSYNCER_HOST` | Uvicorn bind address. Use `0.0.0.0` for Compose. Local run ignores this and binds `127.0.0.1`. |
| `TSYNCER_PORT` | App port. Compose publishes `host:port → container:port` with this value. |
| `TSYNCER_RELOAD` | Uvicorn autoreload for `python -m api`. Off by default; a restart mid-push loses the transaction while Jira has already been written to. `scripts/local-run.sh` passes `--reload` itself. |
| `TSYNCER_LOG_LEVEL` | Level for the app's own log (`tsyncer` logger) on stdout. Default `INFO`. peewee's query log is pinned off at every level — it would print the Jira API token with the SQL parameters. |
| `TSYNCER_SQLITE_DB_PATH` | SQLite **filename or relative path**, not a SQLAlchemy URL. Resolved from the repo root locally and `/opt/app` in Docker. Example: `tsyncer.db`. |

Jira Cloud email and API token are **not** in `.env`. They are stored per workspace in SQLite. The API never returns the token in full (`****`). A blank token on update keeps the stored value.

## URLs

| Path | Auth | What |
|------|------|------|
| `/` | Basic | Redirect to `/web` |
| `/web` | Basic | Calendar (day cards) and Reports |
| `/api/…` | Basic | JSON API used by the UI and by scripts |
| `/docs` | Basic | Swagger UI — interactive OpenAPI |
| `/redoc` | Basic | ReDoc |
| `/openapi.json` | Basic | OpenAPI spec |
| `/health` | none | Liveness JSON `{"status":"ok"}` (Compose healthcheck) |

Example, after a workspace exists:

```bash
curl -u "$TSYNCER_BASIC_USER:$TSYNCER_BASIC_PASSWORD" \
  http://127.0.0.1:7100/api/workspace
```

External line create (same as the UI):

`POST /api/workspace/{id}/days/{YYYY-MM-DD}/worklogs`

Bulk create (several days in one request):

`POST /api/workspace/{id}/worklogs` — JSON array of `{ "date": "YYYY-MM-DD", "lines": [ … ] }`.

## How it works

1. Create a **workspace** (one Jira Cloud site: name, base URL, email, API token, timezone). Save probes `GET /rest/api/3/myself`.
2. Open a **day card**, add lines: issue key, optional tag, message, same-day start–end. Duration is computed. Overlaps are allowed.
3. **Push** drafts to Jira. Synced lines are skipped on bulk push (no duplicate POSTs). A missing issue errors that line; others continue.
4. A synced line cannot be edited or deleted locally. Unsync with Delete-in-Jira (404 means already gone) or Reset-to-draft (local unlink, no Jira call), then edit and push again.

Issue shorthand: `qbo 120` → `QBO-120`. Time shorthand: `930` → `09:00`.

Tags (send the code string, e.g. `"dev"`): `DEV`, `SUP`, `QA`, `DOC`, `REL`, `INT`, `DEM`. Unknown code → empty tag, line still saved. Support is `SUP`, not `SUB`.

Jira comment is assembled, not typed with brackets: `[QBO-120] [DEV] Text message`, or without a tag `[QBO-120] Text message`. Posted as Atlassian Document Format (REST v3). `started` is always sent in the workspace timezone so backfill does not become “now”.

**Reports** aggregate **local** SQLite lines for the current workspace (default calendar month; ISO week is the other option). Not a Jira report, not CSV.

## Tests

```bash
./scripts/local-setup.sh
uv run pytest
```

Tests use an isolated SQLite file and a fake Jira client. They do not call a real Jira site.

## Documentation

| File | What |
|------|------|
| [docs/README.md](docs/README.md) | Index |
| [docs/design.md](docs/design.md) | Domain and sync rules |
| [docs/api.md](docs/api.md) | HTTP API |
| [docs/jira.md](docs/jira.md) | Jira Cloud REST v3 as used here |

## Deploy behind nginx

Compose publishes on `127.0.0.1` only, so nginx terminates TLS and is the single way in. Set `TSYNCER_PORT` in `.env` to the port you proxy to, and use a long random Basic Auth password — it is the only thing in front of the stored Jira API token.

```bash
git clone https://github.com/romi477/t-syncer.git && cd t-syncer
cp .env.example .env && chmod 600 .env   # then fill in credentials and TSYNCER_PORT
./scripts/docker-run.sh
curl http://127.0.0.1:${TSYNCER_PORT}/health
```

Then the proxy. [`deploy/nginx/t-syncer.conf`](deploy/nginx/t-syncer.conf) is a ready server block — set `server_name` and check that `proxy_pass` matches `TSYNCER_PORT`.

```bash
sudo cp deploy/nginx/t-syncer.conf /etc/nginx/sites-available/t-syncer.conf
sudo ln -s /etc/nginx/sites-available/t-syncer.conf /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

TLS with certbot (Debian/Ubuntu). The domain must already resolve to this server and ports 80 and 443 must be open:

```bash
sudo snap install --classic certbot
sudo ln -s /snap/bin/certbot /usr/bin/certbot
sudo certbot --nginx -d example.com
sudo certbot renew --dry-run
```

Certbot rewrites the server block with the certificate and the redirect from port 80, and installs a renewal timer. Do not open the app port in the firewall — it is not reachable from outside the host anyway.

## Layout

```
t_syncer/api/     FastAPI app, peewee models, Jira client, tag catalog
t_syncer/web/     static UI at /web (no build step)
t_syncer/Dockerfile
tests/            pytest
scripts/          local and Docker wrappers
docs/             design, HTTP API, Jira Cloud calls
compose.yaml      Compose v2 (env from .env)
pyproject.toml    pinned direct dependencies
uv.lock           full lockfile
```

Stack: Python 3.12, FastAPI, peewee, SQLite, Pydantic v2, httpx, vanilla JS/HTML/CSS.

## License

Private / personal tool unless a license file is added.
