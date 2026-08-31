from datetime import date, time

import pytest

from api.duration import (
    add_time,
    duration_minutes,
    format_duration,
    format_jira_started,
)


def test_duration_from_range():
    assert duration_minutes(time(9, 0), time(11, 20)) == 140


def test_duration_none_when_incomplete():
    assert duration_minutes(time(9, 0), None) == 0
    assert duration_minutes(None, time(11, 0)) == 0


def test_duration_rejects_end_not_after_start():
    with pytest.raises(ValueError, match="end must be after start"):
        duration_minutes(time(11, 0), time(9, 0), strict=True)


def test_format_duration():
    assert format_duration(140) == "2h 20m"
    assert format_duration(120) == "2h"
    assert format_duration(45) == "45m"
    assert format_duration(0) == "0m"


def test_jira_started_uses_timezone_offset():
    started = format_jira_started(date(2026, 8, 29), time(9, 0), "Europe/Kyiv")

    assert started == "2026-08-29T09:00:00.000+0300"


def test_add_time_plus_from_empty_end():
    start, end = add_time(time(9, 0), None, 60)

    assert start == time(9, 0)
    assert end == time(10, 0)


def test_add_time_minus_no_op_if_would_not_stay_after_start():
    start, end = add_time(time(9, 0), time(9, 30), -60)

    assert start == time(9, 0)
    assert end == time(9, 30)


def test_add_time_plus_refuses_overnight():
    start, end = add_time(time(23, 30), time(23, 45), 60)

    assert end == time(23, 45)


def test_midnight_end_closes_the_day():
    assert duration_minutes(time(22, 0), time(0, 0)) == 120
    assert duration_minutes(time(0, 30), time(0, 0)) == 1410


def test_midnight_on_both_ends_is_still_empty():
    assert duration_minutes(time(0, 0), time(0, 0)) == 0
    with pytest.raises(ValueError):
        duration_minutes(time(0, 0), time(0, 0), strict=True)


def test_add_time_can_reach_midnight():
    start, end = add_time(time(23, 45), time(23, 45), 15)

    assert (start, end) == (time(23, 45), time(0, 0))


def test_add_time_stops_at_midnight():
    start, end = add_time(time(23, 45), time(23, 50), 30)

    assert (start, end) == (time(23, 45), time(23, 50))


def test_add_time_steps_back_from_midnight():
    start, end = add_time(time(22, 0), time(0, 0), -60)

    assert (start, end) == (time(22, 0), time(23, 0))
