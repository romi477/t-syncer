from tests.conftest import auth_get, create_workspace
from tests.test_worklogs import _add_line


def test_month_report_aggregates_local_lines(client):
    ws = create_workspace(client)
    _add_line(client, ws["id"], date="2026-08-03", start="09:00", end="11:00")
    _add_line(client, ws["id"], date="2026-08-27", start="09:00", end="10:20", issue_key="QBO-1")
    _add_line(client, ws["id"], date="2026-08-27", start="10:20", end="11:20", issue_key="QBO-1")
    body = auth_get(
        client,
        f"/api/workspace/{ws['id']}/reports",
        params={"period": "month", "date": "2026-08-27"},
    ).json()

    assert body["period"] == "month"
    assert body["from"] == "2026-08-01"
    assert body["to"] == "2026-08-31"
    assert body["total_minutes"] == 260
    assert body["task_count"] == 2
    assert body["days_with_work"] == 2
    assert [row["issue_key"] for row in body["tasks"]] == ["QBO-1", "QBO-120"]
    qbo1 = body["tasks"][0]
    assert qbo1["total_minutes"] == 140
    assert qbo1["days"] == 1
    assert qbo1["first_date"] == "2026-08-27"
    assert qbo1["last_date"] == "2026-08-27"


def test_week_report_is_monday_sunday(client):
    ws = create_workspace(client)
    _add_line(client, ws["id"], date="2026-08-23", start="09:00", end="10:00")  # Sunday prior
    _add_line(client, ws["id"], date="2026-08-24", start="09:00", end="10:00")
    body = auth_get(
        client,
        f"/api/workspace/{ws['id']}/reports",
        params={"period": "week", "date": "2026-08-27"},
    ).json()

    assert body["from"] == "2026-08-24"
    assert body["to"] == "2026-08-30"
    assert body["total_minutes"] == 60
    assert body["task_count"] == 1


def test_lines_without_issue_key_are_not_counted_as_tasks(client):
    ws = create_workspace(client)
    _add_line(client, ws["id"], date="2026-08-27", start="09:00", end="10:00")
    _add_line(client, ws["id"], date="2026-08-27", start="10:00", end="11:00", issue_key="")
    body = auth_get(
        client,
        f"/api/workspace/{ws['id']}/reports",
        params={"period": "month", "date": "2026-08-27"},
    ).json()

    assert body["total_minutes"] == 120
    assert body["task_count"] == 1
