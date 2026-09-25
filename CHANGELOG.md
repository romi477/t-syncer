# Changelog

All notable changes to T-Syncer are recorded here.
This project follows [Semantic Versioning](https://semver.org/).

## [1.1.0] - 2026-09-25

- Day card: a narrow window keeps the message and the row actions inside the card.
- Time steppers still move when the end is earlier than the start. That end is highlighted. They stop only before 00:00 and past midnight.
- Workspace settings: collapsed Advanced Settings, **Work starts at** (`HH:MM`). An empty start uses the previous line’s end, otherwise this time. Default `09:00`. **Working day (hours)** (default 8) is the length used for the title capacity and the blue projection. **Hours on the report** (default 10, at least the working day, at most 24) is how many hour-cells the day bar draws. The bar is a single row: the first cells, one per working-day hour, keep the usual color, and the rest are light yellow. Time past the report length does not add cells.
- Duplicate copies the issue, tag, and message, and sets both start and end to the latest end on that day.
- Reports open on **Days**: every day of the month or week, one hour-cell per displayed hour on a single bar, and a running day number. The first cells match the working-day length and use the usual color; further cells are light yellow. Saturday, Sunday, and holidays use the rose accent on the working-day cells. **Tasks** lists issues under their project code (`QBO`, `RDCN`); the groups stay open, and the group header is blue.
- The period title shows working days, their capacity, and a blue projection, for example `September 2026 / 19d (152h: 96h)` when a working day is 8h. Capacity is weekdays minus holidays, times the working-day length. The projection keeps hours already logged and tops today and later working days up to that length; a remaining holiday adds no hypothetical hours. Hours already logged on a holiday stay in the report.
- A day card has a Holiday toggle. The calendar draws that day with a rose outline.

## [1.0.1] - 2026-09-17

- Worklog message: the first letter is capitalized as it is typed.
- Reports: the three summary cards carry the application blue instead of neutral ink.
- Ctrl+Cmd+← and Ctrl+Cmd+→ move between the Calendar and Reports tabs, wrapping around.

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

[1.1.0]: https://github.com/romi477/t-syncer/releases/tag/v1.1.0
[1.0.1]: https://github.com/romi477/t-syncer/releases/tag/v1.0.1
[1.0.0]: https://github.com/romi477/t-syncer/releases/tag/v1.0.0
