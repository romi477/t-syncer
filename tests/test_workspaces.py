from tests.conftest import AUTH, WORKSPACE, auth_delete, auth_get, auth_patch, auth_post, create_workspace


def test_create_workspace_probes_myself_and_strips_slash(client, fake_jira):
    body = create_workspace(client)

    assert fake_jira.myself_calls == 1
    assert body["name"] == "Quantum Books"
    assert body["jira_base_url"] == "https://example.atlassian.net"
    assert body["jira_email"] == "ada@example.com"
    assert body["timezone"] == "Europe/Kyiv"
    assert body["jira_display_name"] == "Ada Lovelace"
    assert "jira-token" not in str(body)
    assert body["jira_api_token"] == "****"


def test_create_workspace_rejects_bad_jira_login(client, fake_jira):
    fake_jira.myself_ok = False
    response = auth_post(client, "/api/workspace", json=WORKSPACE)

    assert response.status_code == 400
    assert auth_get(client, "/api/workspace").json() == []


def test_list_and_get_workspace(client):
    created = create_workspace(client)
    listed = auth_get(client, "/api/workspace").json()
    fetched = auth_get(client, f"/api/workspace/{created['id']}").json()

    assert len(listed) == 1
    assert fetched["id"] == created["id"]
    assert fetched["jira_api_token"] == "****"


def test_blank_token_on_update_keeps_stored_token(client, fake_jira):
    created = create_workspace(client)
    fake_jira.display_name = "Ada Updated"
    response = auth_patch(
        client,
        f"/api/workspace/{created['id']}",
        json={"name": "QBO", "jira_api_token": ""},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "QBO"
    assert response.json()["jira_display_name"] == "Ada Updated"
    assert fake_jira.myself_calls == 2


def test_create_workspace_reports_unreachable_jira_as_bad_gateway(client, fake_jira):
    fake_jira.unreachable = True
    response = auth_post(client, "/api/workspace", json=WORKSPACE)

    assert response.status_code == 502
    assert "unreachable" in response.json()["detail"].lower()
    assert auth_get(client, "/api/workspace").json() == []


def test_delete_workspace_removes_it_and_its_lines(client):
    keep = create_workspace(client, name="Keep")
    gone = create_workspace(client, name="Gone")

    response = auth_delete(client, f"/api/workspace/{gone['id']}")

    assert response.status_code == 204
    names = [item["name"] for item in auth_get(client, "/api/workspace").json()]
    assert names == ["Keep"]
    assert auth_get(client, f"/api/workspace/{gone['id']}").status_code == 404
    assert auth_get(client, f"/api/workspace/{keep['id']}").status_code == 200


def test_day_start_defaults_to_nine_and_requires_hh_mm(client):
    created = create_workspace(client)

    assert created["day_start"] == "09:00"

    updated = auth_patch(
        client,
        f"/api/workspace/{created['id']}",
        json={"day_start": "09:30"},
    )

    assert updated.status_code == 200
    assert updated.json()["day_start"] == "09:30"

    rejected = auth_patch(
        client,
        f"/api/workspace/{created['id']}",
        json={"day_start": "930"},
    )

    assert rejected.status_code == 400
    assert auth_get(client, f"/api/workspace/{created['id']}").json()["day_start"] == "09:30"


def test_workspace_saves_when_jira_omits_the_display_name(client, fake_jira):
    fake_jira.display_name = None
    response = auth_post(client, "/api/workspace", json=WORKSPACE)

    assert response.status_code == 201, response.text
    assert response.json()["jira_display_name"] == ""
