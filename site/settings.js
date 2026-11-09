// Travel Radar settings panel. Edits config/cities.yaml, scoring.yaml and days_off.yaml on main through the GitHub
// Contents API with a fine-grained token William pastes once (kept in localStorage only, never logged, never shown again).
// The files are changed by targeted text edits so their comments and key order survive; js-yaml (pinned in index.html)
// parses them and reads every edit back before it is sent. Uses el, icon, $, money, dayOf, todayISO, wireDialog and
// store from app.js. Nothing here runs until the gear button is tapped.
"use strict";

const REPO = "WilliamEbong/spontaneous-travel-radar";
const API = "https://api.github.com/repos/" + REPO;
const TOKEN_KEY = "radar.githubToken";
const TOKEN_URL = "https://github.com/settings/personal-access-tokens/new";
const NEXT_SCAN = "Applies at the next scan, 04:17 Calgary.";
const BAR = { min: 200, max: 5000, step: 50 };
const CONFIG = ["cities.yaml", "scoring.yaml", "days_off.yaml", "holidays.yaml"];
const DAYS_HEADER = "# Written by the dashboard's Settings panel (the Days off calendar); edit by hand if you prefer.\n"
  + "# extra: vacation days, treated like stat holidays (they create or extend long-weekend windows).\n"
  + "# blocked: no trip may touch these dates. Dates are YYYY-MM-DD. A date cannot be in both lists.\n";
const MODE_HINT = {
  "dry-run": "Learning run: trips that would have fired are logged on the page and nobody is alerted.",
  live: "Live: a trip that passes all three gates is written as a real hit, which the alert routine can email you.",
};

// Panel state. It lives as long as the page does, so closing the panel never loses an unsaved edit.
const S = { cities: [], days: { extra: new Set(), blocked: new Set() }, alerts: {}, stats: new Set(), base: null, loading: false, saving: false, flash: null };
const token = () => store.get(TOKEN_KEY);

// ---- GitHub ----
async function gh(path, init = {}) {
  const headers = { Accept: "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28" };
  if (token()) headers.Authorization = "Bearer " + token();
  try {
    return await fetch(API + path, { ...init, headers, cache: "no-store" });
  } catch {
    throw new Error("Could not reach GitHub. Check the connection and try again.");
  }
}
function explain(status, doing) {
  if (status === 401) return "GitHub rejected the token. Disconnect and paste a new one.";
  if (status === 403) return `GitHub refused to ${doing} (403): the token lacks that permission, or the hourly API limit is used up.`;
  if (status === 404) return `GitHub could not find what it needs to ${doing} (404). A token with no access to this repository looks the same.`;
  return `GitHub answered ${status} while trying to ${doing}.`;
}
const fromB64 = (s) => new TextDecoder().decode(Uint8Array.from(atob(s.replace(/\s/g, "")), (c) => c.charCodeAt(0)));
function toB64(text) {
  let bin = "";
  for (const b of new TextEncoder().encode(text)) bin += String.fromCharCode(b);
  return btoa(bin);
}
const parse = (text) => jsyaml.load(text, { schema: jsyaml.CORE_SCHEMA }) || {};   // CORE: dates stay strings

async function getFile(name) {
  const r = await gh(`/contents/config/${name}?ref=main`);
  if (r.status === 404 && name === "days_off.yaml") return { sha: null, text: "" };   // not created yet: the first save creates it
  if (!r.ok) throw new Error(explain(r.status, `read config/${name}`));
  const j = await r.json();
  return { sha: j.sha, text: fromB64(j.content) };
}
function putFile(name, text, sha) {
  const body = { message: "chore: settings from dashboard", content: toB64(text), branch: "main" };
  if (sha) body.sha = sha;
  return gh(`/contents/config/${name}`, { method: "PUT", body: JSON.stringify(body) });
}
async function verifyToken() {
  const r = await gh("");
  if (!r.ok) throw new Error(explain(r.status, "reach the repository"));
}

async function loadConfig() {
  const [cities, scoring, days, holidays] = await Promise.all(CONFIG.map(getFile));
  const c = parse(cities.text), s = parse(scoring.text), d = parse(days.text), h = parse(holidays.text);
  if (!Array.isArray(c.cities) || !c.cities.length) throw new Error("config/cities.yaml on GitHub has no cities list.");
  S.cities = c.cities.map((x) => ({ key: String(x.key), name: String(x.name), airports: (x.airports || []).join(" · "), enabled: x.enabled !== false, bar: Number(x.bar_cad) }));
  S.days = { extra: new Set((d.extra || []).map(String)), blocked: new Set((d.blocked || []).map(String)) };
  S.alerts = { mode: String(s.mode), threshold: Number(s.score_threshold), drop: Number(s.realert_drop_pct),
    weeks: Number(s.dayoff_min_weeks), weekend: s.weekend_trips === true };
  S.stats = new Set((h[h.calendar] || []).map(String));
  S.base = snapshot();
}
function snapshot() {
  return { cities: S.cities.map((c) => ({ key: c.key, enabled: c.enabled, bar: c.bar })), extra: [...S.days.extra].sort(), blocked: [...S.days.blocked].sort(), alerts: { ...S.alerts } };
}

// ---- what changed since the load (per file, and a count for the status line) ----
function diff() {
  const b = S.base, out = { cities: false, order: false, scoring: false, days: false, n: 0 };
  if (!b) return out;
  const was = Object.fromEntries(b.cities.map((c) => [c.key, c]));
  out.order = S.cities.map((c) => c.key).join() !== b.cities.map((c) => c.key).join();
  out.n += out.order ? 1 : 0;
  for (const c of S.cities) {
    const w = was[c.key];
    if (!w) continue;
    const k = (w.enabled !== c.enabled ? 1 : 0) + (w.bar !== c.bar ? 1 : 0);
    if (k) { out.cities = true; out.n += k; }
  }
  out.cities = out.cities || out.order;
  for (const k of ["extra", "blocked"]) {
    const changed = [...S.days[k]].filter((x) => !b[k].includes(x)).length + b[k].filter((x) => !S.days[k].has(x)).length;
    if (changed) { out.days = true; out.n += changed; }
  }
  for (const k in S.alerts) if (S.alerts[k] !== b.alerts[k]) { out.scoring = true; out.n++; }
  return out;
}

function validate() {
  if (!S.cities.some((c) => c.enabled)) return "Keep at least one city on.";
  for (const c of S.cities) {
    if (!Number.isInteger(c.bar) || c.bar < BAR.min || c.bar > BAR.max || c.bar % BAR.step) return `${c.name}: the bar must be a multiple of $${BAR.step} between $${BAR.min} and $${BAR.max}.`;
  }
  const a = S.alerts;
  if (a.mode !== "dry-run" && a.mode !== "live") return "Mode must be learning run or live.";
  if (!Number.isInteger(a.threshold) || a.threshold < 0 || a.threshold > 100) return "The score threshold must be a whole number from 0 to 100.";
  if (!Number.isInteger(a.drop) || a.drop < 0 || a.drop > 100) return "The re-alert drop must be a whole number from 0 to 100.";
  if (!Number.isInteger(a.weeks) || a.weeks < 2 || a.weeks > 12) return "Day-off trips must start a whole number of weeks out, from 2 to 12.";
  if (typeof a.weekend !== "boolean") return "Weekend trips must be on or off.";
  for (const k of ["extra", "blocked"]) {
    for (const d of S.days[k]) {
      const t = Date.parse(d + "T12:00:00Z");
      if (!/^\d{4}-\d{2}-\d{2}$/.test(d) || Number.isNaN(t) || new Date(t).toISOString().slice(0, 10) !== d) return `${d} is not a real date.`;
    }
  }
  for (const d of S.days.extra) if (S.days.blocked.has(d)) return `${dayOf(d)} cannot be both an extra day off and blocked.`;
  return null;
}

// ---- file edits: only the lines that changed, then read back with js-yaml before anything is sent ----
// Edits run on LF text; a file that arrived with CRLF goes back with CRLF, so no line changes but the edited ones.
const lf = (text) => text.replace(/\r\n/g, "\n");
const sameEol = (orig, next) => (orig.includes("\r\n") ? next.replace(/\n/g, "\r\n") : next);
const setLine = (text, re, value, what) => {
  if (!re.test(text)) throw new Error(`${what}, so nothing was saved.`);
  return text.replace(re, (_, pre) => pre + value);
};

function editCities(orig) {
  const text = lf(orig);
  const was = Object.fromEntries(S.base.cities.map((c) => [c.key, c]));
  const parts = text.split(/^(?=  - key: )/m);
  const head = parts.shift();
  const blocks = new Map(parts.map((p) => [(p.match(/^  - key: (\S+)/) || [])[1], p.endsWith("\n") ? p : p + "\n"]));
  const reorder = diff().order;
  const order = reorder ? S.cities.map((c) => c.key) : [...blocks.keys()];
  const body = order.map((key) => {
    let p = blocks.get(key);
    if (!p) throw new Error(`config/cities.yaml on GitHub no longer has ${key}. Close and reopen Settings, then try again.`);
    blocks.delete(key);
    const c = S.cities.find((x) => x.key === key), w = was[key];
    if (!c || !w) return p;
    if (c.bar !== w.bar) p = setLine(p, /^(    bar_cad: )\S+/m, c.bar, `${key} has no bar_cad line in config/cities.yaml`);
    if (c.enabled !== w.enabled) {
      p = p.replace(/^    enabled: .*\n/m, "");                                  // on = the default, so no line at all
      if (!c.enabled) p = setLine(p, /^(    name: .*\n)/m, "    enabled: false\n", `${key} has no name line in config/cities.yaml`);
    }
    return p;
  });
  const next = head + body.join("") + [...blocks.values()].join("");          // a city added on GitHub meanwhile keeps its place, at the end
  const got = parse(next).cities || [];
  for (const c of S.cities) {
    const g = got.find((x) => x.key === c.key), w = was[c.key];
    if (!g || !w) throw new Error("The change to config/cities.yaml did not read back as intended, so nothing was saved.");
    if ((c.bar !== w.bar && g.bar_cad !== c.bar) || (c.enabled !== w.enabled && (g.enabled !== false) !== c.enabled)) {
      throw new Error("The change to config/cities.yaml did not read back as intended, so nothing was saved.");
    }
  }
  if (reorder && got.slice(0, S.cities.length).map((x) => x.key).join() !== S.cities.map((c) => c.key).join()) {
    throw new Error("The new city order did not read back as intended, so nothing was saved.");
  }
  return sameEol(orig, next);
}

function editScoring(orig) {
  const keys = { mode: "mode", threshold: "score_threshold", drop: "realert_drop_pct", weeks: "dayoff_min_weeks", weekend: "weekend_trips" };
  let next = lf(orig);
  for (const [k, yk] of Object.entries(keys)) {
    if (S.alerts[k] === S.base.alerts[k]) continue;                              // untouched here: keep whatever the daily routine wrote
    next = setLine(next, new RegExp(`^(${yk}:[ \\t]*)\\S+`, "m"), S.alerts[k], `config/scoring.yaml has no ${yk} line`);
  }
  const p = parse(next);
  for (const [k, yk] of Object.entries(keys)) {
    if (S.alerts[k] !== S.base.alerts[k] && p[yk] !== S.alerts[k]) throw new Error("The change to config/scoring.yaml did not read back as intended, so nothing was saved.");
  }
  return sameEol(orig, next);
}

function editDays() {
  const list = (s) => `[${[...s].sort().join(", ")}]`;
  const next = `${DAYS_HEADER}extra: ${list(S.days.extra)}\nblocked: ${list(S.days.blocked)}\n`;
  const p = parse(next);
  const same = (set, arr) => [...set].sort().join() === (arr || []).map(String).join();
  if (!same(S.days.extra, p.extra) || !same(S.days.blocked, p.blocked)) throw new Error("config/days_off.yaml did not read back as intended, so nothing was saved.");
  return next;
}

async function save() {
  if (S.saving || !S.base) return;
  const problem = validate();
  if (problem) return setStatus(problem, "bad");
  const d = diff(), jobs = [];
  if (d.cities) jobs.push(["cities.yaml", editCities]);
  if (d.scoring) jobs.push(["scoring.yaml", editScoring]);
  if (d.days) jobs.push(["days_off.yaml", editDays]);
  if (!jobs.length) return;
  S.saving = true;
  $("save-btn").disabled = true;
  setStatus("Saving…");
  try {
    for (const [name, edit] of jobs) {
      for (let attempt = 0; ; attempt++) {
        const cur = await getFile(name);                                        // the current sha, seconds before the write
        const next = edit(cur.text);
        if (next === cur.text) break;                                           // GitHub already has it
        const r = await putFile(name, next, cur.sha);
        if (r.ok) break;
        if ((r.status === 409 || r.status === 422) && attempt === 0) continue;   // someone (the daily routine) committed in between: re-read, re-apply once
        throw new Error(explain(r.status, `write config/${name}`));
      }
    }
    await loadConfig();                                                         // confirm from GitHub, not from memory
    S.flash = { text: "Saved. " + NEXT_SCAN, kind: "ok" };
    render();
  } catch (e) {
    S.flash = { text: e.message, kind: "bad" };
  } finally {
    S.saving = false;
    refreshFoot();
  }
}

// ---- rendering ----
function setStatus(text, kind) {
  const p = $("save-status");
  p.textContent = text || "";
  p.className = "save-status" + (kind ? " " + kind : "");
}
function refreshFoot() {
  const d = diff(), problem = S.base ? validate() : null;
  let text = "", kind = null, ready = false;
  const pending = `${d.n} unsaved change${d.n === 1 ? "" : "s"}.`;
  if (!S.base) text = "";
  else if (!token()) text = d.n ? `${pending} Connect GitHub to save.` : "Connect GitHub to save.";
  else if (problem) { text = problem; kind = "bad"; }
  else if (!d.n) text = "No changes.";
  else { text = pending; ready = true; }
  if (S.flash) { text = S.flash.text; kind = S.flash.kind; }
  $("save-btn").disabled = !ready || S.saving;
  setStatus(text, kind);
}
function touched() { S.flash = null; refreshFoot(); }

function notice(text, retry) {
  const n = el("div", { class: "notice bad" }, icon("i-warn"), el("p", { text }));
  if (retry) {
    const b = el("button", { class: "btn", type: "button", text: "Try again" });
    b.addEventListener("click", retry);
    n.append(b);
  }
  return n;
}

function render() {
  $("settings-body").replaceChildren(connectSection(), citiesSection(), daysSection(), tripsSection(), alertsSection(), scanSection());
  refreshFoot();
}

function connectSection() {
  const sec = el("section", { class: "pset", "aria-labelledby": "s-gh" });
  sec.append(el("h3", { id: "s-gh", text: "GitHub" }));
  if (token()) {
    const off = el("button", { class: "btn quiet", type: "button", text: "Disconnect" });
    off.addEventListener("click", () => { store.set(TOKEN_KEY, null); render(); });
    sec.append(el("p", { class: "hint", text: "Saving commits the config files to the repository as you." }),
      el("div", { class: "connected" }, icon("i-check"), el("span", { text: "Connected. The token stays in this browser only." }), off));
    return sec;
  }
  sec.append(el("p", { class: "hint", text: "Everything below is live to look at. To save, paste a GitHub token that can write to this one repository. It stays in this browser only, is never shown again, and goes nowhere but GitHub." }));
  const input = el("input", { type: "password", id: "gh-token", autocomplete: "off", autocapitalize: "off", spellcheck: "false", placeholder: "github_pat_…", "aria-label": "GitHub token" });
  const btn = el("button", { class: "btn", type: "button", text: "Connect" });
  const go = async () => {
    const t = input.value.trim();
    if (!t) { input.focus(); return; }
    btn.disabled = true;
    btn.textContent = "Checking…";
    input.value = "";
    store.set(TOKEN_KEY, t);
    try {
      await verifyToken();
      S.flash = null;
      render();
    } catch (e) {
      store.set(TOKEN_KEY, null);
      render();
      setStatus(e.message, "bad");
    }
  };
  btn.addEventListener("click", go);
  input.addEventListener("keydown", (e) => { if (e.key === "Enter") go(); });
  const li = (...kids) => el("li", {}, ...kids);
  sec.append(el("div", { class: "connect" }, input, btn),
    el("details", { class: "steps" }, el("summary", { text: "How to create the token (about two minutes)" }),
      el("ol", {},
        li("Open ", el("a", { href: TOKEN_URL, target: "_blank", rel: "noopener", text: "github.com/settings/personal-access-tokens/new" }), ". This makes a fine-grained token."),
        li(el("b", { text: "Token name: " }), "Radar dashboard. ", el("b", { text: "Expiration: " }), "as long as you like; you paste a new one when it runs out."),
        li(el("b", { text: "Repository access: " }), "Only select repositories, then pick spontaneous-travel-radar."),
        li(el("b", { text: "Permissions, Repository permissions, Contents: " }), "Read and write. Optional: Actions: Read and write, which makes “Run scan now” work. Leave everything else at No access."),
        li("Generate token, copy it, paste it above and tap Connect."))));
  return sec;
}

function citiesSection() {
  const sec = el("section", { class: "pset", "aria-labelledby": "s-cities" });
  sec.append(el("div", { class: "pset-head" }, el("h3", { id: "s-cities", text: "Cities" }), el("span", { class: "count", id: "city-count" })),
    el("p", { class: "hint", text: "Off skips the city and saves the scan's request budget. Drag a row, or use the arrows, to set the order “Mine” uses on the page. The bar is the all-in price for two that a complete trip must beat to alert." }));
  const list = el("ul", { class: "crows", id: "crows" });
  fillRows(list);
  wireDrag(list);
  sec.append(list);
  sec.querySelector("#city-count").textContent = countText();
  return sec;
}
const countText = () => `${S.cities.filter((c) => c.enabled).length} of ${S.cities.length} on`;
function fillRows(list) {
  list.replaceChildren(...S.cities.map((c, i) => cityRow(c, i)));
  if ($("city-count")) $("city-count").textContent = countText();
}
function cityRow(c, i) {
  const row = el("li", { class: "crow" + (c.enabled ? "" : " off"), draggable: "true", "data-key": c.key });
  const cb = el("input", { type: "checkbox", role: "switch", checked: c.enabled ? "" : null });
  cb.addEventListener("change", () => {
    c.enabled = cb.checked;
    row.classList.toggle("off", !c.enabled);
    $("city-count").textContent = countText();
    touched();
  });
  const sw = el("label", { class: "switch" }, cb, el("span", { class: "track", "aria-hidden": "true" }), el("span", { class: "sr", text: `${c.name} on` }));
  const out = el("output", { text: money(c.bar) });
  const minus = el("button", { class: "icon-btn sm", type: "button", "aria-label": `Lower ${c.name}'s bar by $${BAR.step}` }, icon("i-minus"));
  const plus = el("button", { class: "icon-btn sm", type: "button", "aria-label": `Raise ${c.name}'s bar by $${BAR.step}` }, icon("i-plus"));
  const step = (d) => {
    c.bar = Math.min(BAR.max, Math.max(BAR.min, c.bar + d));
    out.textContent = money(c.bar);
    minus.disabled = c.bar <= BAR.min;
    plus.disabled = c.bar >= BAR.max;
    touched();
  };
  minus.addEventListener("click", () => step(-BAR.step));
  plus.addEventListener("click", () => step(BAR.step));
  minus.disabled = c.bar <= BAR.min;
  plus.disabled = c.bar >= BAR.max;
  const up = el("button", { class: "icon-btn sm up", type: "button", "aria-label": `Move ${c.name} up`, disabled: i === 0 ? "" : null }, icon("i-chev"));
  const down = el("button", { class: "icon-btn sm down", type: "button", "aria-label": `Move ${c.name} down`, disabled: i === S.cities.length - 1 ? "" : null }, icon("i-chev"));
  up.addEventListener("click", () => move(c.key, i - 1, "up"));
  down.addEventListener("click", () => move(c.key, i + 1, "down"));
  row.append(el("span", { class: "grip", "aria-hidden": "true" }, icon("i-grip")),
    el("div", { class: "cname" }, el("b", { text: c.name }), el("span", { text: c.airports })),
    sw,
    el("div", { class: "stepper bar", role: "group", "aria-label": `${c.name} bar` }, el("span", { class: "lbl", text: "Bar" }), minus, out, plus),
    el("div", { class: "move" }, up, down));
  return row;
}
function move(key, to, dir) {
  const from = S.cities.findIndex((c) => c.key === key);
  if (from < 0 || to < 0 || to >= S.cities.length || from === to) return;
  const [c] = S.cities.splice(from, 1);
  S.cities.splice(to, 0, c);
  const list = $("crows");
  fillRows(list);
  const row = list.querySelector(`[data-key="${key}"]`);
  const btn = row.querySelector("." + dir);
  (btn.disabled ? row.querySelector(dir === "up" ? ".down" : ".up") : btn).focus();   // keep the keyboard on the row it moved
  touched();
}
// Mouse drag and drop (HTML5). Touch and keyboard use the arrows, which do the same thing.
function wireDrag(list) {
  let dragKey = null;
  const clear = () => list.querySelectorAll(".over-top, .over-bottom").forEach((n) => n.classList.remove("over-top", "over-bottom"));
  const half = (row, e) => e.clientY > row.getBoundingClientRect().top + row.offsetHeight / 2;
  list.addEventListener("dragstart", (e) => {
    const row = e.target.closest(".crow");
    if (!row) return;
    dragKey = row.dataset.key;
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", dragKey);
    row.classList.add("dragging");
  });
  list.addEventListener("dragover", (e) => {
    const row = e.target.closest(".crow");
    if (!row || !dragKey) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    clear();
    row.classList.add(half(row, e) ? "over-bottom" : "over-top");
  });
  list.addEventListener("dragleave", (e) => { if (!list.contains(e.relatedTarget)) clear(); });
  list.addEventListener("drop", (e) => {
    const row = e.target.closest(".crow");
    if (!row || !dragKey) return;
    e.preventDefault();
    const from = S.cities.findIndex((c) => c.key === dragKey);
    let to = S.cities.findIndex((c) => c.key === row.dataset.key) + (half(row, e) ? 1 : 0);
    if (from < to) to--;
    dragKey = null;
    clear();
    if (from !== to) {
      const [c] = S.cities.splice(from, 1);
      S.cities.splice(to, 0, c);
      fillRows(list);
      touched();
    }
  });
  list.addEventListener("dragend", () => { dragKey = null; clear(); list.querySelector(".dragging")?.classList.remove("dragging"); });
}

// ---- days off: three months, tap to cycle clear -> extra -> blocked -> clear (weekends and stats: clear -> blocked -> clear) ----
const iso = (y, m, d) => `${y}-${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
function daysSection() {
  const sec = el("section", { class: "pset", "aria-labelledby": "s-days" });
  const today = todayISO();
  const [y, m] = today.split("-").map(Number);
  const months = el("div", { class: "cal-wrap" });
  let last = today;
  for (let i = 0; i < 3; i++) {
    const first = new Date(Date.UTC(y, m - 1 + i, 1));
    const Y = first.getUTCFullYear(), M = first.getUTCMonth() + 1;
    const days = new Date(Date.UTC(Y, M, 0)).getUTCDate();
    const title = new Intl.DateTimeFormat("en-CA", { timeZone: "UTC", month: "long", year: "numeric" }).format(first);
    const grid = el("div", { class: "cal-grid" });
    for (const w of ["M", "T", "W", "T", "F", "S", "S"]) grid.append(el("span", { class: "cal-wd", "aria-hidden": "true", text: w }));
    for (let p = (first.getUTCDay() + 6) % 7; p > 0; p--) grid.append(el("span"));
    for (let d = 1; d <= days; d++) grid.append(dayCell(iso(Y, M, d), d, today));
    last = iso(Y, M, days);
    months.append(el("div", { class: "cal", role: "group", "aria-label": title }, el("h4", { text: title }), grid));
  }
  const leg = (cls, text) => el("span", {}, el("i", { class: cls }), text);
  sec.append(el("h3", { id: "s-days", text: "Days off" }),
    el("p", { class: "hint", text: "Tap a weekday once for an extra day off (it counts like a stat holiday and makes a long weekend), again to block it (no trips touching it), again to clear. Weekends and stat holidays only block." }),
    months,
    el("div", { class: "legend", "aria-hidden": "true" }, leg("l-extra", "Extra day off"), leg("l-blocked", "Blocked"), leg("l-stat", "Stat holiday")));
  const beyond = [...S.days.extra, ...S.days.blocked].filter((d) => d > last).length;
  if (beyond) sec.append(el("p", { class: "hint", text: `${beyond} more date${beyond === 1 ? " is" : "s are"} set after ${dayOf(last)}; they stay as they are.` }));
  return sec;
}
function dayCell(d, n, today) {
  const wd = new Date(d + "T12:00:00Z").getUTCDay();
  const weekend = wd === 0 || wd === 6, stat = S.stats.has(d), past = d < today;
  const b = el("button", { type: "button", class: "cal-day", "data-iso": d, disabled: past ? "" : null }, el("span", { class: "n", text: String(n) }));
  const paint = () => {
    const state = S.days.extra.has(d) ? "extra" : S.days.blocked.has(d) ? "blocked" : "";
    b.className = ["cal-day", weekend ? "wknd" : "", stat ? "stat" : "", d === today ? "today" : "", state].filter(Boolean).join(" ");
    b.setAttribute("aria-label", [dayOf(d, { weekday: "long", day: "numeric", month: "long" }), stat ? "stat holiday" : null,
      state === "extra" ? "extra day off" : state === "blocked" ? "blocked" : null].filter(Boolean).join(", "));
  };
  paint();
  if (!past) {
    b.addEventListener("click", () => {
      const { extra, blocked } = S.days;
      if (extra.has(d)) { extra.delete(d); blocked.add(d); }
      else if (blocked.has(d)) blocked.delete(d);
      else if (weekend || stat) blocked.add(d);          // an extra day off there would change nothing
      else extra.add(d);
      paint();
      touched();
    });
  }
  return b;
}

const WEEKEND_HINT = (on) => on
  ? "Weekend-only trips (leave Friday after 5:30 pm, home Sunday by 4 pm, non-stop, 3 hours or less) are scanned for the next 6 weeks. They need no day off, so they fire only when exceptional."
  : "Off: only trips that use a day off are scanned.";
function tripsSection() {
  const sec = el("section", { class: "pset", "aria-labelledby": "s-trips" });
  const cb = el("input", { type: "checkbox", role: "switch", "aria-labelledby": "weekend-l", checked: S.alerts.weekend ? "" : null });
  const hint = el("p", { class: "hint", text: WEEKEND_HINT(S.alerts.weekend) });
  cb.addEventListener("change", () => { S.alerts.weekend = cb.checked; hint.textContent = WEEKEND_HINT(cb.checked); touched(); });
  sec.append(el("h3", { id: "s-trips", text: "Trips" }),
    slider("weeks", "Day-off trips at least", 2, 12, " weeks", (v) => `Trips that need a day off start ${v} weeks out and run to ${Number(v) + 10} weeks, so you both have time to get it approved.`),
    el("div", { class: "field" },
      el("div", { class: "field-head" }, el("span", { class: "flabel", id: "weekend-l", text: "Weekend trips" }),
        el("label", { class: "switch" }, cb, el("span", { class: "track", "aria-hidden": "true" }))),
      hint));
  return sec;
}

function alertsSection() {
  const sec = el("section", { class: "pset", "aria-labelledby": "s-alerts" });
  const seg = el("fieldset", { class: "seg wide" }, el("legend", { class: "sr", text: "Mode" }));
  const modeHint = el("p", { class: "hint", text: MODE_HINT[S.alerts.mode] || "" });
  for (const [v, label] of [["dry-run", "Learning run"], ["live", "Live alerts"]]) {
    const inp = el("input", { type: "radio", name: "mode", value: v, checked: S.alerts.mode === v ? "" : null });
    inp.addEventListener("change", () => { S.alerts.mode = v; modeHint.textContent = MODE_HINT[v]; touched(); });
    seg.append(el("label", {}, inp, el("span", { text: label })));
  }
  sec.append(el("h3", { id: "s-alerts", text: "Alerts" }),
    el("div", { class: "field" }, el("div", { class: "field-head" }, el("span", { class: "flabel", id: "mode-l", text: "Mode" })), seg, modeHint),
    slider("threshold", "Score threshold", 0, 100, "", (v) => `A trip can alert only with a score of ${v} or more.`),
    slider("drop", "Re-alert drop", 0, 100, "%", (v) => `The same city and weekend alert again only if the fare drops another ${v}%.`));
  return sec;
}
function slider(key, label, min, max, unit, hint) {
  const id = "f-" + key;
  const out = el("output", { for: id, text: S.alerts[key] + unit });
  const inp = el("input", { type: "range", id, min, max, step: 1, value: S.alerts[key] });
  const h = el("p", { class: "hint", text: hint(S.alerts[key]) });
  inp.addEventListener("input", () => {
    S.alerts[key] = Number(inp.value);
    out.textContent = inp.value + unit;
    h.textContent = hint(inp.value);
    touched();
  });
  return el("div", { class: "field" }, el("div", { class: "field-head" }, el("label", { for: id, text: label }), out), inp, h);
}

function scanSection() {
  const sec = el("section", { class: "pset", "aria-labelledby": "s-scan" });
  sec.append(el("h3", { id: "s-scan", text: "Scan" }),
    el("p", { class: "hint", text: "The collector runs every day at 04:17 Calgary (10:17 UTC) and takes about an hour. Settings saved here apply from the next run." }));
  if (!token()) return sec;
  const label = el("span", { text: "Run scan now" });
  const btn = el("button", { class: "btn", type: "button" }, icon("i-play"), label);
  const note = el("p", { class: "hint", text: "Needs the token to have Actions: Read and write. A full scan is about 600 to 700 Google requests, so at most once a day." });
  let armed = 0;
  btn.addEventListener("click", async () => {
    if (!armed) {                                                              // two taps, so a stray tap cannot start an hour-long run
      label.textContent = "Tap again to start";
      armed = setTimeout(() => { armed = 0; label.textContent = "Run scan now"; }, 4000);
      return;
    }
    clearTimeout(armed);
    armed = 0;
    btn.disabled = true;
    label.textContent = "Starting…";
    note.className = "hint";
    try {
      const r = await gh("/actions/workflows/scan.yml/dispatches", { method: "POST", body: JSON.stringify({ ref: "main" }) });
      if (r.status !== 204) throw new Error(r.status === 403 || r.status === 404 ? "GitHub refused: the token needs Actions: Read and write on this repository." : explain(r.status, "start the scan"));
      note.textContent = "Scan started. It takes about an hour; the page shows the new scan when it lands.";
      note.className = "hint ok";
    } catch (e) {
      note.textContent = e.message;
      note.className = "hint bad";
    } finally {
      btn.disabled = false;
      label.textContent = "Run scan now";
    }
  });
  sec.append(btn, note);
  return sec;
}

// ---- open: load once per page life, show skeletons meanwhile ----
async function openSettings() {
  if (S.base || S.loading) return;
  const body = $("settings-body");
  if (typeof jsyaml === "undefined") {
    body.replaceChildren(notice("The settings panel needs the js-yaml library from cdnjs, which did not load. Check the connection and reload the page."));
    return;
  }
  S.loading = true;
  body.replaceChildren(...["70%", "100%", "90%", "40%", "100%", "60%"].map((w) => el("div", { class: "skel", style: `width:${w}` })));
  try {
    await loadConfig();
    render();
  } catch (e) {
    body.replaceChildren(notice(e.message, () => { S.base = null; openSettings(); }));
  } finally {
    S.loading = false;
  }
}

wireDialog($("settings"), $("settings-btn"), $("settings-close"), openSettings);
$("save-btn").addEventListener("click", save);
