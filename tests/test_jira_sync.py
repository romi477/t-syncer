from tests.conftest import auth_delete, auth_patch, auth_post, create_workspace
from tests.test_worklogs import _add_line


def test_push_line_sends_started_adf_and_marks_synced(client, fake_jira):
    ws = create_workspace(client)
    line = _add_line(client, ws["id"])
    response = auth_post(
        client,
        f"/api/workspace/{ws['id']}/worklogs/{line['id']}/push",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "synced"
    assert body["jira_worklog_id"] == "1001"
    assert body["last_error"] is None
    post = fake_jira.posts[0]
    assert post["started"] == "2026-08-29T09:00:00.000+0300"
    assert post["timeSpentSeconds"] == 140 * 60
    assert post["comment"]["type"] == "doc"
    text = post["comment"]["content"][0]["content"][0]["text"]
    assert text == "[QBO-120] [DEV] Implement tags"


def test_push_missing_issue_marks_error_not_synced(client, fake_jira):
    fake_jira.issues["QBO-999"] = 404
    ws = create_workspace(client)
    line = _add_line(client, ws["id"], issue_key="QBO-999")
    response = auth_post(
        client,
        f"/api/workspace/{ws['id']}/worklogs/{line['id']}/push",
    )

    assert response.status_code == 200
    assert response.json()["status"] == "error"
    assert "does not exist" in response.json()["last_error"]
    assert fake_jira.posts == []


def test_get_issue_400_is_missing_issue(client, fake_jira):
    fake_jira.issues["BAD"] = 400
    ws = create_workspace(client)
    line = _add_line(client, ws["id"], issue_key="BAD")
    response = auth_post(
        client,
        f"/api/workspace/{ws['id']}/worklogs/{line['id']}/push",
    )

    assert response.json()["status"] == "error"
    assert fake_jira.posts == []


def test_post_400_is_not_missing_issue(client, fake_jira):
    fake_jira.post_status = 400
    ws = create_workspace(client)
    line = _add_line(client, ws["id"])
    response = auth_post(
        client,
        f"/api/workspace/{ws['id']}/worklogs/{line['id']}/push",
    )

    assert response.json()["status"] == "error"
    assert "does not exist" not in (response.json()["last_error"] or "").lower()


def test_incomplete_line_fails_on_push(client, fake_jira):
    ws = create_workspace(client)
    line = _add_line(client, ws["id"], end=None)
    response = auth_post(
        client,
        f"/api/workspace/{ws['id']}/worklogs/{line['id']}/push",
    )

    assert response.json()["status"] == "error"
    assert fake_jira.posts == []


def test_synced_line_cannot_be_edited_or_deleted_locally(client, fake_jira):
    ws = create_workspace(client)
    line = _add_line(client, ws["id"])
    auth_post(client, f"/api/workspace/{ws['id']}/worklogs/{line['id']}/push")
    patched = auth_patch(
        client,
        f"/api/workspace/{ws['id']}/worklogs/{line['id']}",
        json={"message": "nope"},
    )
    deleted = auth_delete(client, f"/api/workspace/{ws['id']}/worklogs/{line['id']}")

    assert patched.status_code == 409
    assert deleted.status_code == 409


def test_bulk_push_skips_synced_and_continues_after_error(client, fake_jira):
    ws = create_workspace(client)
    ok = _add_line(client, ws["id"], start="09:00", end="10:00")
    auth_post(client, f"/api/workspace/{ws['id']}/worklogs/{ok['id']}/push")
    fake_jira.issues["QBO-999"] = 404
    _add_line(client, ws["id"], issue_key="QBO-999", start="10:00", end="11:00")
    _add_line(client, ws["id"], start="11:00", end="12:00")
    response = auth_post(client, f"/api/workspace/{ws['id']}/days/2026-08-29/push")

    assert response.status_code == 200
    results = response.json()["results"]
    statuses = {row["id"]: row["status"] for row in results}
    assert statuses[ok["id"]] == "skipped"
    assert "error" in statuses.values()
    assert "synced" in statuses.values()
    assert len(fake_jira.posts) == 2


def test_delete_in_jira_404_resets_to_draft(client, fake_jira):
    ws = create_workspace(client)
    line = _add_line(client, ws["id"])
    auth_post(client, f"/api/workspace/{ws['id']}/worklogs/{line['id']}/push")
    fake_jira.delete_status = 404
    response = auth_post(
        client,
        f"/api/workspace/{ws['id']}/worklogs/{line['id']}/delete-in-jira",
    )

    assert response.status_code == 200
    assert response.json()["status"] == "draft"
    assert response.json()["jira_worklog_id"] is None
    assert fake_jira.deletes == [("QBO-120", "1001")]


def test_reset_to_draft_does_not_call_jira(client, fake_jira):
    ws = create_workspace(client)
    line = _add_line(client, ws["id"])
    auth_post(client, f"/api/workspace/{ws['id']}/worklogs/{line['id']}/push")
    fake_jira.deletes.clear()
    response = auth_post(
        client,
        f"/api/workspace/{ws['id']}/worklogs/{line['id']}/reset-to-draft",
    )

    assert response.status_code == 200
    assert response.json()["status"] == "draft"
    assert fake_jira.deletes == []


def test_range_push_uses_from_to(client, fake_jira):
    ws = create_workspace(client)
    _add_line(client, ws["id"], date="2026-08-24", start="09:00", end="10:00")
    _add_line(client, ws["id"], date="2026-08-31", start="09:00", end="10:00")
    response = auth_post(
        client,
        f"/api/workspace/{ws['id']}/push",
        params={"from": "2026-08-24", "to": "2026-08-30"},
    )

    assert response.status_code == 200
    assert len(fake_jira.posts) == 1
    assert fake_jira.posts[0]["started"].startswith("2026-08-24")


def test_pushing_a_synced_line_again_returns_the_full_line(client, fake_jira):
    ws = create_workspace(client)
    line = _add_line(client, ws["id"])
    auth_post(client, f"/api/workspace/{ws['id']}/worklogs/{line['id']}/push")
    response = auth_post(client, f"/api/workspace/{ws['id']}/worklogs/{line['id']}/push")

    assert response.status_code == 200
    body = response.json()
    assert body["skipped"] is True
    assert body["status"] == "synced"
    assert body["issue_key"] == "QBO-120"
    assert body["jira_worklog_id"] == "1001"
    assert len(fake_jira.posts) == 1


def test_a_line_ending_at_midnight_is_pushed_as_same_day_hours(client, fake_jira):
    ws = create_workspace(client)
    line = _add_line(client, ws["id"], date="2026-08-31", start="22:00", end="00:00")
    response = auth_post(client, f"/api/workspace/{ws['id']}/worklogs/{line['id']}/push")

    assert response.status_code == 200
    assert response.json()["status"] == "synced"
    posted = fake_jira.posts[0]

    assert posted["timeSpentSeconds"] == 2 * 60 * 60
    assert posted["started"].startswith("2026-08-31T22:00:00.000")
