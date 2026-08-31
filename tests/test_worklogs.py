from tests.conftest import auth_delete, auth_get, auth_patch, auth_post, create_workspace


def _add_line(client, workspace_id, date="2026-08-29", **overrides):
    payload = {
        "issue_key": "QBO-120",
        "tag": "dev",
        "message": "Implement tags",
        "start": "09:00",
        "end": "11:20",
        **overrides,
    }
    response = auth_post(
        client,
        f"/api/workspace/{workspace_id}/days/{date}/worklogs",
        json=payload,
    )
    assert response.status_code == 201, response.text

    return response.json()


def test_add_line_computes_duration_and_resolves_tag(client):
    ws = create_workspace(client)
    body = _add_line(client, ws["id"])

    assert body["issue_key"] == "QBO-120"
    assert body["tag"] == "DEV"
    assert body["duration_minutes"] == 140
    assert body["status"] == "draft"
    assert body["total_minutes"] == 140


def test_unknown_tag_is_saved_as_null(client):
    ws = create_workspace(client)
    body = _add_line(client, ws["id"], tag="NOPE")

    assert body["tag"] is None
    assert body["status"] == "draft"


def test_incomplete_end_is_allowed_with_zero_duration(client):
    ws = create_workspace(client)
    body = _add_line(client, ws["id"], end=None)

    assert body["end"] is None
    assert body["duration_minutes"] == 0


def test_day_card_returns_lines_and_total(client):
    ws = create_workspace(client)
    _add_line(client, ws["id"], start="09:00", end="10:00")
    _add_line(client, ws["id"], start="10:00", end="10:30", tag="")
    card = auth_get(client, f"/api/workspace/{ws['id']}/days/2026-08-29").json()

    assert card["work_date"] == "2026-08-29"
    assert card["total_minutes"] == 90
    assert len(card["lines"]) == 2


def test_get_worklog_returns_metadata_with_workspace(client):
    ws = create_workspace(client)
    line = _add_line(client, ws["id"])
    response = auth_get(client, f"/api/workspace/{ws['id']}/worklogs/{line['id']}")
    body = response.json()

    assert response.status_code == 200
    assert body["id"] == line["id"]
    assert body["workspace_id"] == ws["id"]
    assert body["workspace"]["id"] == ws["id"]
    assert body["workspace"]["jira_api_token"] == "****"
    assert body["tag"] == "DEV"
    assert body["jira_worklog_id"] is None
    assert "start_time" in body
    assert body["start_time"] == "09:00"


def test_patch_draft_line(client):
    ws = create_workspace(client)
    line = _add_line(client, ws["id"])
    response = auth_patch(
        client,
        f"/api/workspace/{ws['id']}/worklogs/{line['id']}",
        json={"end": "10:00", "message": "Shorter"},
    )

    assert response.status_code == 200
    assert response.json()["duration_minutes"] == 60
    assert response.json()["message"] == "Shorter"


def test_day_range_summaries_for_calendar(client):
    ws = create_workspace(client)
    _add_line(client, ws["id"], date="2026-08-06", start="09:00", end="10:00")
    body = auth_get(
        client,
        f"/api/workspace/{ws['id']}/days",
        params={"from": "2026-08-01", "to": "2026-08-31"},
    ).json()

    assert body["days"][0]["date"] == "2026-08-06"
    assert body["days"][0]["total_minutes"] == 60
    assert body["days"][0]["pending_minutes"] == 60
    assert body["days"][0]["status"] == "draft"


def test_delete_draft_line(client):
    ws = create_workspace(client)
    line = _add_line(client, ws["id"])
    response = auth_delete(client, f"/api/workspace/{ws['id']}/worklogs/{line['id']}")

    assert response.status_code == 204
    card = auth_get(client, f"/api/workspace/{ws['id']}/days/2026-08-29").json()
    assert card["lines"] == []
    assert card["total_minutes"] == 0


def test_bulk_create_lines_for_several_days(client):
    ws = create_workspace(client)
    response = auth_post(
        client,
        f"/api/workspace/{ws['id']}/worklogs",
        json=[
            {
                "date": "2026-08-19",
                "lines": [
                    {
                        "issue_key": "RDI-1",
                        "tag": "int",
                        "message": "Team meeting",
                        "start": "09:30",
                        "end": "09:45",
                    }
                ],
            },
            {
                "date": "2026-08-20",
                "lines": [
                    {
                        "issue_key": "QBO-120",
                        "tag": "dev",
                        "message": "Implement tags",
                        "start": "09:00",
                        "end": "10:00",
                    },
                    {
                        "issue_key": "QBO-120",
                        "tag": "dev",
                        "message": "More work",
                        "start": "10:00",
                        "end": "11:00",
                    },
                ],
            },
        ],
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert [day["date"] for day in body] == ["2026-08-19", "2026-08-20"]
    assert body[0]["total_minutes"] == 15
    assert body[0]["lines"][0]["issue_key"] == "RDI-1"
    assert body[0]["lines"][0]["tag"] == "INT"
    assert body[0]["lines"][0]["status"] == "draft"
    assert body[1]["total_minutes"] == 120
    assert len(body[1]["lines"]) == 2

    card = auth_get(client, f"/api/workspace/{ws['id']}/days/2026-08-19").json()
    assert card["total_minutes"] == 15
    assert len(card["lines"]) == 1


def test_bulk_create_lines_unknown_workspace_is_404(client):
    response = auth_post(
        client,
        "/api/workspace/999/worklogs",
        json=[{"date": "2026-08-19", "lines": []}],
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Workspace not found"


def test_non_numeric_clock_is_saved_as_empty_not_a_crash(client):
    ws = create_workspace(client)
    response = auth_post(
        client,
        f"/api/workspace/{ws['id']}/days/2026-08-29/worklogs",
        json={"issue_key": "QBO-120", "start": "aa:bb", "end": "11:00"},
    )

    assert response.status_code == 201, response.text
    assert response.json()["start"] == "00:00"


def test_a_line_can_end_at_midnight(client):
    ws = create_workspace(client)
    body = _add_line(client, ws["id"], start="22:00", end="00:00")

    assert body["end"] == "00:00"
    assert body["duration_minutes"] == 120


def test_the_tag_is_stored_as_its_code(client):
    from api.db import db
    from api.models import Worklog

    ws = create_workspace(client)
    line = _add_line(client, ws["id"], tag="dev")
    with db.connection_context():
        stored = Worklog.get_by_id(line["id"]).tag

    assert stored == "DEV", "the row itself must say what the tag is"
