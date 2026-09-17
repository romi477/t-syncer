from tests.conftest import auth_get


def _body(js: str, name: str) -> str:
    return js.split(f"function {name}(", 1)[1].split("\n}\n", 1)[0]


def test_the_message_field_capitalizes_its_first_letter(client):
    js = auth_get(client, "/web/app.js").text

    assert "capitalizeFirst(" in js.split("[name=message]", 1)[1].split("});", 1)[0]


def test_capitalizing_leaves_the_rest_of_the_message_alone(client):
    js = auth_get(client, "/web/app.js").text
    body = _body(js, "capitalizeFirst")

    assert "toUpperCase()" in body
    assert "slice(1)" in body


def test_capitalizing_keeps_the_caret_where_the_operator_left_it(client):
    js = auth_get(client, "/web/app.js").text

    assert "setSelectionRange" in js
