from calendar import monthrange
from datetime import date, timedelta


def period_bounds(period: str, anchor: date) -> tuple[date, date]:
    if period == "month":
        last_day = monthrange(anchor.year, anchor.month)[1]

        return date(anchor.year, anchor.month, 1), date(anchor.year, anchor.month, last_day)
    if period == "week":
        start = anchor - timedelta(days=anchor.weekday())

        return start, start + timedelta(days=6)

    raise ValueError(f"unknown period: {period}")
