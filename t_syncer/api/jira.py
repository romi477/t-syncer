from __future__ import annotations

import time
from urllib.parse import quote

import httpx


class JiraError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


class JiraAuthError(JiraError):
    pass


class JiraIssueMissing(JiraError):
    def __init__(self, issue_key: str, status_code: int = 404):
        super().__init__(status_code, f"Issue {issue_key} does not exist")
        self.issue_key = issue_key


_RETRY_ON_TRANSPORT_ERROR = frozenset({"GET", "HEAD", "DELETE", "PUT"})


class JiraClient:
    def __init__(self, base_url: str, email: str, token: str, *, client: httpx.Client | None = None):
        self.base_url = base_url.rstrip("/")
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=self.base_url,
            auth=(email, token),
            timeout=30.0,
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        retry_transport = method.upper() in _RETRY_ON_TRANSPORT_ERROR
        last_error: Exception | None = None
        for attempt in range(4):
            try:
                response = self._client.request(method, path, **kwargs)
            except httpx.TransportError as exc:
                # A non-idempotent request may already have been applied by Jira,
                # so retrying it could create a duplicate worklog.
                if not retry_transport:
                    raise JiraError(0, str(exc)) from exc
                last_error = exc
                time.sleep(0.5 * (2 ** attempt))
                continue
            if response.status_code == 429 and attempt < 3:
                time.sleep(0.5 * (2 ** attempt))
                continue

            return response
        raise JiraError(0, str(last_error) if last_error else "Jira request failed")

    def myself(self) -> dict:
        response = self._request("GET", "/rest/api/3/myself")
        if response.status_code != 200:
            raise JiraAuthError(response.status_code, "Jira credentials were rejected")

        return response.json()

    def get_issue(self, issue_key: str) -> dict:
        encoded = quote(issue_key, safe="")
        response = self._request("GET", f"/rest/api/3/issue/{encoded}")
        if response.status_code in (400, 404):
            raise JiraIssueMissing(issue_key, response.status_code)
        if response.status_code != 200:
            raise JiraError(response.status_code, "Jira could not be asked about the issue")

        return response.json()

    def create_worklog(
        self,
        issue_key: str,
        *,
        started: str,
        time_spent_seconds: int,
        comment: dict,
    ) -> dict:
        encoded = quote(issue_key, safe="")
        response = self._request(
            "POST",
            f"/rest/api/3/issue/{encoded}/worklog",
            params={"adjustEstimate": "leave", "notifyUsers": "false"},
            json={
                "started": started,
                "timeSpentSeconds": time_spent_seconds,
                "comment": comment,
            },
        )
        if response.status_code != 201:
            raise JiraError(response.status_code, "Jira rejected the worklog")
        try:
            return response.json()
        except ValueError:
            # Jira has recorded the worklog; an unreadable body must not make the
            # caller retry it. The id is lost, the write is not.
            return {}

    def delete_worklog(self, issue_key: str, worklog_id: str) -> None:
        encoded = quote(issue_key, safe="")
        response = self._request(
            "DELETE",
            f"/rest/api/3/issue/{encoded}/worklog/{quote(worklog_id, safe='')}",
        )
        if response.status_code in (204, 404):
            return
        raise JiraError(response.status_code, "Jira delete failed")


def default_jira_factory(base_url: str, email: str, token: str) -> JiraClient:
    return JiraClient(base_url, email, token)
