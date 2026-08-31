from tests.conftest import AUTH, auth_get


def test_health_is_public(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_api_without_credentials_is_401(client):
    response = client.get("/api/workspace")

    assert response.status_code == 401
    assert response.headers.get("www-authenticate", "").lower().startswith("basic")


def test_wrong_password_is_401(client):
    response = client.get("/api/workspace", auth=("tester", "nope"))

    assert response.status_code == 401


def test_root_redirects_to_web(client):
    response = client.get("/", auth=AUTH, follow_redirects=False)

    assert response.status_code in (302, 307, 303)
    assert response.headers["location"].rstrip("/").endswith("/web")


def test_web_requires_auth(client):
    response = client.get("/web")

    assert response.status_code == 401


def test_web_serves_app_when_authed(client):
    response = auth_get(client, "/web")

    assert response.status_code == 200
    assert "T-Syncer" in response.text or "T‑Syncer" in response.text


def test_swagger_docs_require_auth(client):
    for path in ("/docs", "/redoc", "/openapi.json"):
        response = client.get(path)

        assert response.status_code == 401, path
        assert response.headers.get("www-authenticate", "").lower().startswith("basic"), path


def test_swagger_docs_are_available_when_authed(client):
    docs = auth_get(client, "/docs")
    spec = auth_get(client, "/openapi.json")

    assert docs.status_code == 200
    assert "swagger" in docs.text.lower()
    assert spec.status_code == 200
    body = spec.json()
    paths = body["paths"]
    assert "/api/workspace/{workspace_id}/worklogs" in paths
    assert "/api/workspace/{workspace_id}/days/{work_date}/push" in paths
    assert "/api/workspace/{workspace_id}/worklogs/{worklog_id}/push" in paths
    assert body["components"]["securitySchemes"]["HTTPBasic"]["scheme"] == "basic"
