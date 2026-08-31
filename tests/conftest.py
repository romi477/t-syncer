from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.fakes import FakeJira
from api.app import create_app

AUTH = ("tester", "secret")

WORKSPACE = {
    "name": "Quantum Books",
    "jira_base_url": "https://example.atlassian.net/",
    "jira_email": "ada@example.com",
    "jira_api_token": "jira-token",
    "timezone": "Europe/Kyiv",
}


@pytest.fixture
def fake_jira() -> FakeJira:
    return FakeJira()


@pytest.fixture
def client(tmp_path, fake_jira):
    app = create_app(
        sqlite_db_path=str(tmp_path / "tsyncer.db"),
        basic_user=AUTH[0],
        basic_password=AUTH[1],
        jira_factory=lambda base_url, email, token: fake_jira,
    )
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def client_factory(tmp_path):
    """Build a client around a specific Jira double, for per-test failure modes."""
    def build(jira):
        app = create_app(
            sqlite_db_path=str(tmp_path / "tsyncer.db"),
            basic_user=AUTH[0],
            basic_password=AUTH[1],
            jira_factory=lambda base_url, email, token: jira,
        )

        return TestClient(app)

    return build


def auth_get(client, path, **kwargs):
    kwargs.setdefault("auth", AUTH)

    return client.get(path, **kwargs)


def auth_post(client, path, **kwargs):
    kwargs.setdefault("auth", AUTH)

    return client.post(path, **kwargs)


def auth_patch(client, path, **kwargs):
    kwargs.setdefault("auth", AUTH)

    return client.patch(path, **kwargs)


def auth_delete(client, path, **kwargs):
    kwargs.setdefault("auth", AUTH)

    return client.delete(path, **kwargs)


def create_workspace(client, **overrides) -> dict:
    payload = {**WORKSPACE, **overrides}
    response = auth_post(client, "/api/workspace", json=payload)
    assert response.status_code == 201, response.text

    return response.json()
