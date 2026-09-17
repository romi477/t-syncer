# Changelog

All notable changes to T-Syncer are recorded here.
This project follows [Semantic Versioning](https://semver.org/).

## [1.0.1] - 2026-09-17

- Worklog message: the first letter is capitalized as it is typed.
- Reports: the three summary cards carry the application blue instead of neutral ink.

## [1.0.0] - 2026-08-31

- Workspaces: one Jira Cloud site each, probed with `GET /rest/api/3/myself` on save; the API token is never returned in full.
- Day card: worklog lines with issue key, tag, message, same-day start–end and a live total.
- Seven tags (`DEV`, `SUP`, `QA`, `DOC`, `REL`, `INT`, `DEM`) assembled into the Jira comment as Atlassian Document Format.
- Shorthand input: `qbo 120` becomes `QBO-120`, `930` becomes `09:00`, ±1h / ±30m / ±15m steppers.
- Push to Jira per line, per day or over a date range; already synced lines are skipped and a line is never sent twice.
- Unsync a line through Delete-in-Jira or Reset-to-draft, then edit and push again.
- Reports: local calendar-month or ISO-week totals per issue key.
- Write API for other tools: `POST /api/workspace/{id}/worklogs` takes many days in one request; `GET /api/workspace/{id}/worklogs/{id}` returns a line's stored metadata.
- Web UI at `/web`, JSON API at `/api`, and OpenAPI (`/docs`, `/redoc`, `/openapi.json`) behind HTTP Basic Auth; only `/health` is public.
- Docker Compose setup with a `/health` healthcheck.

[1.0.1]: https://github.com/romi477/t-syncer/releases/tag/v1.0.1
[1.0.0]: https://github.com/romi477/t-syncer/releases/tag/v1.0.0
