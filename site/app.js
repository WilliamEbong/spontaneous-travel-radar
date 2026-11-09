// Travel Radar dashboard: vanilla JS, no build step. Reads the JSON the collector commits; all data text goes in via textContent.
"use strict";

const TZ = "America/Edmonton";
const STALE_HOURS = 30;
const PATTERN = { "fri-off": "Fri off", "mon-off": "Mon off", "stat-thu-4d": "Thu stat, 4 days", "stat-tue-4d": "Tue stat, 4 days" };
const BANDS = ["amazing", "good", "average", "bad"];

const $ = (id) => document.getElementById(id);
function el(tag, props = {}, ...kids) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (v == null) continue;
    if (k === "class") n.className = v;
    else if (k === "text") n.textContent = v;
    else n.setAttribute(k, v);
  }
  for (const k of kids) if (k != null) n.append(k);
  return n;
}
const svgEl = (tag, attrs = {}) => {
  const n = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  return n;
};
const icon = (name, cls = "ic") => {
  const s = svgEl("svg", { class: cls, "aria-hidden": "true" });
  s.append(svgEl("use", { href: `#${name}` }));
  return s;
};

async function getJSON(path) {
  try {
    const r = await fetch(path, { cache: "no-store" });
    return r.ok ? await r.json() : null;
  } catch { return null; }
}
async function getText(path) {
  try {
    const r = await fetch(path, { cache: "no-store" });
    return r.ok ? await r.text() : null;
  } catch { return null; }
}

// ---- formatting ----
const money = (n) => (n == null ? "–" : "$" + Math.round(n).toLocaleString("en-CA"));
const fmtTZ = (iso, opts) => new Intl.DateTimeFormat("en-GB", { timeZone: TZ, ...opts }).format(new Date(iso));
const when = (iso) => fmtTZ(iso, { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
// Leg times are stored as local wall time + offset; show that wall time as written (YYC legs = Calgary time),
// so an out-of-date browser zone database cannot shift them.
const wall = (iso) => new Intl.DateTimeFormat("en-GB", { timeZone: "UTC", weekday: "short", hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).format(new Date(iso.slice(0, 19) + "Z"));
const dayOf = (d, opts = { day: "numeric", month: "short" }) => new Intl.DateTimeFormat("en-GB", { timeZone: "UTC", ...opts }).format(new Date(d + "T12:00:00Z"));
function span(a, b) {
  const sameMonth = a.slice(0, 7) === b.slice(0, 7);
  return `${dayOf(a, sameMonth ? { weekday: "short", day: "numeric" } : { weekday: "short", day: "numeric", month: "short" })} – ${dayOf(b, { weekday: "short", day: "numeric", month: "short" })}`;
}
// The long weekend itself (days off), from the window id "<day 1>_<pattern>": a 3-day block, or 4 with a stat.
function windowLabel(r) {
  const [first, pattern] = r.window_id.split("_");
  const last = new Date(first + "T12:00:00Z");
  last.setUTCDate(last.getUTCDate() + (pattern.endsWith("4d") ? 3 : 2));
  return `${span(first, last.toISOString().slice(0, 10))} · ${PATTERN[pattern] || pattern}`;
}
function stopsText([out, back]) {
  if (!out && !back) return "Non-stop";
  if (out && back) return `${out} stop each way`;
  return out ? `${out} stop out` : `${back} stop back`;
}
const todayISO = () => new Intl.DateTimeFormat("en-CA", { timeZone: TZ, year: "numeric", month: "2-digit", day: "2-digit" }).format(Date.now());
function ago(iso) {
  const h = (Date.now() - new Date(iso)) / 3.6e6;
  if (h < 1) return "just now";
  if (h < 36) return `${Math.round(h)} h ago`;
  return `${Math.round(h / 24)} d ago`;
}
function flightsLink(r) {
  const apt = r.airport.split("/")[0];
  const q = `Flights to ${apt} from YYC on ${r.dates.out_dep.slice(0, 10)} through ${r.dates.back_dep.slice(0, 10)}`;
  return "https://www.google.com/travel/flights?q=" + encodeURIComponent(q);
}
function bandPill(band, count) {
  const p = el("span", { class: `pill band-${band}`, text: band });
  if (count != null) p.append(" ", el("span", { class: "n", text: String(count) }));
  return p;
}
function emptyCard(iconName, title, text) {
  return el("div", { class: "card empty-card" }, icon(iconName), el("p", {}, el("b", { text: title }), text));
}

// ---- sparkline: 2px line, end dot, crosshair + tooltip on hover/focus (dataviz skill); the table twin is below it ----
const tip = () => $("tip");
function showTip(x, y, value, label) {
  const t = tip();
  t.replaceChildren(el("strong", { text: value }), " ", el("span", { text: label }));
  t.hidden = false;
  const w = t.offsetWidth;
  t.style.left = Math.min(window.innerWidth - w - 8, Math.max(8, x - w / 2)) + "px";
  t.style.top = y - 36 + "px";
}
function hideTip() { tip().hidden = true; }

function sparkline(points, cityName) {
  const W = 300, H = 64, P = 6;
  const vals = points.map((p) => p[1]);
  const lo = Math.min(...vals), hi = Math.max(...vals);
  const x = (i) => (points.length === 1 ? W / 2 : P + (i * (W - 2 * P)) / (points.length - 1));
  const y = (v) => (hi === lo ? H / 2 : P + ((hi - v) * (H - 2 * P)) / (hi - lo));
  const last = points[points.length - 1];
  const svg = svgEl("svg", { class: "spark", viewBox: `0 0 ${W} ${H}`, tabindex: "0", role: "img",
    "aria-label": `${cityName}: cheapest fare per person over ${points.length} scan days, latest ${money(last[1])}, low ${money(lo)}, high ${money(hi)}` });
  svg.append(svgEl("line", { class: "base", x1: 0, x2: W, y1: H - 0.5, y2: H - 0.5 }));
  const cross = svgEl("line", { class: "cross", y1: 0, y2: H, visibility: "hidden" });
  svg.append(cross);
  if (points.length > 1) svg.append(svgEl("path", { class: "line", d: points.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p[1]).toFixed(1)}`).join("") }));
  svg.append(svgEl("circle", { class: "dot", cx: x(points.length - 1), cy: y(last[1]), r: 4 }));
  const at = (i) => {
    const r = svg.getBoundingClientRect();
    cross.setAttribute("x1", x(i)); cross.setAttribute("x2", x(i)); cross.setAttribute("visibility", "visible");
    showTip(r.left + (x(i) / W) * r.width, r.top, money(points[i][1]) + " pp", dayOf(points[i][0], { weekday: "short", day: "numeric", month: "short" }));
  };
  svg.addEventListener("pointermove", (e) => {
    const r = svg.getBoundingClientRect();
    const fx = ((e.clientX - r.left) / r.width) * W;
    let best = 0;
    points.forEach((_, i) => { if (Math.abs(x(i) - fx) < Math.abs(x(best) - fx)) best = i; });
    at(best);
  });
  svg.addEventListener("focus", () => at(points.length - 1));
  for (const ev of ["pointerleave", "blur"]) svg.addEventListener(ev, () => { cross.setAttribute("visibility", "hidden"); hideTip(); });
  return svg;
}

function history(points, cityName) {
  const box = el("div", { class: "hist" });
  if (!points || !points.length) {
    box.append(el("p", { class: "empty", text: "No history yet. The first point lands with the next scan." }));
    return box;
  }
  const vals = points.map((p) => p[1]);
  const last = points[points.length - 1];
  if (points.length < 2) {
    box.append(el("div", { class: "spark-cap" },
      el("span", {}, el("b", { text: money(last[1]) }), ` on ${dayOf(last[0], { weekday: "short", day: "numeric", month: "short" })}`),
      el("span", { class: "muted", text: "First scan day. The line draws itself as scans accumulate." })));
    return box;
  }
  box.append(sparkline(points, cityName));
  box.append(el("div", { class: "spark-cap" },
    el("span", {}, "Latest ", el("b", { text: money(last[1]) })),
    el("span", {}, "Low ", el("b", { text: money(Math.min(...vals)) })),
    el("span", {}, "High ", el("b", { text: money(Math.max(...vals)) })),
    el("span", { class: "muted", text: `${points.length} scan days` })));
  const tbody = el("tbody");
  for (const [d, v] of points) {
    tbody.append(el("tr", {}, el("th", { scope: "row", text: dayOf(d, { weekday: "short", day: "numeric", month: "short" }) }), el("td", { class: "num", text: money(v) })));
  }
  box.append(el("details", { class: "tbl" }, el("summary", { text: "Show as a table" }),
    el("table", {}, el("thead", {}, el("tr", {}, el("th", { scope: "col", text: "Scan day" }), el("th", { scope: "col", class: "num", text: "Cheapest per person" }))), tbody)));
  return box;
}

// ---- tiny, safe markdown for the templated briefs and notes: headings, bullets, numbered lists, **bold**, [text](https://...) ----
function inline(node, text) {
  const re = /\*\*(.+?)\*\*|\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g;
  let i = 0, m;
  while ((m = re.exec(text))) {
    node.append(text.slice(i, m.index));
    node.append(m[1] !== undefined ? el("strong", { text: m[1] }) : el("a", { href: m[3], text: m[2], rel: "noopener", target: "_blank" }));
    i = re.lastIndex;
  }
  node.append(text.slice(i));
}
function renderMd(md, base = 3) {
  const box = el("div", { class: "brief" });
  const tags = [base, base + 1, base + 2].map((n) => `h${Math.min(n, 6)}`);
  let list = null;
  for (const line of md.split("\n")) {
    const item = line.match(/^(?:- |\* |(\d+)\. )(.*)/);
    if (item) {
      const kind = item[1] ? "ol" : "ul";
      if (!list || list.tagName.toLowerCase() !== kind) box.append((list = el(kind)));
      const li = el("li"); inline(li, item[2]); list.append(li);
      continue;
    }
    list = null;
    if (!line.trim()) continue;
    const h = line.match(/^(#{1,3}) (.*)/);
    const n = el(h ? tags[h[1].length - 1] : "p");
    inline(n, h ? h[2] : line);
    box.append(n);
  }
  // The collector writes ISO dates into titles ("Vancouver: 2026-11-20 to 2026-11-22", "Daily note 2026-11-10"); show them like the cards do.
  const title = box.querySelector(tags[0]);
  if (title) title.textContent = title.textContent.replace(/\d{4}-\d{2}-\d{2}/g, (d) => dayOf(d, { weekday: "short", day: "numeric", month: "short" }));
  return box;
}
// Hit ids are "<scan date>_<city>_<window id>"; the window id is the tail after the city key.
const hitWindowId = (r) => r.id.slice(r.id.indexOf(r.city) + r.city.length + 1);
const hitWindow = (r) => windowLabel({ window_id: hitWindowId(r) });
const GATES = "an amazing fare (or a good one in the cheapest tenth of its history), a score of 80 or more, and a complete trip under the city's bar";
function hitCard(r, note, base) {
  const d = el("details", {});
  d.append(el("summary", {},
    el("span", { class: "row" },
      el("span", { class: "main" }, el("span", { class: "name", text: r.city_name }), el("span", { class: "sub", text: hitWindow(r) })),
      el("span", { class: "price" }, el("span", { class: "for2", text: money(r.total_cad) }), el("span", { class: "pp", text: "all-in for two" }))),
    el("span", { class: "meta" }, el("span", { text: `Score ${r.score}` }), note ? el("span", { text: note }) : null,
      el("span", { class: "muted", text: "Brief" }), icon("i-chev", "ic chev"))));
  d.addEventListener("toggle", async () => {
    if (!d.open || d.dataset.loaded) return;
    d.dataset.loaded = "1";
    const md = await getText(r.path_md);
    d.append(el("div", { class: "body" }, md ? renderMd(md, base) : el("p", { class: "empty", text: "Brief not found." })));
  });
  return el("article", { class: "card city hit" }, d);
}
const hitCards = (rows, note, base = 3) => el("div", { class: "cards" }, ...rows.map((r) => hitCard(r, note ? note(r) : null, base)));
function briefList(rows, label) {
  const card = el("div", { class: "card" });
  for (const r of rows) {
    const d = el("details", { class: "item" },
      el("summary", {}, el("span", { class: "city", text: r.city_name }), el("span", { class: "small", text: label(r) }), icon("i-chev", "ic chev")));
    d.addEventListener("toggle", async () => {
      if (!d.open || d.dataset.loaded) return;
      d.dataset.loaded = "1";
      const md = await getText(r.path_md);
      d.append(md ? renderMd(md) : el("p", { class: "empty", text: "Brief not found." }));
    });
    card.append(d);
  }
  return card;
}

// ---- city cards ----
function cityCard(r, ctx) {
  const d = el("details", {});
  d.append(el("summary", {},
    el("span", { class: "row" },
      el("span", { class: "main" },
        el("span", { class: "name", text: r.city_name }),
        el("span", { class: "sub", text: `${r.airport} · ${r.airlines} · ${stopsText(r.stops)}` })),
      el("span", { class: "price" },
        el("span", { class: "for2", text: money(r.flights_cad_2pax) }),
        el("span", { class: "pp", text: `${money(r.price_pp)} per person` }))),
    el("span", { class: "dates", text: windowLabel(r) }),
    el("span", { class: "sub", text: `Leave ${wall(r.dates.out_dep)} · home ${wall(r.dates.back_arr)}` }),
    el("span", { class: "meta" },
      bandPill(r.band),
      el("span", { text: `${Math.round(r.hours_on_ground)} h on the ground` }),
      el("span", { text: `Score ${r.score}` }),
      r.history_pct != null ? el("span", { text: `Cheaper than ${100 - Math.round(r.history_pct)}% of past fares` }) : null,
      icon("i-chev", "ic chev"))));
  d.addEventListener("toggle", () => {
    if (!d.open || d.dataset.loaded) return;
    d.dataset.loaded = "1";
    d.append(cityBody(r, ctx));
  });
  const card = el("article", { class: "card city" }, d);
  card.dataset.score = r.score; card.dataset.price = r.flights_cad_2pax; card.dataset.name = r.city_name;
  return card;
}

function cityBody(r, { series, windows }) {
  const body = el("div", { class: "body" });
  const left = el("div", {}, el("h3", { class: "sub-h", text: "Cheapest fare per person on any long weekend, by scan day" }), history(series[r.city], r.city_name));
  const right = el("div", {});
  const ws = windows.filter((w) => w.city === r.city).sort((a, b) => a.dates.check_in.localeCompare(b.dates.check_in));
  if (ws.length) {
    right.append(el("h3", { class: "sub-h", text: "Every long weekend" }));
    const tbody = el("tbody");
    for (const w of ws) {
      tbody.append(el("tr", { class: w.window_id === r.window_id ? "is-best" : null },
        el("th", { scope: "row" }, el("span", { text: windowLabel(w) }), el("span", { class: "sub", text: `${w.airport} · ${w.airlines} · ${stopsText(w.stops)} · leave ${wall(w.dates.out_dep)}, home ${wall(w.dates.back_arr)}` })),
        el("td", {}, bandPill(w.band)),
        el("td", { class: "num", text: money(w.flights_cad_2pax) }),
        el("td", { class: "num", text: String(w.score) })));
    }
    right.append(el("table", { class: "wins" },
      el("thead", {}, el("tr", {}, ...["Trip", "Band", "For two", "Score"].map((h, i) => el("th", { scope: "col", class: i > 1 ? "num" : null, text: h })))), tbody));
  }
  body.append(left, right, el("p", { class: "links" },
    el("a", { href: flightsLink(r), rel: "noopener", target: "_blank" }, icon("i-plane"), `Open in Google Flights`),
    el("span", { class: "muted", text: ` · Complete trip about ${money(r.total_cad)} for two, alert bar ${money(r.bar_cad)}` })));
  return body;
}

function sortCards(by) {
  const box = $("cities");
  const cmp = {
    score: (a, b) => b.dataset.score - a.dataset.score || a.dataset.price - b.dataset.price,
    price: (a, b) => a.dataset.price - b.dataset.price,
    city: (a, b) => a.dataset.name.localeCompare(b.dataset.name),
    mine: (a, b) => a.dataset.order - b.dataset.order,
  }[by];
  box.append(...[...box.children].sort(cmp));
}

// ---- sections ----
function renderVerdict(latest, hits, stale) {
  const box = $("verdict");
  const rows = latest.best_by_city || [];
  // Hit files are never deleted, so a live hit stays on the page only until its long weekend has started.
  const today = todayISO();
  const live = hits.filter((h) => h.mode === "live" && h.is_hit && hitWindowId(h).slice(0, 10) >= today);
  const dry = hits.filter((h) => h.mode === "dry-run" && h.is_hit);
  const learning = latest.mode === "dry-run";
  const h1 = el("h1", { id: "verdict-h" });
  box.replaceChildren(h1);
  if (live.length) {
    h1.textContent = live.length === 1 ? "One trip worth booking today." : `${live.length} trips worth booking today.`;
    box.append(el("p", { class: "lead", text: `${live.length === 1 ? "It" : "Each"} passed all three gates: ${GATES}. Open the brief for the hotels and the links.` }), hitCards(live, null, 2));
  } else {
    h1.textContent = "Nothing worth booking today.";
    const counts = {};
    for (const r of rows) counts[r.band] = (counts[r.band] || 0) + 1;
    const cheapest = rows.reduce((a, b) => (!a || b.flights_cad_2pax < a.flights_cad_2pax ? b : a), null);
    const parts = [];
    if (rows.length) {
      parts.push(`${rows.length} cities scanned.`);
      if (cheapest) parts.push(`Cheapest for two is ${cheapest.city_name} at ${money(cheapest.flights_cad_2pax)}, ${cheapest.band === "bad" ? "still in the bad band" : `band ${cheapest.band}`}.`);
    } else parts.push("No trip fitted a long-weekend window in the last scan.");
    if (learning) parts.push(dry.length ? `Learning run: ${dry.length} would have fired, nothing alerts yet.` : "Learning run: nothing alerts yet while the bands are tuned from this data.");
    box.append(el("p", { class: "lead", text: parts.join(" ") }));
    if (rows.length) box.append(el("div", { class: "bands", role: "group", "aria-label": "Band spread" }, ...BANDS.map((b) => bandPill(b, counts[b] || 0))));
  }
  if (stale) {
    box.append(el("div", { class: "notice" }, icon("i-warn"),
      el("p", { text: `The last scan is ${Math.round(stale)} hours old, so these fares may be out of date. The daily run may have failed; the health panel has the details.` })));
  }
}

function renderCities(latest, series) {
  const rows = latest.best_by_city || [];
  const sec = $("cities-sec");
  sec.hidden = false;
  if (!rows.length) {
    $("cities").replaceChildren(emptyCard("i-radar", "No in-window trips found.", "The last scan found no itinerary that fits a long-weekend window for any city. The next scan tries again."));
    return;
  }
  const ctx = { series, windows: latest.windows || [] };
  const mine = Object.fromEntries((latest.cities || []).map((c, i) => [c.key, i]));   // config/cities.yaml order, set in Settings
  $("cities").replaceChildren(...rows.map((r) => { const card = cityCard(r, ctx); card.dataset.order = mine[r.city] ?? 999; return card; }));
  sortCards(document.querySelector("#sort input:checked").value);
}

function renderDry(latest, hits) {
  const dry = hits.filter((h) => h.mode === "dry-run").sort((a, b) => b.is_hit - a.is_hit || b.created.localeCompare(a.created));
  const sec = $("dry-sec");
  sec.hidden = latest.mode !== "dry-run";
  if (sec.hidden) return;
  $("dry").replaceChildren(dry.length
    ? hitCards(dry, (r) => (r.is_hit ? "Would have fired" : "Near miss"))
    : emptyCard("i-pulse", "Nothing has reached the hotel check yet.", `A trip lands here once it clears the gates: ${GATES}. Expected after the bands are retuned.`));
}

async function renderNotes(digests) {
  const box = $("notes");
  if (!digests.length) {
    box.replaceChildren(emptyCard("i-note", "No notes yet.", "A short note follows each daily scan during the learning run, with a weekly digest on Mondays."));
    return;
  }
  const [latest, ...rest] = digests;
  const md = await getText(latest.path);
  const brief = md ? renderMd(md) : el("p", { class: "empty", text: "Note not found." });
  box.replaceChildren(el("article", { class: "card note" }, brief));
  if (rest.length) {
    box.append(el("h3", { class: "sub-h", text: "Earlier notes" }),
      briefList(rest.map((d) => ({ city_name: dayOf(d.date, { weekday: "short", day: "numeric", month: "short" }), path_md: d.path })), () => ""));
  }
}

function renderHealth(latest, stale) {
  const h = latest.health || {};
  const names = Object.fromEntries((latest.cities || []).map((c) => [c.key, c.name]));
  const items = [
    ["Last scan", latest.scan_ts ? when(latest.scan_ts) : "–", stale ? "bad" : "ok"],
    ["Mode", latest.mode === "dry-run" ? "learning run (no alerts)" : latest.mode],
    ["Coverage", `${h.coverage_pct ?? "–"}% of ${h.queries_planned ?? "–"} queries`, (h.coverage_pct ?? 100) < 80 ? "bad" : "ok"],
    ["Requests sent", `${h.queries_attempted ?? "–"} of ${h.budget_max ?? "–"} budget`],
    ["Fetch errors", h.fetch_error_count, h.fetch_error_count ? "bad" : "ok"],
    ["Blocked by Google", h.blocked ? "yes" : "no", h.blocked ? "bad" : "ok"],
    ["SerpApi this month", `${h.serpapi_used_this_month ?? 0} of ${h.serpapi_cap ?? 60} searches`],
    ["Cache hits", h.cache_hits],
    ["Skipped (budget)", h.budget_skipped],
    ["Events", h.events_source],
    ["Host", h.host],
    ["Duration", h.duration_s != null ? `${Math.round(h.duration_s / 60)} min` : "–"],
    ["No non-stop found", (h.no_nonstop || []).map((k) => names[k] || k).join(", ") || "none", null, true],
  ];
  const dl = el("dl", { class: "health" });
  for (const [k, v, st, wide] of items) {
    const d = el("div", {}, el("dt", { text: k }), el("dd", { class: st ? `status-${st}` : null, text: v == null ? "–" : String(v) }));
    if (wide) d.style.gridColumn = "1 / -1";
    dl.append(d);
  }
  const errs = (h.fetch_errors || []).slice(0, 5);
  $("health-body").replaceChildren(dl,
    errs.length ? el("ul", { class: "errs" }, ...errs.map((e) => el("li", { text: `${e.route} ${e.day}: ${e.error}` }))) : "",
    el("p", { class: "sheet-foot", text: "Healthy means coverage above 80%, no fetch errors, not blocked, and a scan in the last 30 hours." }));
  const state = h.blocked || stale ? "bad" : (h.coverage_pct ?? 100) < 80 || h.fetch_error_count ? "warn" : "ok";
  $("health-dot").className = "dot " + state;
  const label = "Scan health: " + { ok: "healthy", warn: "warning", bad: "problem" }[state];
  $("health-btn").setAttribute("aria-label", label);
  $("health-btn").title = label;
}

function wireDialog(dlg, openBtn, closeBtn, onOpen) {
  openBtn.addEventListener("click", () => { dlg.showModal(); if (onOpen) onOpen(); });
  closeBtn.addEventListener("click", () => dlg.close());
  dlg.addEventListener("click", (e) => {   // a click on the backdrop lands on the dialog element itself, outside its box
    const r = dlg.getBoundingClientRect();
    if (e.target === dlg && (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom)) dlg.close();
  });
}
// localStorage is a convenience only (the chosen sort, the GitHub token): every call tolerates a blocked store.
const store = {
  get(k) { try { return localStorage.getItem(k); } catch { return null; } },
  set(k, v) { try { v == null ? localStorage.removeItem(k) : localStorage.setItem(k, v); } catch { /* private mode or blocked */ } },
};

async function main() {
  wireDialog($("health"), $("health-btn"), $("health-close"));
  const savedSort = document.querySelector(`#sort input[value="${store.get("radar.sort")}"]`);
  if (savedSort) savedSort.checked = true;
  $("sort").addEventListener("change", (e) => { store.set("radar.sort", e.target.value); sortCards(e.target.value); });
  const [latest, series, hits, digests] = await Promise.all([
    getJSON("data/latest.json"), getJSON("data/series.json"), getJSON("hits/index.json"), getJSON("data/digests/index.json"),
  ]);
  if (!latest) {
    $("scan-age").textContent = "No scan yet";
    $("verdict").replaceChildren(el("h1", { id: "verdict-h", text: "No scan published yet." }),
      el("p", { class: "lead", text: "The collector runs every day at 10:17 UTC and publishes its results here." }));
    $("health-body").replaceChildren(el("p", { class: "sheet-foot", text: "No scan has been published yet." }));
    renderNotes(digests || []);
    return;
  }
  const ageH = (Date.now() - new Date(latest.scan_ts)) / 3.6e6;
  const stale = ageH > STALE_HOURS ? ageH : 0;
  const chip = $("scan-age");
  chip.replaceChildren(el("span", { class: "chip-long", text: "Scanned " }), ago(latest.scan_ts));   // "Scanned" hides on narrow phones
  chip.title = when(latest.scan_ts) + " Calgary time";
  chip.classList.toggle("warn", Boolean(stale));

  const all = hits || [];
  renderVerdict(latest, all, stale);
  renderCities(latest, series || {});
  renderDry(latest, all);
  renderHealth(latest, stale);
  renderNotes(digests || []);
}

main();
