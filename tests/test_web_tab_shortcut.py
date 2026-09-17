from tests.conftest import auth_get


def _handler(js: str) -> str:
    return js.split("const TAB_STEPS", 1)[1].split("boot();", 1)[0]


def test_both_modifiers_are_required_to_switch_tabs(client):
    js = auth_get(client, "/web/app.js").text
    handler = _handler(js)

    assert "event.ctrlKey && event.metaKey" in handler
    assert "event.altKey || event.shiftKey" in handler


def test_the_arrows_walk_the_tabs(client):
    js = auth_get(client, "/web/app.js").text
    handler = _handler(js)

    assert "ArrowLeft: -1" in handler
    assert "ArrowRight: 1" in handler


def test_the_tabs_are_a_ring_so_either_arrow_reaches_the_other_one(client):
    js = auth_get(client, "/web/app.js").text
    handler = _handler(js)

    assert "% TABS.length" in handler
    assert 'const TABS = ["calendar", "reports"]' in js


def test_switching_tabs_goes_through_the_same_path_as_a_click(client):
    js = auth_get(client, "/web/app.js").text

    assert "async function showTab(" in js
    assert "await showTab(actionNode.dataset.tab)" in js


def test_a_sheet_or_a_running_push_holds_the_shortcut_back(client):
    js = auth_get(client, "/web/app.js").text
    guard = js.split("function tabShortcutAllowed(", 1)[1].split("\n}\n", 1)[0]

    assert "state.busy" in guard
    assert "state.workspaceId" in guard
    assert "[data-view=settings]" in guard
    assert "[data-view=metadata]" in guard
