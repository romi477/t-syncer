from datetime import date

from pydantic import BaseModel, Field


class WorkspaceIn(BaseModel):
    name: str
    jira_base_url: str
    jira_email: str
    jira_api_token: str
    timezone: str = "Europe/Kyiv"


class WorkspaceUpdate(BaseModel):
    name: str | None = None
    jira_base_url: str | None = None
    jira_email: str | None = None
    jira_api_token: str | None = None
    timezone: str | None = None


class LineIn(BaseModel):
    issue_key: str = Field(default="", examples=["QBO-120"])
    tag: str | None = Field(default=None, examples=["dev"])
    message: str = Field(default="", examples=["Implement tags synchronization"])
    start: str | None = Field(default=None, examples=["09:00"])
    end: str | None = Field(default=None, examples=["10:00"])


class LinePatch(BaseModel):
    issue_key: str | None = None
    tag: str | None = None
    message: str | None = None
    start: str | None = None
    end: str | None = None


class DayLinesIn(BaseModel):
    date: date
    lines: list[LineIn]
