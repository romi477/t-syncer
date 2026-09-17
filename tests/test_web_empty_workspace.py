import re

from tests.conftest import auth_get


def test_boot_does_not_open_create_sheet_when_no_workspaces(client):
    js = auth_get(client, "/web/app.js").text
    boot = js.split("async function boot()", 1)[1].split("window.addEventListener", 1)[0]

    assert 'openSettings("create")' not in boot


def test_workspace_switching_uses_header_select_only(client):
    html = auth_get(client, "/web").text
    js = auth_get(client, "/web/app.js").text
    render = js.split("function renderWorkspaces()", 1)[1].split("async function loadMonth", 1)[0]

    assert 'data-field="workspace-list"' not in html
    assert 'data-field="active-workspace-name"' in html
    assert "workspace-list" not in render
    assert "select-workspace" not in js
    assert "NEW_WORKSPACE_VALUE" in js
    assert "New workspace…" in render
    assert "openSettings(\"create\")" in js.split('$("[data-field=workspace]").addEventListener("change"', 1)[1]
    assert 'data-action="new-workspace"' not in html


def test_empty_workspace_select_is_placeholder_not_empty(client):
    js = auth_get(client, "/web/app.js").text
    css = auth_get(client, "/web/app.css").text
    render = js.split("function renderWorkspaces()", 1)[1].split("async function loadMonth", 1)[0]

    assert "No workspace" in js
    assert "select.disabled = false" in render
    assert 'select.classList.toggle("is-needed", empty)' in render
    assert ".header-end .select.is-needed" in css
    assert ".header-end .select" in css
    assert "min-width" in css.split(".header-end .select", 1)[1].split("}", 1)[0]


def test_issue_and_totals_use_semantic_data_colors(client):
    css = auth_get(client, "/web/app.css").text
    js = auth_get(client, "/web/app.js").text
    html = auth_get(client, "/web/").text
    report = js.split("function loadReport()", 1)[1].split("function periodLabel", 1)[0]

    issue_block = css.split(".field-issue", 1)[1].split("}", 1)[0]
    assert "color: var(--issue-ink)" in issue_block
    assert "font-weight: 500" in issue_block

    dur_block = css.split(".dur {", 1)[1].split("}", 1)[0]
    assert "color: var(--issue-ink)" in dur_block
    assert "font-weight: 500" in dur_block

    key_block = css.split(".t-row .key", 1)[1].split("}", 1)[0]
    assert "color: var(--issue-ink)" in key_block

    time_block = css.split(".t-row .time", 1)[1].split("}", 1)[0]
    assert "color: var(--issue-ink)" in time_block

    assert 'class="time"' in report
    assert "line-count" not in html
    assert "line-count" not in js


def test_synced_row_reset_to_draft_requires_delete_in_jira_first(client):
    js = auth_get(client, "/web/app.js").text
    render = js.split("function renderRow(line)", 1)[1].split("function escapeAttr", 1)[0]
    click = js.split('action === "delete-in-jira"', 1)[1].split('action === "reset-to-draft"', 1)[0]
    reset = js.split('action === "reset-to-draft"', 1)[1].split("} else if", 1)[0]

    assert "deleteInJiraAttempted" in js
    assert 'data-action="reset-to-draft" ${state.deleteInJiraAttempted.has(String(line.id)) ? "" : "disabled"}' in render
    assert "deleteInJiraAttempted.add(String(line.id))" in click
    assert "deleteInJiraAttempted.delete(String(line.id))" in click
    assert "deleteInJiraAttempted.has(String(line.id))" in reset


def test_add_line_focuses_issue_field(client):
    js = auth_get(client, "/web/app.js").text
    add = js.split('action === "add-line"', 1)[1].split("} else if", 1)[0]

    assert "focusLineIssue(line.id)" in add
    assert 'querySelector("[name=issue_key]")' in js


def test_save_and_sync_disabled_without_lines(client):
    js = auth_get(client, "/web/app.js").text
    html = auth_get(client, "/web").text
    actions = js.split("function refreshDayActions()", 1)[1].split("\n}", 1)[0]

    assert "save.disabled = !needsSave" in actions
    assert "sync.disabled = needsSave || !needsSync" in actions
    assert 'data-action="save-card"' in html
    assert "disabled" in html.split('data-action="save-card"', 1)[1].split(">", 1)[0]
    assert "disabled" in html.split('data-action="sync-card"', 1)[1].split(">", 1)[0]


def test_web_assets_are_not_browser_cached(client):
    for path in ("/web", "/web/app.js", "/web/app.css"):
        header = auth_get(client, path).headers.get("cache-control", "").lower()
        assert "no-store" in header, path


def test_select_chevron_has_its_own_padding(client):
    css = auth_get(client, "/web/app.css").text
    assert "padding: 0 26px 0 8px" in css
    assert "-webkit-appearance: none" in css


def test_settings_sheet_has_delete_workspace_control(client):
    html = auth_get(client, "/web").text
    js = auth_get(client, "/web/app.js").text
    css = auth_get(client, "/web/app.css").text
    open_settings = js.split("function openSettings(mode)", 1)[1].split(
        "async function deleteCurrentWorkspace", 1
    )[0]
    deleter = js.split("async function deleteCurrentWorkspace()", 1)[1].split(
        "async function switchWorkspace", 1
    )[0]

    actions = html.split('<div class="sheet-actions">', 1)[1].split("</div>", 1)[0]

    assert 'data-action="delete-workspace"' in html
    assert 'title="Delete workspace"' in html
    assert 'data-action="delete-workspace"' in actions, "delete belongs in the sheet footer"
    assert actions.index("delete-workspace") < actions.index("close-settings")
    assert "delete-workspace" in open_settings
    assert "hidden" in open_settings
    assert 'action === "delete-workspace"' in js
    assert 'method: "DELETE"' in deleter
    assert "/api/workspace/" in deleter
    assert ".icon-btn.trash" in css
    assert "margin-right: auto" in css.split(".sheet-actions .trash", 1)[1].split("}", 1)[0]


def test_sync_card_uses_one_day_push_request(client):
    js = auth_get(client, "/web/app.js").text
    block = js.split('action === "sync-card"', 1)[1].split("} else if", 1)[0]

    assert "/api/workspace/${state.workspaceId}/days/${state.date}/push" in block
    assert "/worklogs/" not in block
    assert "for (" not in block


def test_push_line_uses_worklog_push_not_day_push(client):
    js = auth_get(client, "/web/app.js").text
    block = js.split('action === "push-line"', 1)[1].split("} else if", 1)[0]

    assert "/api/workspace/${state.workspaceId}/worklogs/${line.id}/push" in block
    assert "/days/${state.date}/push" not in block


def test_time_steppers_are_link_style_not_fields(client):
    css = auth_get(client, "/web/app.css").text
    step = css.split(".step {", 1)[1].split("}", 1)[0]
    step_btn = css.split(".step button {", 1)[1].split("}", 1)[0]

    assert "border:" not in step
    assert "background:" not in step
    assert "box-shadow:" not in step
    assert "background: transparent" in step_btn
    assert "color: var(--blue-step)" in step_btn
    assert "font-weight: 600" in step_btn
    down = css.split(".step button.down {", 1)[1].split("}", 1)[0]
    down_rule = css.split(".step button.down::before", 1)[1].split("}", 1)[0]
    assert "color: var(--blue-step-down)" in down
    assert "border-top:" not in down
    assert "width: 24px" in down_rule
    assert "border-top: 1px solid" in down_rule
    assert "text-decoration: underline" in css.split(".step button:hover:not(:disabled)", 1)[1]


def test_synced_row_fields_look_locked_not_editable(client):
    js = auth_get(client, "/web/app.js").text
    css = auth_get(client, "/web/app.css").text
    render = js.split("function renderRow(line)", 1)[1].split("function escapeAttr", 1)[0]
    rule = css.split(".row.is-synced .field.is-frozen,\n.row.is-synced .dur.is-frozen {", 1)[1].split("}", 1)[0]

    assert 'const frozenClass = locked ? " is-frozen" : ""' in render
    assert 'class="field field-issue${frozenClass}"' in render
    assert 'class="dur${frozenClass}"' in render
    assert ".row.is-synced .dur.is-frozen" in css
    assert "background: transparent" in rule
    assert "pointer-events: none" in rule
    assert "box-shadow: none" in rule
    assert ".row.is-synced .field.is-frozen:focus" in css


def test_synced_row_shows_lock_instead_of_hiding_push(client):
    js = auth_get(client, "/web/app.js").text
    css = auth_get(client, "/web/app.css").text
    render = js.split("function renderRow(line)", 1)[1].split("function escapeAttr", 1)[0]

    assert "const pushControl = locked" in render
    assert 'class="sync-lock"' in render
    assert "Synced to Jira" in render
    assert 'data-action="push-line"' in render
    assert '${locked ? "hidden" : ""}' not in render
    assert ".sync-lock" in css


def test_synced_row_id_available_via_metadata_menu(client):
    js = auth_get(client, "/web/app.js").text
    render = js.split("function renderRow(line)", 1)[1].split("function escapeAttr", 1)[0]

    assert 'class="row-id"' not in render
    assert 'data-action="get-metadata"' in render
    assert "Jira worklog" not in render


def test_new_line_does_not_prefill_issue_or_times(client):
    js = auth_get(client, "/web/app.js").text
    html = auth_get(client, "/web").text
    new_line = js.split("function newLine(seed = {})", 1)[1].split(
        "async function loadWorkspaces", 1
    )[0]
    render = js.split("function renderRow(line)", 1)[1].split("function escapeAttr", 1)[0]

    assert "fallbackStart()" not in new_line
    assert "seed.start || null" in new_line
    assert "seed.end || null" in new_line
    assert 'placeholder="qbo 120"' not in render
    assert 'placeholder="9 00"' not in render
    assert 'placeholder="11 30"' not in render
    assert "autocomplete=\"off\"" in render
    assert 'data-field="default-start"' not in html
    assert "The first line starts at" not in html


def test_worklog_status_stripe_follows_row_radius(client):
    css = auth_get(client, "/web/app.css").text
    row = css.split(".row {", 1)[1].split("}", 1)[0]

    assert "linear-gradient(var(--status-accent)" in row
    assert "/ 3px 100% no-repeat" in row
    assert ".row::before" not in css


def test_worklog_row_outline_is_half_header_chrome_line(client):
    css = auth_get(client, "/web/app.css").text
    root = css.split(":root {", 1)[1].split("}", 1)[0]
    header = css.split(".header {", 1)[1].split("}", 1)[0]
    row = css.split(".row {", 1)[1].split("}", 1)[0]

    assert "--chrome-line-width: 1px" in root
    assert "--row-line-width: 0.5px" in root
    assert "border: var(--chrome-line-width) solid var(--chrome-line)" in header
    assert "border: var(--row-line-width) solid var(--chrome-line)" in row


def test_column_headers_align_with_field_cells(client):
    css = auth_get(client, "/web/app.css").text
    cols = css.split(".cols {", 1)[1].split("}", 1)[0]
    grid = css.split(".cols, .row-grid {", 1)[1].split("}", 1)[0]

    assert "text-align: center" in cols
    assert ".range-head span { text-align: center; }" in css
    assert "text-align: center" in css.split(".field-issue {", 1)[1].split("}", 1)[0]
    assert "padding: 10px 8px" in cols
    assert "margin: 0 14px" in cols
    assert "margin: 0 14px 2px" not in cols


def test_row_grid_uses_display_contents_not_nested_grid(client):
    css = auth_get(client, "/web/app.css").text

    assert ".row-grid,\n.msg-row { display: contents; }" in css
    assert ".row-grid,\n.range {" not in css


def test_start_and_end_headers_are_separate_columns(client):
    html = auth_get(client, "/web").text
    js = auth_get(client, "/web/app.js").text
    headers = html.split('class="cols"', 1)[1]
    render = js.split("function renderRow(line)", 1)[1].split("function escapeAttr", 1)[0]

    assert "START – END" not in headers
    assert ">START<" in headers
    assert ">END<" in headers
    assert 'class="range-head"' in html
    assert 'class="range"' in render
    assert "range-sep" not in render


def test_month_pending_is_gray_until_positive(client):
    html = auth_get(client, "/web/").text
    js = auth_get(client, "/web/app.js").text
    css = auth_get(client, "/web/app.css").text
    load_month = js.split("async function loadMonth()", 1)[1].split("async function loadDay", 1)[0]

    assert 'data-field="month-pending">0m</b>' in html
    assert 'class="is-pending" data-field="month-pending"' not in html
    assert 'classList.toggle("is-pending", monthPending > 0)' in load_month
    assert "color: var(--muted)" in css.split(".stat b {", 1)[1].split("}", 1)[0]
    assert ".stat b.is-pending { color: var(--amber); }" in css


def test_push_buttons_show_pending_mark_instead_of_yellow_fill(client):
    js = auth_get(client, "/web/app.js").text
    css = auth_get(client, "/web/app.css").text

    assert "setPushButtonLabel" in js
    assert "push-pending-mark" in js
    assert "push-pending-icon" not in js
    assert ".push-pending-mark" in css
    assert ".push-pending-icon" not in css


def test_sync_locks_ui_with_spinner_until_push_finishes(client):
    html = auth_get(client, "/web").text
    js = auth_get(client, "/web/app.js").text
    css = auth_get(client, "/web/app.css").text
    push = js.split("async function pushResults", 1)[1].split("async function", 1)[0]
    busy = js.split("function setBusy", 1)[1].split("function closeMenus", 1)[0]
    click = js.split('document.addEventListener("click"', 1)[1].split("const action =", 1)[0]

    assert 'data-view="busy"' not in html
    assert "btn-spin" in css
    assert ".btn.is-busy" in css
    assert "@keyframes spin" in css
    assert "btn-spin" in busy
    assert "is-busy" in busy
    assert "setBusy(true" in push
    assert "setBusy(false)" in push
    assert "state.busy" in click
    assert "actionNode)" in js.split('action === "sync-card"', 1)[1]
    assert "actionNode)" in js.split('action === "push-week"', 1)[1]
    assert "actionNode)" in js.split('action === "push-month"', 1)[1]


def test_calendar_arrow_keys_move_days_with_alt(client):
    js = auth_get(client, "/web/app.js").text
    keyboard = js.split('window.addEventListener("keydown"', 1)[1].split("boot();", 1)[0]

    assert "event.altKey" in keyboard
    assert "calendarShortcutAllowed" in keyboard
    assert "ArrowLeft: -1" in keyboard
    assert "ArrowRight: 1" in keyboard
    assert "ArrowUp: -7" in keyboard
    assert "ArrowDown: 7" in keyboard
    assert "moves[event.code]" in keyboard
    assert "moveCalendarDay(delta)" in keyboard
    assert "KeyI" not in keyboard
    assert "KeyS" not in keyboard


def test_ctrl_s_and_ctrl_i_drive_the_card_buttons(client):
    js = auth_get(client, "/web/app.js").text
    html = auth_get(client, "/web").text
    block = js.split("const CARD_SHORTCUTS", 1)[1].split("boot();", 1)[0]

    assert '{s: "save-card", i: "add-line"}' in block
    assert "event.ctrlKey || event.metaKey" in block
    assert "event.preventDefault()" in block, "must not let the browser save the page"
    assert "cardShortcutAllowed()" in block
    assert 'title="Save card (Ctrl+S)"' in html
    assert 'title="Add line (Ctrl+I)"' in html


def test_the_card_shortcut_guard_allows_typing_in_a_field(client):
    js = auth_get(client, "/web/app.js").text
    guard = js.split("function cardShortcutAllowed", 1)[1].split("\n}", 1)[0]

    assert "state.busy" in guard
    assert "data-view=settings" in guard
    assert "TEXTAREA" not in guard, "saving while a line field has focus is the point"


def _frontend_tags(js: str) -> list[tuple[str, str]]:
    block = js.split("const TAGS = [", 1)[1].split("];", 1)[0]

    return re.findall(r'\{code: "([A-Z]+)", label: "([^"]+)"\}', block)


def test_the_tag_dropdown_matches_the_backend_catalog(client):
    from api.tags import TAGS

    js = auth_get(client, "/web/app.js").text

    assert _frontend_tags(js) == [(tag.code, tag.label) for tag in TAGS]


def test_tag_options_carry_their_help_text(client):
    js = auth_get(client, "/web/app.js").text
    options = js.split("const tagOptions", 1)[1].split(".join(", 1)[0]

    assert "title=" in options, "hovering an option must explain the tag"
    assert "escapeAttr(tag.label)" in options


def test_the_tag_field_explains_itself_on_hover(client):
    js = auth_get(client, "/web/app.js").text
    row = js.split("function renderRow", 1)[1].split("function escapeAttr", 1)[0]
    binding = js.split('row.querySelector("[name=tag]")', 1)[1].split("});", 1)[0]

    assert 'title="${escapeAttr(tagHelp(line.tag))}"' in row
    assert "event.target.title = tagHelp(line.tag)" in binding, "title must follow the choice"
