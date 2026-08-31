from __future__ import annotations

from dataclasses import dataclass, field

from api.jira import JiraAuthError, JiraError, JiraIssueMissing


@dataclass
class FakeJira:
    display_name: str = "Ada Lovelace"
    myself_ok: bool = True
    unreachable: bool = False
    issues: dict[str, int] = field(default_factory=lambda: {"QBO-120": 200})
    post_status: int = 201
    delete_status: int = 204
    next_id: int = 1001
    posts: list[dict] = field(default_factory=list)
    deletes: list[tuple[str, str]] = field(default_factory=list)
    myself_calls: int = 0

    def close(self) -> None:
        return None

    def myself(self) -> dict:
        self.myself_calls += 1
        if self.unreachable:
            raise JiraError(0, "Jira is unreachable")
        if not self.myself_ok:
            raise JiraAuthError(401, "Jira credentials were rejected")

        return {"displayName": self.display_name}

    def get_issue(self, issue_key: str) -> dict:
        status = self.issues.get(issue_key, 404)
        if status in (400, 404):
            raise JiraIssueMissing(issue_key, status)

        return {"key": issue_key}

    def create_worklog(
        self,
        issue_key: str,
        *,
        started: str,
        time_spent_seconds: int,
        comment: dict,
    ) -> dict:
        if self.post_status != 201:
            raise JiraError(self.post_status, "Jira rejected the worklog")
        worklog_id = str(self.next_id)
        self.next_id += 1
        self.posts.append(
            {
                "issue_key": issue_key,
                "started": started,
                "timeSpentSeconds": time_spent_seconds,
                "comment": comment,
                "id": worklog_id,
            }
        )

        return {"id": worklog_id}

    def delete_worklog(self, issue_key: str, worklog_id: str) -> None:
        self.deletes.append((issue_key, worklog_id))
        if self.delete_status in (204, 404):
            return
        raise JiraError(self.delete_status, "Jira delete failed")
