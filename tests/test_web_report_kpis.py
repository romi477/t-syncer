from tests.conftest import auth_get


def _block(css: str, selector: str) -> str:
    return css.split(f"\n{selector} {{", 1)[1].split("}", 1)[0]


def test_the_report_cards_carry_the_app_blue(client):
    css = auth_get(client, "/web/app.css").text

    assert "var(--blue-soft)" in _block(css, ".kpi")


def test_the_report_numbers_are_blue_rather_than_ink(client):
    css = auth_get(client, "/web/app.css").text
    numbers = _block(css, ".kpi b")

    assert "var(--blue-ink)" in numbers
    assert "var(--issue-ink)" not in numbers
