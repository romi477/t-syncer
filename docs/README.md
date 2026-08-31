# Documentation

Operator guide (install, `.env`, local/Docker run): [`../README.md`](../README.md).

Session contract for agents: [`../CLAUDE.md`](../CLAUDE.md). Where that file and these pages disagree, **this directory wins**.

| Page | What it holds |
|------|----------------|
| [design.md](design.md) | Domain: workspace, day card, lines, tags, reports, sync state |
| [api.md](api.md) | HTTP routes as implemented. Live Swagger: `/docs` |
| [jira.md](jira.md) | Jira Cloud REST v3 calls from `t_syncer/api/jira.py` |

The shipped UI is `t_syncer/web/` (`index.html`, `app.js`, `app.css`). There is no template compiler and no second backend.
