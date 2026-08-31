from api.parse import live_issue, live_time, norm_issue, norm_time


def test_live_issue_turns_spaces_into_dash_and_uppercases():
    assert live_issue("qbo 120") == "QBO-120"


def test_norm_issue_strips_stray_dashes():
    assert norm_issue(" QBO-120- ") == "QBO-120"


def test_norm_time_from_compact_and_spaced():
    assert norm_time("930") == "09:30"
    assert norm_time("9 00") == "09:00"
    assert norm_time("9:0") == "09:00"
    assert norm_time("1745") == "17:45"


def test_live_time_keeps_colon_while_typing():
    assert live_time("9 3") == "9:3"


def test_norm_time_ignores_non_numeric_around_colon():
    assert norm_time("aa:bb") == "00:00"
    assert norm_time("9:xx") == "09:00"
    assert norm_time("h9:m30") == "09:30"


def test_twenty_four_hundred_is_midnight():
    assert norm_time("24:00") == "00:00"
    assert norm_time("2400") == "00:00"
