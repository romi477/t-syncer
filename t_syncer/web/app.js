// Order and labels mirror api/tags.py; a test fails if the two drift apart.
const TAGS = [
  {code: "DEV", label: "Development"},
  {code: "INT", label: "Internal communications"},
  {code: "SUP", label: "Support and escalations"},
  {code: "QA", label: "Testing (separate activity)"},
  {code: "DOC", label: "Documentation"},
  {code: "REL", label: "Releases"},
  {code: "DEM", label: "Demos and customer meetings"},
];
const NEW_WORKSPACE_VALUE = "__new__";
const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];
const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

const state = {
  workspaces: [],
  workspaceId: null,
  date: isoDate(new Date()),
  calYear: new Date().getFullYear(),
  calMonth: new Date().getMonth(),
  days: {},
  lines: [],
  dirty: false,
  tab: "calendar",
  period: "month",
  nextTemp: 1,
  savedFingerprint: "[]",
  busy: false,
  busyButton: null,
  toastTimer: null,
  deleteInJiraAttempted: new Set(),
};

function isoDate(value) {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");

  return `${year}-${month}-${day}`;
}

function parseIso(value) {
  const [year, month, day] = value.split("-").map(Number);

  return new Date(year, month - 1, day);
}

function addDays(iso, delta) {
  const date = parseIso(iso);
  date.setDate(date.getDate() + delta);

  return isoDate(date);
}

function liveIssue(value) {
  return value.toUpperCase().replaceAll(" ", "-");
}

function normIssue(value) {
  return liveIssue(value).replace(/-+/g, "-").replace(/^-|-$/g, "");
}

function liveTime(value) {
  return value.replaceAll(" ", ":");
}

function capitalizeFirst(value) {
  return value.slice(0, 1).toUpperCase() + value.slice(1);
}

function digitsOf(value) {
  return String(value).replace(/\D/g, "");
}

function normTime(value) {
  const raw = liveTime(value).trim();
  if (!raw) {
    return "";
  }
  let hours;
  let minutes;
  if (raw.includes(":")) {
    const [head, tail] = raw.split(":");
    hours = Number(digitsOf(head) || 0);
    minutes = Number(digitsOf(tail) || 0);
  } else {
    const digits = digitsOf(raw);
    if (digits.length <= 2) {
      hours = Number(digits || 0);
      minutes = 0;
    } else if (digits.length === 3) {
      hours = Number(digits[0]);
      minutes = Number(digits.slice(1));
    } else {
      hours = Number(digits.slice(0, 2));
      minutes = Number(digits.slice(2, 4));
    }
  }
  if (hours === 24 && minutes === 0) {   // 24:00 is how people write end of day
    return "00:00";
  }
  hours = Math.min(Math.max(hours, 0), 23);
  minutes = Math.min(Math.max(minutes, 0), 59);

  return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}`;
}

function toMinutes(clock) {
  if (!clock) {
    return null;
  }
  const [hours, minutes] = clock.split(":").map(Number);

  return hours * 60 + minutes;
}

function fromMinutes(total) {
  const hours = Math.floor(total / 60);
  const minutes = total % 60;

  return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}`;
}

// 00:00 as an end closes the day: 22:00-00:00 ends at 24:00, not at 0. Mirrors
// _end_minutes in api/duration.py.
function endMinutes(start, end) {
  const minutes = toMinutes(end);
  if (minutes === 0 && toMinutes(start) > 0) {
    return 24 * 60;
  }

  return minutes;
}

// Hovering the closed select should explain the tag it currently holds; an
// option's own title only shows while the list is open.
function tagHelp(code) {
  const tag = TAGS.find((item) => item.code === code);

  return tag ? tag.label : "No tag on this line";
}

function durationMinutes(start, end) {
  const from = toMinutes(start);
  const to = toMinutes(end);
  if (from === null || to === null) {
    return 0;
  }
  const until = endMinutes(start, end);
  if (until <= from) {
    return 0;
  }

  return until - from;
}

function formatDuration(minutes) {
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  if (hours && rest) {
    return `${hours}h ${rest}m`;
  }
  if (hours) {
    return `${hours}h`;
  }

  return `${rest}m`;
}

function addTime(start, end, delta, fallbackStart) {
  let nextStart = start;
  if (!nextStart) {
    nextStart = fallbackStart || "09:00";
  }
  let nextEnd = end;
  if (!nextEnd) {
    if (delta <= 0) {
      return [nextStart, nextEnd];
    }
    nextEnd = nextStart;
  }
  const next = endMinutes(nextStart, nextEnd) + delta;
  if (next > 24 * 60 || next <= toMinutes(nextStart)) {
    return [nextStart, end];
  }
  if (next === 24 * 60) {
    return [nextStart, "00:00"];
  }

  return [nextStart, fromMinutes(next)];
}

async function api(path, options = {}) {
  const headers = Object.assign({"Accept": "application/json"}, options.headers || {});
  if (options.body && !(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }
  const response = await fetch(path, Object.assign({credentials: "same-origin"}, options, {headers}));
  if (response.status === 204) {
    return null;
  }
  const text = await response.text();
  const data = text ? JSON.parse(text) : null;
  if (!response.ok) {
    const detail = data && data.detail ? data.detail : response.statusText;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }

  return data;
}

function $(selector, root = document) {
  return root.querySelector(selector);
}

function $all(selector, root = document) {
  return [...root.querySelectorAll(selector)];
}

function currentWorkspace() {
  return state.workspaces.find((item) => item.id === state.workspaceId) || null;
}

function markDirty(value = true) {
  state.dirty = value;
  refreshDayActions();
}

function cardFingerprint() {
  return JSON.stringify(state.lines.map((line) => [
    line.local ? "local" : line.id,
    line.issue_key || "",
    line.tag || "",
    line.message || "",
    line.start || "",
    line.end || "",
  ]));
}

function rememberSavedCard() {
  state.savedFingerprint = cardFingerprint();
}

function refreshDirty() {
  markDirty(cardFingerprint() !== state.savedFingerprint);
}

function refreshDayActions() {
  const save = $("[data-action=save-card]");
  const sync = $("[data-action=sync-card]");
  if (!save || !sync) {
    return;
  }
  const needsSave = state.dirty;
  const needsSync = state.lines.some((line) => line.status !== "synced");
  save.disabled = !needsSave;
  save.classList.toggle("is-needed", needsSave);
  sync.disabled = needsSave || !needsSync;
}

function dismissToast() {
  if (state.toastTimer) {
    clearTimeout(state.toastTimer);
    state.toastTimer = null;
  }
  $("[data-view=toast]").hidden = true;
}

function showToast(title, items) {
  $("[data-field=toast-title]").textContent = title;
  $("[data-field=toast-items]").innerHTML = items.map((item) => {
    const mark = item.ok ? "mark-ok" : "mark-no";
    const sign = item.ok ? "✓" : "✕";

    return `<div class="toast-item"><span class="${mark}">${sign}</span><span>${escapeHtml(item.text)}</span></div>`;
  }).join("");
  $("[data-view=toast]").hidden = false;
  if (state.toastTimer) {
    clearTimeout(state.toastTimer);
  }
  state.toastTimer = setTimeout(dismissToast, 5000);
}

function pendingInRange(fromIso, toIso) {
  let pending = 0;
  const cursor = parseIso(fromIso);
  const end = parseIso(toIso);
  while (cursor <= end) {
    pending += state.days[isoDate(cursor)]?.pending_minutes || 0;
    cursor.setDate(cursor.getDate() + 1);
  }

  return pending;
}

function setPushButtonLabel(button, label, showPendingMark) {
  const spin = button.querySelector(".btn-spin");
  button.replaceChildren();
  if (spin) {
    button.append(spin);
  }
  if (showPendingMark) {
    const mark = document.createElement("span");
    mark.className = "push-pending-mark";
    mark.textContent = "!";
    mark.setAttribute("aria-hidden", "true");
    button.append(mark);
    button.append(document.createTextNode(` ${label}`));
  } else {
    button.append(document.createTextNode(label));
  }
}

function refreshPushButtons() {
  const weekBtn = $("[data-action=push-week]");
  const monthBtn = $("[data-action=push-month]");
  if (!weekBtn || !monthBtn) {
    return;
  }
  if (!state.workspaceId) {
    setPushButtonLabel(weekBtn, "Week locked", false);
    setPushButtonLabel(monthBtn, "Month locked", false);
    weekBtn.disabled = true;
    monthBtn.disabled = true;
    weekBtn.classList.remove("is-pending");
    monthBtn.classList.remove("is-pending");
    weekBtn.classList.add("is-locked");
    monthBtn.classList.add("is-locked");

    return;
  }
  const [weekFrom, weekTo] = periodBounds("week", state.date);
  const [monthFrom, monthTo] = periodBounds("month", state.date);
  const weekPending = pendingInRange(weekFrom, weekTo);
  const monthPending = pendingInRange(monthFrom, monthTo);
  setPushButtonLabel(weekBtn, weekPending > 0 ? "Week not pushed" : "Week locked", weekPending > 0);
  setPushButtonLabel(monthBtn, monthPending > 0 ? "Month not pushed" : "Month locked", monthPending > 0);
  weekBtn.disabled = weekPending === 0 || state.busy;
  monthBtn.disabled = monthPending === 0 || state.busy;
  weekBtn.classList.toggle("is-pending", weekPending > 0);
  monthBtn.classList.toggle("is-pending", monthPending > 0);
  weekBtn.classList.toggle("is-locked", weekPending === 0);
  monthBtn.classList.toggle("is-locked", monthPending === 0);
}

function setBusy(on, button) {
  state.busy = on;
  if (!on) {
    const current = state.busyButton;
    if (current) {
      current.classList.remove("is-busy");
      const spin = current.querySelector(".btn-spin");
      if (spin) {
        spin.remove();
      }
    }
    state.busyButton = null;
    refreshPushButtons();

    return;
  }
  state.busyButton = button || null;
  if (!button) {
    refreshPushButtons();

    return;
  }
  button.classList.add("is-busy");
  if (!button.classList.contains("btn-save") && !button.querySelector(".btn-spin")) {
    const spin = document.createElement("span");
    spin.className = "btn-spin";
    spin.setAttribute("aria-hidden", "true");
    button.prepend(spin);
  }
  refreshPushButtons();
}

function closeMenus() {
  $all(".menu").forEach((menu) => {
    menu.hidden = true;
  });
}

function linePayload(line) {
  return {
    issue_key: line.issue_key,
    tag: line.tag,
    message: line.message,
    start: line.start,
    end: line.end,
  };
}

function fallbackStart() {
  for (let index = state.lines.length - 1; index >= 0; index -= 1) {
    if (state.lines[index].end) {
      return state.lines[index].end;
    }
  }

  return "09:00";
}

function newLine(seed = {}) {
  const start = seed.start || null;
  const end = seed.end || null;

  return {
    id: `tmp-${state.nextTemp++}`,
    issue_key: seed.issue_key || "",
    tag: seed.tag || null,
    message: seed.message || "",
    start,
    end,
    duration_minutes: durationMinutes(start, end),
    status: "draft",
    jira_worklog_id: null,
    last_error: null,
    local: true,
  };
}

async function loadWorkspaces() {
  state.workspaces = await api("/api/workspace");
  const stored = Number(localStorage.getItem("tsyncer.workspace") || 0);
  state.workspaceId = state.workspaces.some((item) => item.id === stored)
    ? stored
    : (state.workspaces[0] ? state.workspaces[0].id : null);
  renderWorkspaces();
}

function renderWorkspaces() {
  const select = $("[data-field=workspace]");
  const empty = state.workspaces.length === 0;
  const options = [];
  if (empty) {
    options.push('<option value="" disabled selected>No workspace</option>');
  } else {
    options.push(...state.workspaces.map((item) => (
      `<option value="${item.id}" ${item.id === state.workspaceId ? "selected" : ""}>${escapeHtml(item.name)}</option>`
    )));
  }
  options.push(`<option value="${NEW_WORKSPACE_VALUE}">New workspace…</option>`);
  select.innerHTML = options.join("");
  select.disabled = false;
  select.classList.toggle("is-needed", empty);
  const settings = $("[data-action=open-settings]");
  if (settings) {
    settings.disabled = empty;
  }
  const workspace = currentWorkspace();
  const sidebarWs = $(".sidebar-ws");
  if (sidebarWs) {
    sidebarWs.classList.toggle("is-empty", !workspace);
  }
  const name = $("[data-field=active-workspace-name]");
  if (name) {
    name.textContent = workspace ? workspace.name : "No workspace";
  }
  const total = $("[data-field=active-workspace-total]");
  if (total) {
    total.hidden = !workspace;
    if (!workspace) {
      total.textContent = "0m";
      total.classList.remove("is-pending");
    }
  }
}

async function loadMonth() {
  if (!state.workspaceId) {
    state.days = {};
    $("[data-field=month-pending]").textContent = "0m";
    $("[data-field=month-pending]").classList.remove("is-pending");
    renderCalendar();
    refreshPushButtons();

    return;
  }
  const monthStart = isoDate(new Date(state.calYear, state.calMonth, 1));
  const monthEnd = isoDate(new Date(state.calYear, state.calMonth + 1, 0));
  const [weekFrom, weekTo] = periodBounds("week", state.date);
  const [anchorMonthFrom, anchorMonthTo] = periodBounds("month", state.date);
  const from = [monthStart, weekFrom, anchorMonthFrom].sort()[0];
  const to = [monthEnd, weekTo, anchorMonthTo].sort().at(-1);
  const body = await api(`/api/workspace/${state.workspaceId}/days?from=${from}&to=${to}`);
  state.days = Object.fromEntries((body.days || []).map((day) => [day.date, day]));
  const monthTotal = (body.days || [])
    .filter((day) => day.date >= monthStart && day.date <= monthEnd)
    .reduce((sum, day) => sum + day.total_minutes, 0);
  const monthPending = (body.days || [])
    .filter((day) => day.date >= monthStart && day.date <= monthEnd)
    .reduce((sum, day) => sum + day.pending_minutes, 0);
  $("[data-field=month-pending]").textContent = formatDuration(monthPending);
  $("[data-field=month-pending]").classList.toggle("is-pending", monthPending > 0);
  const badge = $("[data-field=active-workspace-total]");
  if (badge) {
    badge.textContent = formatDuration(monthTotal);
    badge.classList.toggle("is-pending", monthPending > 0);
  }
  renderCalendar();
  refreshPushButtons();
}

function renderCalendar() {
  $("[data-field=month-label]").textContent = `${MONTHS[state.calMonth]} ${state.calYear}`;
  const grid = $("[data-field=calendar]");
  const first = new Date(state.calYear, state.calMonth, 1);
  const startOffset = (first.getDay() + 6) % 7;
  const cursor = new Date(state.calYear, state.calMonth, 1 - startOffset);
  const today = isoDate(new Date());
  const labels = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
    .map((name) => `<span class="cal-dow">${name}</span>`).join("");
  const cells = [];
  for (let index = 0; index < 42; index += 1) {
    const iso = isoDate(cursor);
    const out = cursor.getMonth() !== state.calMonth;
    const summary = state.days[iso];
    const classes = ["cal-day"];
    if (out) {
      classes.push("is-out");
    }
    if (iso === today) {
      classes.push("is-today");
    }
    if (iso === state.date) {
      classes.push("is-on");
    }
    let dot = "";
    if (summary) {
      const kind = summary.status === "error" ? "is-err" : (summary.status === "synced" ? "is-ok" : "is-draft");
      dot = `<span class="cal-dot ${kind}"></span>`;
    } else {
      dot = `<span class="cal-dot"></span>`;
    }
    cells.push(
      `<button class="${classes.join(" ")}" type="button" data-action="pick-day" data-date="${iso}"><span>${cursor.getDate()}</span>${dot}</button>`
    );
    cursor.setDate(cursor.getDate() + 1);
  }
  grid.innerHTML = labels + cells.join("");
}

async function loadDay() {
  if (!state.workspaceId) {
    state.lines = [];
    rememberSavedCard();
    markDirty(false);
    renderDay();
    return;
  }
  const card = await api(`/api/workspace/${state.workspaceId}/days/${state.date}`);
  state.lines = card.lines || [];
  rememberSavedCard();
  markDirty(false);
  renderDay();
}

function renderDay() {
  const date = parseIso(state.date);
  const today = isoDate(new Date());
  $("[data-field=date-label]").textContent = `${WEEKDAYS[(date.getDay() + 6) % 7]}, ${date.getDate()} ${MONTHS[date.getMonth()]}`;
  $("[data-field=today-jump]").hidden = state.date === today;
  const total = state.lines.reduce((sum, line) => sum + durationMinutes(line.start, line.end), 0);
  const count = state.lines.length;
  $("[data-field=day-total]").textContent = formatDuration(total);
  const empty = count === 0;
  $("[data-field=empty-day]").hidden = !empty;
  $("[data-field=lines-wrap]").hidden = empty;
  $("[data-field=lines]").innerHTML = state.lines.map(renderRow).join("");
  bindRows();
  refreshDayActions();
}

function focusLineIssue(lineId) {
  const row = document.querySelector(`[data-field=lines] .row[data-id="${CSS.escape(String(lineId))}"]`);
  const issue = row?.querySelector("[name=issue_key]");
  if (!issue || issue.disabled) {
    return;
  }
  issue.focus();
}

function renderRow(line) {
  const locked = line.status === "synced";
  const duration = durationMinutes(line.start, line.end);
  const tagOptions = [`<option value="" title="No tag on this line">No tag</option>`]
    .concat(TAGS.map((tag) => (
      `<option value="${tag.code}" title="${escapeAttr(tag.label)}" ${line.tag === tag.code ? "selected" : ""}>${tag.code}</option>`
    )))
    .join("");
  const note = line.status === "error" ? (line.last_error || "") : "";
  const statusKind = line.status === "synced"
    ? "synced"
    : (line.status === "error" ? "error" : (line.local ? "local" : "draft"));
  const statusTitle = statusKind === "synced" ? "Synced" : (statusKind === "error" ? "Error" : (statusKind === "local" ? "Unsaved" : "Saved"));
  const menu = locked
    ? `<button type="button" data-action="get-metadata">Get metadata</button>
       <button type="button" data-action="delete-in-jira">Delete in Jira</button>
       <button type="button" data-action="reset-to-draft" ${state.deleteInJiraAttempted.has(String(line.id)) ? "" : "disabled"}>Reset to draft</button>
       <button type="button" data-action="delete-line" disabled>Delete locally</button>`
    : `<button type="button" data-action="get-metadata">Get metadata</button>
       <button class="is-danger" type="button" data-action="delete-line">Delete line</button>`;

  const pushControl = locked
    ? `<span class="sync-lock" title="Synced to Jira" aria-label="Synced to Jira">
        <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <rect x="3.5" y="7" width="9" height="7" rx="1.2"></rect>
          <path d="M5.5 7V5.2a2.5 2.5 0 0 1 5 0V7"></path>
        </svg>
      </span>`
    : `<button class="icon-btn ghost push" type="button" data-action="push-line" title="Push this line to Jira">
        <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M2.4 7.3L13.7 2.7 8.9 13.4 7.4 8.7z"></path>
          <path d="M7.4 8.7L13.7 2.7"></path>
        </svg>
      </button>`;

  const frozenClass = locked ? " is-frozen" : "";

  return `<article class="row row-status-${statusKind} ${locked ? "is-synced" : ""}" data-id="${line.id}" data-status="${line.status}" title="${statusTitle}">
    <div class="row-grid">
      <span class="row-lead" aria-hidden="true"></span>
      <input class="field field-issue${frozenClass}" name="issue_key" value="${escapeAttr(line.issue_key || "")}" autocomplete="off" ${locked ? "disabled" : ""}>
      <select class="field${frozenClass}" name="tag" aria-label="Tag" title="${escapeAttr(tagHelp(line.tag))}" ${locked ? "disabled" : ""}>${tagOptions}</select>
      <div class="range">
        <input class="field field-time${frozenClass}" name="start" value="${escapeAttr(line.start || "")}" aria-label="Start" autocomplete="off" ${locked ? "disabled" : ""}>
        <input class="field field-time${frozenClass}" name="end" value="${escapeAttr(line.end || "")}" aria-label="End" autocomplete="off" ${locked ? "disabled" : ""}>
      </div>
      <div class="steps ${locked ? "is-locked" : ""}">
        <div class="step"><button type="button" data-delta="60">+1h</button><button class="down" type="button" data-delta="-60">−1h</button></div>
        <div class="step"><button type="button" data-delta="30">+30m</button><button class="down" type="button" data-delta="-30">−30m</button></div>
        <div class="step"><button type="button" data-delta="15">+15m</button><button class="down" type="button" data-delta="-15">−15m</button></div>
      </div>
      <span></span>
      <span class="dur${frozenClass}" data-field="duration">${duration ? formatDuration(duration) : "—"}</span>
      <div class="row-actions">
        ${pushControl}
        <button class="icon-btn ghost" type="button" data-action="duplicate" title="Duplicate line">⧉</button>
        <button class="icon-btn ghost" type="button" data-action="more" title="More actions">···</button>
        <div class="menu" hidden>${menu}</div>
      </div>
    </div>
    <div class="msg-row">
      <input class="field field-msg${frozenClass}" name="message" placeholder="What was done" value="${escapeAttr(line.message || "")}" ${locked ? "disabled" : ""}>
    </div>
    <div class="note ${line.status === "error" ? "is-error" : ""}" data-field="note" ${note ? "" : "hidden"}>${escapeHtml(note)}</div>
  </article>`;
}

function escapeAttr(value) {
  return String(value).replaceAll("&", "&amp;").replaceAll('"', "&quot;").replaceAll("<", "&lt;");
}

function escapeHtml(value) {
  return String(value).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
}

function findLine(id) {
  return state.lines.find((line) => String(line.id) === String(id));
}

function bindRows() {
  $all("[data-field=lines] .row").forEach((row) => {
    const line = findLine(row.dataset.id);
    if (!line) {
      return;
    }
    const issue = row.querySelector("[name=issue_key]");
    issue.addEventListener("input", () => {
      issue.value = liveIssue(issue.value);
      line.issue_key = issue.value;
      refreshDirty();
    });
    issue.addEventListener("blur", () => {
      issue.value = normIssue(issue.value);
      line.issue_key = issue.value;
      refreshDirty();
    });
    row.querySelector("[name=tag]").addEventListener("change", (event) => {
      line.tag = event.target.value || null;
      event.target.title = tagHelp(line.tag);
      refreshDirty();
    });
    const start = row.querySelector("[name=start]");
    const end = row.querySelector("[name=end]");
    start.addEventListener("input", () => {
      start.value = liveTime(start.value);
    });
    end.addEventListener("input", () => {
      end.value = liveTime(end.value);
    });
    start.addEventListener("blur", () => {
      start.value = normTime(start.value);
      line.start = start.value || null;
      refreshRowDuration(row, line);
      refreshDirty();
    });
    end.addEventListener("blur", () => {
      end.value = normTime(end.value);
      line.end = end.value || null;
      refreshRowDuration(row, line);
      refreshDirty();
    });
    row.querySelector("[name=message]").addEventListener("input", (event) => {
      const field = event.target;
      const capitalized = capitalizeFirst(field.value);
      if (capitalized !== field.value) {
        // Same length, so the caret belongs where it was: assigning value alone
        // would throw it to the end of the field mid-word.
        const caret = field.selectionStart;
        field.value = capitalized;
        field.setSelectionRange(caret, caret);
      }
      line.message = field.value;
      refreshDirty();
    });
    row.querySelectorAll("[data-delta]").forEach((button) => {
      button.addEventListener("click", () => {
        if (line.status === "synced") {
          return;
        }
        const [nextStart, nextEnd] = addTime(line.start, line.end, Number(button.dataset.delta), fallbackStart());
        line.start = nextStart;
        line.end = nextEnd;
        start.value = nextStart || "";
        end.value = nextEnd || "";
        refreshRowDuration(row, line);
        refreshDirty();
      });
    });
  });
}

function refreshRowDuration(row, line) {
  line.duration_minutes = durationMinutes(line.start, line.end);
  row.querySelector("[data-field=duration]").textContent = line.duration_minutes
    ? formatDuration(line.duration_minutes)
    : "—";
  const total = state.lines.reduce((sum, item) => sum + durationMinutes(item.start, item.end), 0);
  $("[data-field=day-total]").textContent = formatDuration(total);
}

async function saveCard() {
  if (!state.workspaceId) {
    return;
  }
  for (const line of state.lines) {
    if (line.status === "synced") {
      continue;
    }
    if (line.local) {
      const created = await api(`/api/workspace/${state.workspaceId}/days/${state.date}/worklogs`, {
        method: "POST",
        body: JSON.stringify(linePayload(line)),
      });
      line.id = created.id;
      line.local = false;
      line.status = created.status;
    } else {
      await api(`/api/workspace/${state.workspaceId}/worklogs/${line.id}`, {
        method: "PATCH",
        body: JSON.stringify(linePayload(line)),
      });
    }
  }
  markDirty(false);
  await loadDay();
  await loadMonth();
}

async function ensureSaved() {
  if (state.dirty) {
    await saveCard();
  }
}

async function moveCalendarDay(delta) {
  if (state.busy || !state.workspaceId) {
    return;
  }
  await ensureSaved();
  state.date = addDays(state.date, delta);
  const picked = parseIso(state.date);
  state.calYear = picked.getFullYear();
  state.calMonth = picked.getMonth();
  await loadMonth();
  await loadDay();
}

function cardShortcutAllowed() {
  if (state.tab !== "calendar" || state.busy || !state.workspaceId) {
    return false;
  }

  return $("[data-view=settings]").hidden && $("[data-view=metadata]").hidden;
}

const TABS = ["calendar", "reports"];

async function showTab(name) {
  state.tab = name;
  $all("[data-tab]").forEach((tab) => tab.classList.toggle("is-on", tab.dataset.tab === state.tab));
  $("[data-view=calendar]").hidden = state.tab !== "calendar";
  $("[data-view=reports]").hidden = state.tab !== "reports";
  if (state.tab === "reports") {
    await loadReport();
  }
}

function tabShortcutAllowed() {
  if (state.busy || !state.workspaceId) {
    return false;
  }

  return $("[data-view=settings]").hidden && $("[data-view=metadata]").hidden;
}

function calendarShortcutAllowed(event) {
  if (!cardShortcutAllowed()) {
    return false;
  }
  const tag = event.target.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || event.target.isContentEditable) {
    return false;
  }

  return true;
}

function periodBounds(period, iso) {
  const date = parseIso(iso);
  if (period === "month") {
    const start = isoDate(new Date(date.getFullYear(), date.getMonth(), 1));
    const end = isoDate(new Date(date.getFullYear(), date.getMonth() + 1, 0));

    return [start, end];
  }
  const weekday = (date.getDay() + 6) % 7;
  const startDate = new Date(date);
  startDate.setDate(date.getDate() - weekday);
  const endDate = new Date(startDate);
  endDate.setDate(startDate.getDate() + 6);

  return [isoDate(startDate), isoDate(endDate)];
}

function shiftPeriodAnchor(delta) {
  const date = parseIso(state.date);
  if (state.period === "month") {
    date.setDate(1);
    date.setMonth(date.getMonth() + delta);
  } else {
    date.setDate(date.getDate() + delta * 7);
  }
  state.date = isoDate(date);
  state.calYear = date.getFullYear();
  state.calMonth = date.getMonth();
}

function reportContainsToday(fromIso, toIso) {
  const today = isoDate(new Date());

  return today >= fromIso && today <= toIso;
}

async function pushResults(title, path, button) {
  setBusy(true, button);
  try {
    await ensureSaved();
    const body = await api(path, {method: "POST"});
    const items = (body.results || []).map((row) => ({
      ok: row.status === "synced" || row.status === "skipped",
      text: row.status === "skipped"
        ? `#${row.id} already synced`
        : (row.status === "synced" ? `#${row.id} pushed` : `#${row.id} ${row.last_error || "error"}`),
    }));
    showToast(title, items.length ? items : [{ok: true, text: "Nothing to push"}]);
    await loadDay();
    await loadMonth();
  } finally {
    setBusy(false);
  }
}

async function loadReport() {
  if (!state.workspaceId) {
    return;
  }
  const body = await api(`/api/workspace/${state.workspaceId}/reports?period=${state.period}&date=${state.date}`);
  const start = parseIso(body.from);
  const end = parseIso(body.to);
  $("[data-field=period-label]").textContent = periodLabel(state.period, body.from, body.to);
  $("[data-field=report-today-jump]").hidden = reportContainsToday(body.from, body.to);
  $("[data-field=rep-total]").textContent = formatDuration(body.total_minutes);
  $("[data-field=rep-tasks]").textContent = String(body.task_count);
  $("[data-field=rep-days]").textContent = String(body.days_with_work);
  const empty = body.task_count === 0;
  $("[data-field=empty-report]").hidden = !empty;
  $("[data-field=report-table]").hidden = empty;
  $("[data-field=report-rows]").innerHTML = (body.tasks || []).map((task) => {
    const pct = Math.round((task.share || 0) * 100);
    const span = task.first_date === task.last_date
      ? formatShort(task.first_date)
      : `${formatShort(task.first_date)} – ${formatShort(task.last_date)}`;

    return `<div class="t-row">
      <span class="key">${escapeHtml(task.issue_key)}</span>
      <span class="time">${formatDuration(task.total_minutes)}</span>
      <span class="muted">${task.days}</span>
      <span class="muted">${span}</span>
      <div class="share"><span>${pct}%</span><span class="bar"><i style="width:${pct}%"></i></span></div>
    </div>`;
  }).join("");
}

function periodLabel(period, fromIso, toIso) {
  const start = parseIso(fromIso);
  const end = parseIso(toIso);
  if (period === "month") {
    return `${MONTHS[start.getMonth()]} ${start.getFullYear()}`;
  }
  const sameMonth = start.getMonth() === end.getMonth() && start.getFullYear() === end.getFullYear();
  if (sameMonth) {
    return `${start.getDate()}–${end.getDate()} ${MONTHS[end.getMonth()]} ${end.getFullYear()}`;
  }

  return `${formatShort(fromIso)} – ${formatShort(toIso)} ${end.getFullYear()}`;
}

function formatShort(iso) {
  const date = parseIso(iso);

  return `${date.getDate()} ${MONTHS[date.getMonth()].slice(0, 3)}`;
}

function openSettings(mode) {
  $("[data-view=metadata]").hidden = true;
  const form = $("[data-form=workspace]");
  form.dataset.mode = mode;
  $("[data-field=sheet-title]").textContent = mode === "create" ? "New workspace" : "Workspace settings";
  $("[data-field=sheet-action]").textContent = mode === "create" ? "Probe & create" : "Probe & save";
  $("[data-action=delete-workspace]").hidden = mode === "create";
  if (mode === "create") {
    form.reset();
    form.jira_base_url.value = "https://";
    form.timezone.value = "Europe/Kyiv";
  } else {
    const workspace = currentWorkspace();
    if (!workspace) {
      return;
    }
    form.name.value = workspace.name;
    form.jira_base_url.value = workspace.jira_base_url;
    form.jira_email.value = workspace.jira_email;
    form.timezone.value = workspace.timezone;
    form.jira_api_token.value = "";
  }
  $("[data-view=settings]").hidden = false;
}

async function deleteCurrentWorkspace() {
  if (!state.workspaceId) {
    return;
  }
  const workspace = currentWorkspace();
  const name = workspace ? workspace.name : "this workspace";
  if (!window.confirm(`Delete ${name} and all its lines? This cannot be undone.`)) {
    return;
  }
  const id = state.workspaceId;
  await api(`/api/workspace/${id}`, {method: "DELETE"});
  $("[data-view=settings]").hidden = true;
  state.workspaces = state.workspaces.filter((item) => item.id !== id);
  markDirty(false);
  if (Number(localStorage.getItem("tsyncer.workspace") || 0) === id) {
    localStorage.removeItem("tsyncer.workspace");
  }
  const next = state.workspaces[0];
  if (next) {
    state.workspaceId = next.id;
    localStorage.setItem("tsyncer.workspace", String(state.workspaceId));
  } else {
    state.workspaceId = null;
  }
  renderWorkspaces();
  await loadMonth();
  await loadDay();
  if (state.tab === "reports") {
    await loadReport();
  }
}

async function switchWorkspace(id) {
  await ensureSaved();
  state.workspaceId = Number(id);
  localStorage.setItem("tsyncer.workspace", String(state.workspaceId));
  renderWorkspaces();
  await loadMonth();
  await loadDay();
  if (state.tab === "reports") {
    await loadReport();
  }
}

document.addEventListener("click", async (event) => {
  if (state.busy) {
    event.preventDefault();
    return;
  }
  if (event.target.matches("[data-view=metadata]")) {
    event.target.hidden = true;
    return;
  }
  const actionNode = event.target.closest("[data-action], [data-tab], [data-period]");
  if (!actionNode) {
    if (!event.target.closest(".menu")) {
      closeMenus();
    }
    return;
  }
  const action = actionNode.dataset.action;
  const row = event.target.closest(".row");
  const line = row ? findLine(row.dataset.id) : null;
  try {
    if (actionNode.dataset.tab) {
      await showTab(actionNode.dataset.tab);
      return;
    }
    if (actionNode.dataset.period) {
      state.period = actionNode.dataset.period;
      $all("[data-period]").forEach((tab) => tab.classList.toggle("is-on", tab.dataset.period === state.period));
      await loadReport();
      return;
    }
    if (action === "prev-period") {
      shiftPeriodAnchor(-1);
      await loadReport();
      await loadMonth();
    } else if (action === "next-period") {
      shiftPeriodAnchor(1);
      await loadReport();
      await loadMonth();
    } else if (action === "report-today") {
      state.date = isoDate(new Date());
      const today = parseIso(state.date);
      state.calYear = today.getFullYear();
      state.calMonth = today.getMonth();
      await loadReport();
      await loadMonth();
    } else if (action === "toggle-sidebar") {
      $(".sidebar").classList.toggle("is-hidden");
    } else if (action === "open-settings") {
      openSettings("edit");
    } else if (action === "close-settings") {
      $("[data-view=settings]").hidden = true;
    } else if (action === "close-metadata") {
      $("[data-view=metadata]").hidden = true;
    } else if (action === "delete-workspace") {
      await deleteCurrentWorkspace();
    } else if (action === "prev-month") {
      const next = new Date(state.calYear, state.calMonth - 1, 1);
      state.calYear = next.getFullYear();
      state.calMonth = next.getMonth();
      await loadMonth();
    } else if (action === "next-month") {
      const next = new Date(state.calYear, state.calMonth + 1, 1);
      state.calYear = next.getFullYear();
      state.calMonth = next.getMonth();
      await loadMonth();
    } else if (action === "pick-day") {
      await ensureSaved();
      state.date = actionNode.dataset.date;
      const picked = parseIso(state.date);
      state.calYear = picked.getFullYear();
      state.calMonth = picked.getMonth();
      await loadMonth();
      await loadDay();
    } else if (action === "prev-day") {
      await moveCalendarDay(-1);
    } else if (action === "next-day") {
      await moveCalendarDay(1);
    } else if (action === "today") {
      await ensureSaved();
      state.date = isoDate(new Date());
      const today = parseIso(state.date);
      state.calYear = today.getFullYear();
      state.calMonth = today.getMonth();
      await loadMonth();
      await loadDay();
    } else if (action === "add-line") {
      const line = newLine();
      state.lines.push(line);
      refreshDirty();
      renderDay();
      focusLineIssue(line.id);
    } else if (action === "save-card") {
      if (!state.dirty) {
        return;
      }
      setBusy(true, actionNode);
      try {
        await saveCard();
      } finally {
        setBusy(false);
      }
    } else if (action === "sync-card") {
      if (state.dirty || state.lines.every((line) => line.status === "synced")) {
        return;
      }
      await pushResults("Sync card", `/api/workspace/${state.workspaceId}/days/${state.date}/push`, actionNode);
    } else if (action === "push-week") {
      const [from, to] = periodBounds("week", state.date);
      await pushResults("Push week", `/api/workspace/${state.workspaceId}/push?from=${from}&to=${to}`, actionNode);
    } else if (action === "push-month") {
      const [from, to] = periodBounds("month", state.date);
      await pushResults("Push month", `/api/workspace/${state.workspaceId}/push?from=${from}&to=${to}`, actionNode);
    } else if (action === "duplicate" && line) {
      state.lines.push(newLine({issue_key: line.issue_key, tag: line.tag, message: line.message}));
      refreshDirty();
      renderDay();
    } else if (action === "get-metadata" && line) {
      closeMenus();
      await ensureSaved();
      if (line.local) {
        return;
      }
      const body = await api(`/api/workspace/${state.workspaceId}/worklogs/${line.id}`);
      $("[data-field=metadata-json]").textContent = JSON.stringify(body, null, 2);
      $("[data-view=metadata]").hidden = false;
    } else if (action === "push-line" && line) {
      setBusy(true, actionNode);
      try {
        await ensureSaved();
        if (line.local) {
          return;
        }
        const result = await api(`/api/workspace/${state.workspaceId}/worklogs/${line.id}/push`, {method: "POST"});
        showToast("Push worklog", [{
          ok: result.status === "synced" || result.skipped,
          text: result.skipped
            ? `#${result.id} already synced`
            : (result.status === "synced" ? `#${result.id} pushed` : `#${result.id} ${result.last_error || "error"}`),
        }]);
        await loadDay();
        await loadMonth();
      } finally {
        setBusy(false);
      }
    } else if (action === "more") {
      const menu = row.querySelector(".menu");
      const open = menu.hidden;
      closeMenus();
      menu.hidden = !open;
    } else if (action === "delete-line" && line && line.status !== "synced") {
      const wasLocal = line.local;
      if (!wasLocal) {
        await api(`/api/workspace/${state.workspaceId}/worklogs/${line.id}`, {method: "DELETE"});
      }
      state.lines = state.lines.filter((item) => item.id !== line.id);
      if (!wasLocal) {
        rememberSavedCard();
      }
      refreshDirty();
      renderDay();
      await loadMonth();
    } else if (action === "delete-in-jira" && line) {
      state.deleteInJiraAttempted.add(String(line.id));
      try {
        const result = await api(`/api/workspace/${state.workspaceId}/worklogs/${line.id}/delete-in-jira`, {method: "POST"});
        state.deleteInJiraAttempted.delete(String(line.id));
        showToast("Delete in Jira", [{ok: true, text: `#${result.id} is a draft again`}]);
        await loadDay();
        await loadMonth();
      } catch (error) {
        showToast("Error", [{ok: false, text: error.message}]);
        renderDay();
        closeMenus();
      }
    } else if (action === "reset-to-draft" && line) {
      if (line.status === "synced" && !state.deleteInJiraAttempted.has(String(line.id))) {
        return;
      }
      await api(`/api/workspace/${state.workspaceId}/worklogs/${line.id}/reset-to-draft`, {method: "POST"});
      state.deleteInJiraAttempted.delete(String(line.id));
      await loadDay();
    } else if (action === "dismiss-toast") {
      dismissToast();
    }
  } catch (error) {
    showToast("Error", [{ok: false, text: error.message}]);
  }
});

$("[data-field=workspace]").addEventListener("change", async (event) => {
  const value = event.target.value;
  if (value === NEW_WORKSPACE_VALUE) {
    renderWorkspaces();
    openSettings("create");

    return;
  }
  if (!value) {
    return;
  }
  await switchWorkspace(value);
});

$("[data-form=workspace]").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.target;
  const payload = {
    name: form.name.value,
    jira_base_url: form.jira_base_url.value,
    jira_email: form.jira_email.value,
    jira_api_token: form.jira_api_token.value,
    timezone: form.timezone.value,
  };
  try {
    if (form.dataset.mode === "create") {
      const created = await api("/api/workspace", {method: "POST", body: JSON.stringify(payload)});
      state.workspaces.push(created);
      $("[data-view=settings]").hidden = true;
      await switchWorkspace(created.id);
    } else {
      const updated = await api(`/api/workspace/${state.workspaceId}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
      state.workspaces = state.workspaces.map((item) => item.id === updated.id ? updated : item);
      $("[data-view=settings]").hidden = true;
      renderWorkspaces();
    }
  } catch (error) {
    showToast("Workspace", [{ok: false, text: error.message}]);
  }
});

async function boot() {
  try {
    await loadWorkspaces();
    await loadMonth();
    await loadDay();
  } catch (error) {
    showToast("Error", [{ok: false, text: error.message}]);
  }
}

window.addEventListener("beforeunload", (event) => {
  if (state.dirty) {
    event.preventDefault();
    event.returnValue = "";
  }
});

window.addEventListener("keydown", async (event) => {
  if (!event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) {
    return;
  }
  if (!calendarShortcutAllowed(event)) {
    return;
  }
  const moves = {
    ArrowLeft: -1,
    ArrowRight: 1,
    ArrowUp: -7,
    ArrowDown: 7,
  };
  const delta = moves[event.code];
  if (delta === undefined) {
    return;
  }
  event.preventDefault();
  try {
    await moveCalendarDay(delta);
  } catch (error) {
    showToast("Error", [{ok: false, text: error.message}]);
  }
}, true);

// Ctrl+S and Ctrl+I fire the buttons themselves, so a disabled Save card stays
// a no-op. Deliberately allowed while a line field has focus: you type, then
// save. Cmd is accepted too -- on a Mac that is the reflex.
const CARD_SHORTCUTS = {s: "save-card", i: "add-line"};

window.addEventListener("keydown", (event) => {
  if (!(event.ctrlKey || event.metaKey) || event.altKey || event.shiftKey) {
    return;
  }
  const action = CARD_SHORTCUTS[event.key.toLowerCase()];
  if (!action || !cardShortcutAllowed()) {
    return;
  }
  // Even when the button is disabled: never let the browser Save Page instead.
  event.preventDefault();
  $(`[data-action=${action}]`).click();
});

// Ctrl+Cmd+Left / Ctrl+Cmd+Right walk the tabs. The ring wraps, so with two
// tabs either arrow reaches the other one from wherever you are. Both modifiers
// are required: Ctrl+Arrow alone is a Mac Spaces gesture, Cmd+Arrow is browser
// history, and Alt+Arrow already moves the calendar day.
const TAB_STEPS = {ArrowLeft: -1, ArrowRight: 1};

window.addEventListener("keydown", async (event) => {
  if (!(event.ctrlKey && event.metaKey) || event.altKey || event.shiftKey) {
    return;
  }
  const step = TAB_STEPS[event.code];
  if (step === undefined || !tabShortcutAllowed()) {
    return;
  }
  event.preventDefault();
  const next = (TABS.indexOf(state.tab) + step + TABS.length) % TABS.length;
  try {
    await showTab(TABS[next]);
  } catch (error) {
    showToast("Error", [{ok: false, text: error.message}]);
  }
});

boot();
