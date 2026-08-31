import httpx
import pytest

from api.jira import JiraClient, JiraError


@pytest.fixture(autouse=True)
def no_backoff(monkeypatch):
    monkeypatch.setattr("api.jira.time.sleep", lambda _seconds: None)


def _client(handler) -> JiraClient:
    transport = httpx.MockTransport(handler)
    inner = httpx.Client(transport=transport, base_url="https://example.atlassian.net")

    return JiraClient("https://example.atlassian.net", "ada@example.com", "token", client=inner)


def test_get_issue_retries_after_transport_error():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.method)
        if len(calls) < 3:
            raise httpx.ConnectError("boom", request=request)

        return httpx.Response(200, json={"key": "QBO-120"})

    assert _client(handler).get_issue("QBO-120") == {"key": "QBO-120"}
    assert calls == ["GET", "GET", "GET"]


def test_create_worklog_is_not_retried_after_transport_error():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.method)
        raise httpx.ConnectError("boom", request=request)

    with pytest.raises(JiraError):
        _client(handler).create_worklog(
            "QBO-120",
            started="2026-08-29T09:00:00.000+0300",
            time_spent_seconds=3600,
            comment={},
        )

    assert calls == ["POST"]


def test_create_worklog_retries_on_rate_limit():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.method)
        if len(calls) < 2:
            return httpx.Response(429)

        return httpx.Response(201, json={"id": "1001"})

    result = _client(handler).create_worklog(
        "QBO-120",
        started="2026-08-29T09:00:00.000+0300",
        time_spent_seconds=3600,
        comment={},
    )

    assert result == {"id": "1001"}
    assert calls == ["POST", "POST"]


def test_get_issue_server_error_message_excludes_response_body():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(502, text="<html><body>Bad gateway</body></html>")

    with pytest.raises(JiraError) as caught:
        _client(handler).get_issue("QBO-120")

    assert "<html>" not in caught.value.message
    assert caught.value.status_code == 502
