from peewee import (
    AutoField,
    BooleanField,
    DateField,
    ForeignKeyField,
    IntegerField,
    Model,
    TextField,
    TimeField,
)

from api.db import db


class BaseModel(Model):
    class Meta:
        database = db


class Workspace(BaseModel):
    id = AutoField()
    name = TextField()
    jira_base_url = TextField()
    jira_email = TextField()
    jira_api_token = TextField()
    timezone = TextField()
    day_start = TextField(default="09:00")
    day_hours = IntegerField(default=8)
    report_hours = IntegerField(default=10)
    jira_display_name = TextField(default="")

    class Meta:
        table_name = "workspaces"


class DayMark(BaseModel):
    id = AutoField()
    workspace = ForeignKeyField(
        Workspace,
        backref="day_marks",
        column_name="workspace",
        on_delete="CASCADE",
    )
    work_date = DateField()
    holiday = BooleanField(default=False)

    class Meta:
        table_name = "day_marks"
        indexes = ((("workspace", "work_date"), True),)


class Worklog(BaseModel):
    id = AutoField()
    # column_name keeps the schema the Pony version wrote, so an existing
    # tsyncer.db opens unchanged.
    workspace = ForeignKeyField(
        Workspace,
        backref="worklogs",
        column_name="workspace",
        on_delete="CASCADE",
    )
    work_date = DateField()
    start_time = TimeField(null=True)
    end_time = TimeField(null=True)
    duration_minutes = IntegerField(default=0)
    issue_key = TextField(default="")
    tag = TextField(default="")
    message = TextField(default="")
    status = TextField(default="draft")
    jira_worklog_id = TextField(default="")
    last_error = TextField(default="")

    class Meta:
        table_name = "worklogs"
