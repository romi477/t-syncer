from datetime import date

from api.periods import period_bounds


def test_month_bounds_of_anchor():
    start, end = period_bounds("month", date(2026, 8, 27))

    assert start == date(2026, 8, 1)
    assert end == date(2026, 8, 31)


def test_week_is_monday_through_sunday():
    start, end = period_bounds("week", date(2026, 8, 27))  # Thursday

    assert start == date(2026, 8, 24)
    assert end == date(2026, 8, 30)
