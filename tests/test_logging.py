import logging

from tests.conftest import WORKSPACE, auth_post, create_workspace
from tests.test_worklogs import _add_line

LOGGER = "tsyncer"


def test_a_pushed_worklog_is_logged_with_its_jira_id(client, caplog):
    ws = create_workspace(client)
    line = _add_line(client, ws["id"])
    with caplog.at_level(logging.INFO, logger=LOGGER):
        auth_post(client, f"/api/workspace/{ws['id']}/worklogs/{line['id']}/push")

    pushed = [r for r in caplog.records if r.name == LOGGER and "pushed" in r.message]

    assert pushed, caplog.text
    assert "QBO-120" in pushed[0].message
    assert "1001" in pushed[0].message


def test_a_refused_worklog_is_logged_with_the_reason(client, fake_jira, caplog):
    ws = create_workspace(client)
    fake_jira.issues["QBO-999"] = 404
    line = _add_line(client, ws["id"], issue_key="QBO-999")
    with caplog.at_level(logging.INFO, logger=LOGGER):
        auth_post(client, f"/api/workspace/{ws['id']}/worklogs/{line['id']}/push")

    failed = [r for r in caplog.records if r.name == LOGGER and r.levelno >= logging.WARNING]

    assert failed, caplog.text
    assert "QBO-999" in failed[0].message
    assert "does not exist" in failed[0].message


def test_deleting_in_jira_is_logged(client, caplog):
    ws = create_workspace(client)
    line = _add_line(client, ws["id"])
    auth_post(client, f"/api/workspace/{ws['id']}/worklogs/{line['id']}/push")
    with caplog.at_level(logging.INFO, logger=LOGGER):
        auth_post(client, f"/api/workspace/{ws['id']}/worklogs/{line['id']}/delete-in-jira")

    deleted = [r for r in caplog.records if r.name == LOGGER and "deleted" in r.message]

    assert deleted, caplog.text
    assert "1001" in deleted[0].message


def test_an_unreachable_jira_is_logged_on_workspace_save(client, fake_jira, caplog):
    fake_jira.unreachable = True
    with caplog.at_level(logging.INFO, logger=LOGGER):
        auth_post(client, "/api/workspace", json=WORKSPACE)

    probed = [r for r in caplog.records if r.name == LOGGER and r.levelno >= logging.WARNING]

    assert probed, caplog.text
    assert "example.atlassian.net" in probed[0].message


def test_logs_never_carry_the_jira_token(client, caplog):
    token = "super-secret-jira-token"
    with caplog.at_level(logging.DEBUG):
        ws = create_workspace(client, jira_api_token=token)
        line = _add_line(client, ws["id"])
        auth_post(client, f"/api/workspace/{ws['id']}/worklogs/{line['id']}/push")

    assert token not in caplog.text


def test_configuring_logging_twice_does_not_duplicate_handlers():
    from api.logging import configure_logging

    configure_logging("INFO")
    first = len(logging.getLogger(LOGGER).handlers)
    configure_logging("INFO")

    assert len(logging.getLogger(LOGGER).handlers) == first
