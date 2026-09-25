from datetime import date, datetime, time
from zoneinfo import ZoneInfo

_MIDNIGHT = 24 * 60


def _as_minutes(value: time) -> int:

    return value.hour * 60 + value.minute


def _end_minutes(start: time, end: time) -> int:
    """Minutes from midnight for an end time, where 00:00 closes the day.

    A line that runs 22:00-00:00 ends at the midnight *after* its start, so the
    end is 24:00 rather than 0. Only an end reads this way, and only when the
    start is not midnight itself: 00:00-00:00 stays an empty range, not a day.
    """
    minutes = _as_minutes(end)
    if minutes == 0 and _as_minutes(start) > 0:

        return _MIDNIGHT

    return minutes


def duration_minutes(
    start: time | None,
    end: time | None,
    *,
    strict: bool = False,
) -> int:
    if start is None or end is None:

        return 0

    minutes = _end_minutes(start, end) - _as_minutes(start)
    if minutes <= 0:
        if strict:
            raise ValueError("end must be after start")

        return 0

    return minutes


def format_duration(minutes: int) -> str:
    hours, remainder = divmod(minutes, 60)
    if hours and remainder:

        return f"{hours}h {remainder}m"
    if hours:

        return f"{hours}h"

    return f"{remainder}m"


def format_jira_started(work_date: date, start: time, timezone: str) -> str:
    started = datetime.combine(work_date, start, tzinfo=ZoneInfo(timezone))

    return started.strftime("%Y-%m-%dT%H:%M:%S.000%z")


def add_time(
    start: time | None,
    end: time | None,
    delta_minutes: int,
    *,
    fallback_start: time | None = None,
) -> tuple[time | None, time | None]:
    if start is None:
        start = fallback_start or time(9, 0)
    if end is None:
        if delta_minutes <= 0:

            return start, end
        end = start

    new_end = _end_minutes(start, end) + delta_minutes
    # An end earlier than the start is still a time the user can step. Only the
    # edges of the day stop the button: before 00:00 and past midnight.
    if new_end > _MIDNIGHT or new_end < 0:

        return start, end
    if new_end == _MIDNIGHT:

        return start, time(0, 0)

    hours, minutes = divmod(new_end, 60)

    return start, time(hours, minutes)
