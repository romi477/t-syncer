from tests.conftest import auth_get


def _branch(js: str, action: str) -> str:
    return js.split(f'action === "{action}"', 1)[1].split("} else if (action ===", 1)[0]


def test_save_card_cannot_be_double_submitted(client):
    js = auth_get(client, "/web/app.js").text

    assert "setBusy(true" in _branch(js, "save-card")


def test_push_line_cannot_be_double_submitted(client):
    js = auth_get(client, "/web/app.js").text
    branch = _branch(js, "push-line")

    assert "setBusy(true" in branch
    assert "setBusy(false)" in branch


def test_the_click_handler_still_drops_clicks_while_busy(client):
    js = auth_get(client, "/web/app.js").text

    assert "if (state.busy)" in js
