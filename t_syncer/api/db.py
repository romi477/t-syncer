from functools import wraps
from pathlib import Path

from peewee import SqliteDatabase

from api.config import ROOT

# Deferred: the filename only arrives from Settings when the app starts.
db = SqliteDatabase(None)

_PRAGMAS = {
    "journal_mode": "wal",
    "foreign_keys": 1,
    "busy_timeout": 5000,
}


def resolve_sqlite_path(path: str) -> str:
    candidate = Path(path)
    if candidate.is_absolute():

        return str(candidate)

    return str(ROOT / candidate)


def close_db() -> None:
    if db.deferred:
        return
    if not db.is_closed():
        db.close()


def init_db(sqlite_db_path: str) -> None:
    from api import models  # noqa: F401 — bind the models before creating tables

    filename = resolve_sqlite_path(sqlite_db_path)
    Path(filename).parent.mkdir(parents=True, exist_ok=True)
    close_db()
    db.init(filename, pragmas=_PRAGMAS)
    with db.connection_context():
        db.create_tables([models.Workspace, models.Worklog, models.DayMark])
        present = {column.name for column in db.get_columns("workspaces")}
        if "day_start" not in present:
            db.execute_sql(
                "ALTER TABLE workspaces ADD COLUMN day_start TEXT NOT NULL DEFAULT '09:00'"
            )
        if "day_hours" not in present:
            db.execute_sql(
                "ALTER TABLE workspaces ADD COLUMN day_hours INTEGER NOT NULL DEFAULT 8"
            )
        if "report_hours" not in present:
            db.execute_sql(
                "ALTER TABLE workspaces ADD COLUMN report_hours INTEGER NOT NULL DEFAULT 10"
            )


def db_request(func):
    """Open the connection and release it inside one call.

    Peewee keeps connection state in a thread local and FastAPI may run a
    request's parts on different threadpool threads, so the connection must
    never outlive the handler call. Statements commit as they run; a route that
    needs several writes to land together says so with `db.atomic()`.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        with db.connection_context():

            return func(*args, **kwargs)

    return wrapper
