def live_issue(value: str) -> str:

    return value.upper().replace(" ", "-")


def norm_issue(value: str) -> str:
    key = live_issue(value)
    while "--" in key:
        key = key.replace("--", "-")

    return key.strip("-")


def live_time(value: str) -> str:

    return value.replace(" ", ":")


def _digits(value: str) -> str:

    return "".join(ch for ch in value if ch.isdigit())


def _clamp_clock(hours: int, minutes: int) -> tuple[int, int]:
    hours = min(max(hours, 0), 23)
    minutes = min(max(minutes, 0), 59)

    return hours, minutes


def norm_time(value: str) -> str:
    raw = live_time(value).strip()
    if not raw:

        return ""
    if ":" in raw:
        head, _, tail = raw.partition(":")
        hours = int(_digits(head) or 0)
        minutes = int(_digits(tail) or 0)
    else:
        digits = _digits(raw)
        if len(digits) <= 2:
            hours, minutes = int(digits or 0), 0
        elif len(digits) == 3:
            hours, minutes = int(digits[0]), int(digits[1:])
        else:
            hours, minutes = int(digits[:2]), int(digits[2:4])

    if (hours, minutes) == (24, 0):  # 24:00 is how people write end of day

        return "00:00"
    hours, minutes = _clamp_clock(hours, minutes)

    return f"{hours:02d}:{minutes:02d}"
