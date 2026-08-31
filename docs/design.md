# Design

Personal local-first timesheet. SQLite is the source of truth. Jira Cloud is a write-only push target.

A developer works with several Jira Cloud sites (several customers). Each site is a **workspace**. In a workspace they pick a calendar day, add worklog lines locally, then push them to Jira.

Success: fill a day without touching Jira's UI, push the day in one action, and recover if a line was deleted in Jira by hand.

## Not in v1

- Importing worklogs that already exist in Jira
- Multi-user accounts (one Basic Auth identity for the whole app)
- Encrypting the API token at rest
- Jira project or issue catalog, autocomplete, search
- Overlap checks between ranges
- Overnight ranges (end on the next calendar day)
- Updating a Jira worklog in place (edit after sync = unsync, then push a new worklog)
- Jira Data Center / Server
- CSV/PDF download, cross-workspace reports, charts, breakdown by tag
- A stored Jira `accountId` field

## Surfaces

| Path | What |
|------|------|
| `/` | Redirect to `/web` |
| `/web` | Calendar (day cards) and Reports tabs |
| `/api` | JSON API used by the UI and by scripts |
| `/health` | Unauthenticated liveness check |

App auth is HTTP Basic from `TSYNCER_BASIC_USER` / `TSYNCER_BASIC_PASSWORD`. Jira email and token stay on the workspace row.

## Workspace

One Jira Cloud site.

| Field | Notes |
|-------|--------|
| `name` | Local label |
| `jira_base_url` | `https://example.atlassian.net`, no trailing slash |
| `jira_email` | Cloud account email. HTTP Basic user against Jira. |
| `jira_api_token` | Atlassian API token. Never returned in full (`****`). Blank on update = keep stored token. |
| `timezone` | IANA name, e.g. `Europe/Kyiv`. Used only to compose `started` on push. |
| `jira_display_name` | Cached from `GET /rest/api/3/myself` (“connected as …”). Not a form field. |

No Jira user/account id on the workspace. `myself` only **probes** that email+token work. Worklogs are created as that authenticated Jira user.

No `project` entity. The Jira project is the prefix of the issue key (`QBO-120` → QBO).

Sidebar **+** opens the same settings sheet as create (title **New workspace**). Gear opens edit for the current workspace. In edit mode a muted-red trash icon on the title row deletes that workspace and its lines (`DELETE /api/workspace/{id}`), after confirm.

## Day card

One calendar day inside a workspace: the date plus its lines plus the running total. It is not a separate table — workspace + `work_date` is enough.

Daily total = sum of `duration_minutes` for all lines on that date (draft, error, and synced).

## Worklog line

| Field | Notes |
|-------|--------|
| `work_date` | Calendar day the line belongs to |
| `start_time`, `end_time` | Same-day range. End must be after start when both are set. |
| `duration_minutes` | Computed: end − start. Integer minutes. Display as `2h 20m` (`2h` or `20m` when the other part is zero). |
| `issue_key` | Normalized on save (`qbo 120` → `QBO-120`). May be empty until push. |
| `tag` | Nullable code from the hardcoded list (JSON is the code string) |
| `message` | Free text |
| `status` | `draft` \| `synced` \| `error` |
| `jira_worklog_id` | Set after a successful push |
| `last_error` | Last push failure message, if any |

Incomplete times (missing start or end) save with `duration_minutes = 0`. Push of an incomplete line fails that line with an error; it does not crash.

Overlapping ranges on the same day **are allowed**. Overnight ranges are not.

Time shorthand: `9 00` / `930` / `9:0` → `09:00`. Non-numeric clock values save as empty, not as a 4xx.

Time steppers: ±1h / ±30m / ±15m. If start is empty, it becomes the previous line’s end on this card, else `09:00`. Plus adds to end; minus shrinks end and is a no-op if that would make end ≤ start. Crossing midnight is not applied.

## Tags

Hardcoded catalog of **seven** codes. Optional on a line. Empty tag is omitted from the Jira comment.

The tag is a **code string** end to end — in the request (`dev`, `DEV`, ` Dev `), in the row, and in the response. Trim, case-insensitive match. Hit → store the code (`DEV`). Miss or empty → no tag. A miss is not an error; the line is still saved.

The catalogue in `api/tags.py` is free to be reordered or extended by hand: a row says what its tag is without a lookup.

| Code | Label |
|------|--------|
| DEV | Development |
| SUP | Support and escalations (not `SUB`) |
| QA | Testing (separate activity) |
| DOC | Documentation |
| REL | Releases |
| INT | Internal communications (not “Interaction”) |
| DEM | Demos and customer meetings |

## Reports

Read-only aggregation of **local** lines in the current workspace (draft, error, and synced).

| Period | Range | Default |
|--------|--------|---------|
| Month | Calendar month | **Yes** |
| Week | Monday–Sunday containing the anchor date | Available |

Anchor date = `date` query param, else today.

Totals: hours and how many distinct issue keys had time in the period. Per task (sorted by hours descending): issue key, total time, days with work, first and last `work_date`, share of the period. Lines with an empty issue key are not counted as tasks.

No tag breakdown, no charts, no CSV.

## Jira comment

Built from fields. The user does not type square brackets.

- With tag: `[QBO-120] [DEV] Text message`
- Without tag: `[QBO-120] Text message`

Posted as Atlassian Document Format (API v3), not a plain string. Shape is in [jira.md](jira.md).

## Sync state

| Status | Edit | Local delete | Push | Delete in Jira | Reset to draft |
|--------|------|--------------|------|----------------|----------------|
| draft  | yes  | yes          | yes  | no             | no             |
| error  | yes  | yes          | retry| no             | no             |
| synced | no   | **blocked**  | skip | yes            | yes            |

Push one line: `GET issue` then `POST worklog`. GET 400/404 → that line `error`, continue bulk. Do **not** treat POST 400 as a missing issue (usually a bad `started` / ADF body).

Bulk push (day / `from`–`to`) skips `synced` lines. One line’s failure does not abort the rest.

A line is saved as `synced` the moment Jira accepts the write, before anything else can fail. A later error inside the same request must never turn it back into a draft — that draft would be pushed again and Jira would hold the hours twice. For the same reason a `POST worklog` is never retried after a transport error: the write may already have landed.

Delete in Jira: `DELETE` worklog. 204 or **404** (already gone) → local draft. Reset to draft is the same end state with no Jira call.

Always send `started` in the workspace timezone. Details: [jira.md](jira.md).
