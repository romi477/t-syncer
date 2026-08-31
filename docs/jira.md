# Jira Cloud REST v3

Implementation: `t_syncer/api/jira.py`. Routes must not call httpx.

Auth: HTTP Basic, workspace `jira_email` + `jira_api_token`, against the workspace base URL (no trailing slash).

Official reference: [Jira Cloud REST API v3](https://developer.atlassian.com/cloud/jira/platform/rest/v3/). Do not invent paths, ADF shape, or `started` format.

## Probe on workspace save

`GET /rest/api/3/myself`

Non-200 → credentials rejected (API maps this to 400). Optional cache of `displayName`.

## Issue exists

`GET /rest/api/3/issue/{issueKey}` (key URL-encoded)

| Status | Meaning |
|--------|---------|
| 200 | Issue exists; may POST a worklog |
| 400 or 404 | Missing / invalid key → line `error`, bulk continues |
| other | Line `error` with a generic failure |

Do **not** treat **POST** 400 as a missing issue. That is usually a bad body (`started` / ADF).

## Create worklog

`POST /rest/api/3/issue/{issueKey}/worklog?adjustEstimate=leave&notifyUsers=false`

```json
{
  "started": "2026-08-29T09:00:00.000+0300",
  "timeSpentSeconds": 3600,
  "comment": {
    "type": "doc",
    "version": 1,
    "content": [
      {
        "type": "paragraph",
        "content": [{ "type": "text", "text": "[QBO-120] [DEV] Text message" }]
      }
    ]
  }
}
```

`started` is **always** sent. Format from `work_date` + `start_time` + workspace timezone:

```
%Y-%m-%dT%H:%M:%S.000%z
```

Example: `2026-08-29T09:00:00.000+0300`. No trailing `Z`. If omitted, Jira stamps **now** and backfill lands on today.

`timeSpentSeconds` = `duration_minutes * 60`.

201 → store returned worklog `id`, status `synced`, clear `last_error`.

POST is **not** retried on transport errors (a retry could duplicate a worklog). GET / HEAD / DELETE / PUT retry on transport errors and on HTTP 429 (four attempts, exponential backoff).

## Delete worklog

`DELETE /rest/api/3/issue/{issueKey}/worklog/{jiraWorklogId}`

204 or **404** (already gone) → success. Local line becomes `draft`, `jira_worklog_id` cleared.

## Comment text

Assembled in `t_syncer/api/comments.py`, never typed with brackets by the user:

- With tag: `[QBO-120] [DEV] Text message`
- Without tag: `[QBO-120] Text message`
