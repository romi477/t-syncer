"""Pony keeps its session in a thread local, so a request must enter and leave
that session inside one call on one thread. These tests run a real uvicorn
worker pool, which is where the threads actually diverge.
"""
import os
import socket
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest
from api.db import close_db, db, init_db
from api.models import Workspace
from tests.conftest import AUTH

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))

        return sock.getsockname()[1]


def _seed_workspace(db_path) -> int:
    """Create the workspace in SQLite directly: a live server would probe Jira."""
    init_db(str(db_path))
    try:
        with db.connection_context():
            workspace = Workspace.create(
                name="Quantum Books",
                jira_base_url="https://example.atlassian.net",
                jira_email="ada@example.com",
                jira_api_token="jira-token",
                timezone="Europe/Kyiv",
            )

            return workspace.id
    finally:
        close_db()


@pytest.fixture
def live_server(tmp_path):
    db_path = tmp_path / "tsyncer.db"
    workspace_id = _seed_workspace(db_path)
    port = _free_port()
    env = {
        **os.environ,
        "PYTHONPATH": os.path.join(ROOT, "t_syncer"),
        "TSYNCER_BASIC_USER": AUTH[0],
        "TSYNCER_BASIC_PASSWORD": AUTH[1],
        "TSYNCER_SQLITE_DB_PATH": str(db_path),
    }
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "api.app:create_app_from_settings",
         "--factory", "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(100):
            if process.poll() is not None:
                pytest.fail(f"server died: {process.stderr.read().decode()[-2000:]}")
            try:
                if httpx.get(f"{base}/health", timeout=0.5).status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.1)
        else:
            pytest.fail("server did not become healthy")

        yield base, workspace_id
    finally:
        process.terminate()
        process.wait(timeout=10)


def test_parallel_reads_keep_the_session_consistent(live_server):
    live_server, workspace_id = live_server
    paths = [
        "/api/workspace",
        f"/api/workspace/{workspace_id}/days/2026-08-31",
        f"/api/workspace/{workspace_id}/days?from=2026-08-01&to=2026-08-31",
        f"/api/workspace/{workspace_id}/reports?period=month&date=2026-08-31",
    ] * 15

    def get(path):
        return httpx.get(f"{live_server}{path}", auth=AUTH, timeout=15).status_code

    with ThreadPoolExecutor(max_workers=12) as pool:
        codes = list(pool.map(get, paths))

    assert set(codes) == {200}, f"{codes.count(500)} of {len(codes)} requests returned 500"


def test_parallel_writes_are_all_committed(live_server):
    live_server, workspace_id = live_server
    dates = [f"2026-09-{day:02d}" for day in range(1, 21)]

    def add(date):
        return httpx.post(
            f"{live_server}/api/workspace/{workspace_id}/days/{date}/worklogs",
            auth=AUTH,
            json={"issue_key": "QBO-120", "start": "09:00", "end": "10:00"},
            timeout=15,
        ).status_code

    with ThreadPoolExecutor(max_workers=10) as pool:
        codes = list(pool.map(add, dates))

    assert set(codes) == {201}, f"{codes.count(500)} of {len(codes)} writes returned 500"
    days = httpx.get(
        f"{live_server}/api/workspace/{workspace_id}/days?from=2026-09-01&to=2026-09-30",
        auth=AUTH,
        timeout=15,
    ).json()["days"]

    assert len(days) == len(dates), "a write was accepted but never committed"


def test_every_api_route_carries_its_own_db_session():
    """A new route that forgets @db_request would bring the thread bug back."""
    from api.app import create_app

    app = create_app(sqlite_db_path=":memory:", basic_user="u", basic_password="p")
    unwrapped = [
        route.path
        for route in app.routes
        if getattr(route, "path", "").startswith("/api")
        and not hasattr(route.endpoint, "__wrapped__")
    ]

    assert unwrapped == [], f"routes without @db_request: {unwrapped}"
