import pytest

from tests.conftest import auth_get, auth_post, create_workspace
from tests.test_worklogs import _add_line


class BodylessJira:
    """Jira accepts the POST but answers with a body the client cannot read."""

    def __init__(self):
        self.posts = []

    def close(self):
        return None

    def myself(self):
        return {"displayName": "Ada Lovelace"}

    def get_issue(self, issue_key):
        return {"key": issue_key}

    def create_worklog(self, issue_key, **kwargs):
        self.posts.append(issue_key)

        return {}


class ExplodingJira(BodylessJira):
    """First worklog is written, the second call fails in an unexpected way."""

    def create_worklog(self, issue_key, **kwargs):
        self.posts.append(issue_key)
        if len(self.posts) == 1:
            return {"id": "1001"}

        raise RuntimeError("boom")


@pytest.fixture
def bodyless_client(client_factory):
    jira = BodylessJira()

    with client_factory(jira) as test_client:
        yield test_client, jira


@pytest.fixture
def exploding_client(client_factory):
    jira = ExplodingJira()

    with client_factory(jira) as test_client:
        yield test_client, jira


def test_accepted_worklog_is_synced_even_without_a_readable_id(bodyless_client):
    client, jira = bodyless_client
    ws = create_workspace(client)
    line = _add_line(client, ws["id"])
    response = auth_post(client, f"/api/workspace/{ws['id']}/worklogs/{line['id']}/push")

    assert response.status_code == 200
    assert response.json()["status"] == "synced"
    assert len(jira.posts) == 1


def test_a_worklog_jira_accepted_is_never_pushed_twice(bodyless_client):
    client, jira = bodyless_client
    ws = create_workspace(client)
    line = _add_line(client, ws["id"])
    auth_post(client, f"/api/workspace/{ws['id']}/worklogs/{line['id']}/push")
    auth_post(client, f"/api/workspace/{ws['id']}/worklogs/{line['id']}/push")

    assert len(jira.posts) == 1


def test_bulk_push_keeps_lines_that_jira_already_accepted(exploding_client):
    client, jira = exploding_client
    ws = create_workspace(client)
    _add_line(client, ws["id"], date="2026-08-31", start="09:00", end="10:00")
    _add_line(client, ws["id"], date="2026-08-31", start="10:00", end="11:00")
    response = auth_post(client, f"/api/workspace/{ws['id']}/days/2026-08-31/push")

    assert response.status_code == 200
    assert len(jira.posts) == 2
    card = auth_get(client, f"/api/workspace/{ws['id']}/days/2026-08-31").json()
    statuses = [row["status"] for row in card["lines"]]

    assert statuses[0] == "synced", "the line Jira accepted must not fall back to draft"
    assert statuses[1] == "error"


def test_a_failed_line_does_not_abort_the_rest_of_the_card(exploding_client):
    client, jira = exploding_client
    ws = create_workspace(client)
    _add_line(client, ws["id"], date="2026-08-31", start="09:00", end="10:00")
    _add_line(client, ws["id"], date="2026-08-31", start="10:00", end="11:00")
    _add_line(client, ws["id"], date="2026-08-31", start="11:00", end="12:00")
    results = auth_post(client, f"/api/workspace/{ws['id']}/days/2026-08-31/push").json()["results"]

    assert [row["status"] for row in results] == ["synced", "error", "error"]
    assert len(jira.posts) == 3
