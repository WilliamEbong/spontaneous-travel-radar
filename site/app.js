// Travel Radar dashboard: vanilla JS, no build step. Reads the JSON the collector and the daily routine commit;
// all data text goes in via textContent. Order (v2): hits, every trip that scored 70+, every city, notes.
"use strict";

const TZ = "America/Edmonton";
const STALE_HOURS = 30;
const PATTERN = { "fri-off": "Fri off", "mon-off": "Mon off", "stat-thu-4d": "Thu stat, 4 days", "stat-tue-4d": "Tue stat, 4 days", weekend: "Fri to Sun" };
const CLASS = { weekend: "No day off needed", dayoff: "Needs a day off" };
const CLASS_ORDER = ["weekend", "dayoff"];
const LADDER = { exceptional: "exceptional", good: "good", typical: "typical", above: "above typical" };
const EASE = "cubic-bezier(0.3, 0, 0.7, 1)";   // the page's one easing (DESIGN.md, Motion)
const MOTION = !matchMedia("(prefers-reduced-motion: reduce)").matches;   // false = straight cuts everywhere

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
// The trip's days from the window id "<day 1>_<pattern>": a 3-day block, 4 with a stat, or Friday to Sunday for "weekend".
function windowDays(windowId) {
  const [first, pattern] = windowId.split("_");
  const last = new Date(first + "T12:00:00Z");
  last.setUTCDate(last.getUTCDate() + (pattern.endsWith("4d") ? 3 : 2));
  return { text: span(first, last.toISOString().slice(0, 10)), pattern: PATTERN[pattern] || pattern };
}
const windowLabel = (windowId) => { const w = windowDays(windowId); return `${w.text} · ${w.pattern}`; };
function stopsText([out, back]) {
  if (!out && !back) return "Non-stop";
  if (out && back) return `${out} stop each way`;
  return out ? `${out} stop out` : `${back} stop back`;
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
// Pills always print their text: colour never carries the meaning alone (D-22).
const ladderPill = (label) => (label ? el("span", { class: `lad lad-${label}`, text: LADDER[label] || label }) : null);
const classPill = (cls) => el("span", { class: `cls cls-${cls}`, text: CLASS[cls] || cls });
function emptyCard(iconName, title, text) {
  return el("div", { class: "slip empty-card" }, icon(iconName), el("p", {}, el("b", { text: title }), text));
}
const pct = (share) => (share == null ? "–" : `${Math.round(share * 100)}%`);
const byClass = (rows, cls = (r) => r.trip_class) => CLASS_ORDER.map((c) => [c, rows.filter((r) => (cls(r) || "dayoff") === c)]).filter(([, rs]) => rs.length);

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
  if (points.length > 1) svg.append(svgEl("path", { class: "line", pathLength: "1", d: points.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p[1]).toFixed(1)}`).join("") }));   // pathLength 1: the line draws itself with a dash offset when its tray opens
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
  const re = /\*\*(.+?)\*\*|\[([^\]]+)\]\((https:\/\/[^)\s]+)\)/g;   // https links only
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
// A <details> whose body is a brief: fetched once, at the first sign of interest (a hover, focus or touch on the summary) so
// it is usually in hand when the card opens and the body can rise with the card; else fetched when it opens.
function lazyBrief(d, path, base) {
  let md;
  const fetchIt = () => (md ??= getText(path));
  const sum = d.querySelector("summary");
  for (const ev of ["pointerenter", "focusin", "touchstart"]) sum.addEventListener(ev, fetchIt, { once: true, passive: true });
  d.addEventListener("toggle", async () => {
    if (!d.open || d.dataset.loaded) return;
    d.dataset.loaded = "1";
    const text = await fetchIt();
    const brief = text ? renderMd(text, base) : el("p", { class: "empty", text: "Brief not found." });
    if (text && /^H[2-6]$/.test(brief.firstChild?.tagName || "")) brief.firstChild.remove();   // the card already names the city, dates and score
    d.append(el("div", { class: "body" }, brief));
  });
}
// Trays, drawers and hit cards fade up the first time they come into view, the ones arriving together 60 ms apart (at most
// 300). The classes are added here, so without JS, or with reduced motion, nothing is ever hidden; once a card has shown, the
// classes come off again so no transform lingers under its floating breakdown slip.
const revealer = MOTION && "IntersectionObserver" in window ? new IntersectionObserver((entries) => {
  let i = 0;
  for (const e of entries) {
    if (!e.isIntersecting) continue;
    revealer.unobserve(e.target);
    e.target.style.setProperty("--d", `${Math.min(i++, 5) * 60}ms`);
    e.target.classList.add("in");
    e.target.addEventListener("transitionend", () => { e.target.classList.remove("reveal", "in"); e.target.style.removeProperty("--d"); }, { once: true });
  }
}, { rootMargin: "0px 0px -8% 0px" }) : null;
function reveal(nodes) {
  if (!revealer) return;
  for (const n of nodes) { n.classList.add("reveal"); revealer.observe(n); }
}
function groupHead(cls, n) {
  return el("h3", { class: `grp grp-${cls}` }, classPill(cls), el("span", { class: "n", text: n === 1 ? "1 trip" : `${n} trips` }));
}

// ---- score breakdown (D-75): the score is a button. Hover or keyboard focus opens its panel on wide screens (it floats by
// the button); a tap toggles it on phones (it sits inline under the row). Escape, a tap outside or leaving closes it; one
// open at a time. Rows come from the collector: {key, label, points, max, input}; the points add up to the score. ----
let bdSeq = 0, bdOpen = null, bdTimer = 0;
const floating = () => matchMedia("(min-width: 720px)").matches;
const fmtPts = (n) => (Number.isInteger(n) ? String(n) : n.toFixed(1)).replace("-", "−");
function bdFill(panel, rows, score) {
  const tbody = el("tbody");
  for (const r of rows) {
    const td = el("td");
    if (r.points != null) {   // lodging has no points of its own: it moves price and convenience
      const bar = el("span", { class: "bdbar", "aria-hidden": "true" }, el("i"));
      bar.firstChild.style.width = `${Math.max(0, Math.min(100, (100 * r.points) / r.max))}%`;
      td.append(el("span", { class: "pts", text: `${fmtPts(r.points)} / ${r.max}` }), bar);
    }
    td.append(el("span", { class: "in", text: r.input }));
    tbody.append(el("tr", {}, el("th", { scope: "row", text: r.label }), td));
  }
  panel.replaceChildren(el("p", { class: "bd-h", text: `How ${score} adds up` }), el("table", { class: "bdt" }, tbody));
}
function bdClose() {
  if (!bdOpen) return;
  bdOpen.panel.hidden = true;   // its position stays while it fades out; bdPlace sets it afresh on the next open
  bdOpen.btn.setAttribute("aria-expanded", "false");
  bdOpen = null;
}
// Wide screens: the panel is fixed, so no card or list clips it; below the button, or above when there is no room.
function bdPlace({ btn, panel }) {
  if (!floating()) { panel.style.cssText = ""; return; }
  const r = btn.getBoundingClientRect(), w = panel.offsetWidth, h = panel.offsetHeight;
  const below = r.bottom + 6 + h <= window.innerHeight || r.top - 6 - h < 0;
  const left = r.left + w + 8 <= window.innerWidth ? r.left : r.right - w;   // under the score's left edge, else right-aligned
  panel.style.left = `${Math.max(8, Math.min(window.innerWidth - w - 8, left))}px`;
  panel.style.top = `${below ? r.bottom + 6 : r.top - 6 - h}px`;
}
function bdShow(btn, panel, by) {
  clearTimeout(bdTimer);
  if (bdOpen && bdOpen.btn !== btn) bdClose();
  if (bdOpen) { bdOpen.by = by; return; }
  panel.hidden = false;
  btn.setAttribute("aria-expanded", "true");
  bdOpen = { btn, panel, by };
  bdPlace(bdOpen);
}
// [button, panel] to drop where the score text was; plain text when a row has no breakdown (data from before D-75).
function scoreUI(score, rows, label = "Score", short = false) {
  const lbl = short ? el("span", { class: "lbl", text: label }) : `${label} `;   // the table's column head already says Score
  if (!rows || !rows.length) return [el("span", { class: "strong" }, lbl, String(score))];
  const id = `bd-${++bdSeq}`;
  const btn = el("button", { type: "button", class: "score", "aria-expanded": "false", "aria-controls": id }, lbl, el("span", { class: "n", text: String(score) }));
  const panel = el("div", { class: "bd", id, role: "group", "aria-label": `${label} ${score} breakdown`, hidden: "" });
  let filled = false;
  const open = (by) => { if (!filled) { bdFill(panel, rows, score); filled = true; } bdShow(btn, panel, by); };
  const mine = () => bdOpen && bdOpen.btn === btn;
  btn.addEventListener("click", (e) => {
    e.preventDefault(); e.stopPropagation();   // inside a <summary>: a tap on the score must not toggle the card
    if (mine() && bdOpen.by !== "hover") bdClose(); else open("click");
  });
  btn.addEventListener("pointerenter", (e) => { if (e.pointerType === "mouse" && !mine()) open("hover"); });
  const leave = (e) => { if (e.pointerType === "mouse" && mine() && bdOpen.by === "hover") bdTimer = setTimeout(bdClose, 150); };
  btn.addEventListener("pointerleave", leave);
  panel.addEventListener("pointerleave", leave);
  panel.addEventListener("pointerenter", () => clearTimeout(bdTimer));
  btn.addEventListener("focus", () => { if (btn.matches(":focus-visible")) open("focus"); });
  btn.addEventListener("blur", () => { if (mine()) bdClose(); });
  panel.addEventListener("click", (e) => { e.preventDefault(); e.stopPropagation(); });
  return [btn, panel];
}
document.addEventListener("keydown", (e) => { if (e.key === "Escape") bdClose(); });
document.addEventListener("pointerdown", (e) => { if (bdOpen && !bdOpen.btn.contains(e.target) && !bdOpen.panel.contains(e.target)) bdClose(); });
for (const ev of ["scroll", "resize"]) window.addEventListener(ev, () => { if (bdOpen) bdPlace(bdOpen); }, { passive: true });   // a floating panel follows its button (focus may scroll it into view)

// ---- hits ----
function hitCard(r) {
  const w = windowDays(r.window_id);
  const [num, ...panel] = scoreUI(r.final_score, r.breakdown, "Final", true);   // the same anatomy as a city tray, the numeral in rust
  const d = el("details", {});
  d.append(el("summary", {},
    el("span", { class: "row" },
      el("span", { class: "main" }, el("span", { class: "name", text: r.city_name }), el("span", { class: "sub", text: `${w.text} · ${w.pattern}` })),
      el("span", { class: "num" }, num)),
    el("span", { class: "fig" }, el("span", { class: "for2", text: money(r.total_cad) }), el("span", { class: "pp", text: "complete trip for two" })),
    el("span", { class: "meta" }, el("span", { class: "ml" }, el("span", { text: `Flights ${money(r.price_pp)} pp` }), ladderPill(r.ladder)), classPill(r.trip_class), icon("i-chev", "ic chev")),
    ...panel));
  lazyBrief(d, r.path_md, 2);
  return el("article", { class: `city hit c-${r.trip_class}` }, d);
}
const hitLine = (latest) => {
  const t = [...new Set(Object.values(latest.classes || {}).map((c) => c.hit_threshold))];
  return `score of ${t.length ? t.join(" or ") : 80}`;
};

// The headline and the one line under the horizon live in the first frame; the lead and the hit cards begin on the paper.
function frameLead(kicker, city, figure, href) {
  const a = $("frame-lead");
  a.replaceChildren(el("span", { class: "k", text: kicker }), el("span", { class: "c", text: city }), el("span", { class: "f", text: figure }));
  a.href = href;
  a.hidden = false;
}
function renderVerdict(latest, index, stale) {
  const box = $("verdict-body"), h1 = $("verdict-h"), lead = $("lead");
  const today = todayISO();
  // Hit files are never deleted, so a hit stays on the page only until its trip has started.
  const hits = index.filter((h) => h.is_hit && h.window_id.slice(0, 10) >= today).sort((a, b) => b.final_score - a.final_score);
  box.replaceChildren();
  const note = latest.mode === "dry-run" ? " Learning run: nothing is emailed yet." : "";
  if (hits.length) {
    const top = hits[0];
    h1.textContent = hits.length === 1 ? "One trip worth booking." : `${hits.length} trips worth booking.`;
    frameLead(hits.length === 1 ? "The hit" : "The top hit", top.city_name, `${windowLabel(top.window_id)} · ${money(top.total_cad)} for two · final ${top.final_score}`, "#verdict");
    lead.textContent = `${hits.length === 1 ? "It" : "Each"} cleared all three passes: a fare at or under the route's good, a complete trip well under what it normally costs, and enough on for those dates to reach a final ${hitLine(latest)}.`
      + (note || " Open the brief for the lodging, what's on and the links.");
    for (const [cls, rows] of byClass(hits)) {
      const cards = rows.map(hitCard);
      box.append(groupHead(cls, rows.length), el("div", { class: "cards" }, ...cards));
      reveal(cards);
    }
  } else {
    h1.textContent = "Nothing worth booking today.";
    const best = (latest.best_by_city || [])[0];
    if (best) frameLead("Best deal today", best.city_name, `${windowLabel(best.window_id)} · ${money(best.total_cad)} for two` + (best.share != null ? ` · ${pct(best.share)} of typical` : ""), `#city-${best.city}`);
    else $("frame-lead").hidden = true;
    lead.textContent = (best ? "" : "No trip fitted a window in the last scan. ") + `A hit needs a final ${hitLine(latest)}. Most days nothing comes close, and that is the radar working.` + note;
  }
  if (stale) {
    box.append(el("div", { class: "notice" }, icon("i-warn"),
      el("p", { text: `The last scan is ${Math.round(stale)} hours old, so these fares may be out of date. The daily run may have failed; the health panel has the details.` })));
  }
}

// ---- passed: every trip at or over its class's candidate line, and how far it got ----
function stage(r, good, idx) {
  const c = r.candidate_id ? idx.get(r.candidate_id) : null;
  if (!c) {
    if (good != null && r.price_pp > good) return { step: 1, text: `Fares only: ${money(r.price_pp)} pp is above this route's good (${money(good)}).` };
    return { step: 1, text: "Fares only: higher-scoring candidates used today's lodging checks (three a day)." };
  }
  const base = { c, score: c.final_score ?? c.score_p2, hit: c.is_hit };
  if (c.pass === 3) return { ...base, step: 3, text: `${c.is_hit ? "Hit" : "Near miss"}: ${money(c.total_cad)} for two, what's on +${c.events_pts}, final ${c.final_score}.` };
  if (c.status === "dropped") return { ...base, step: 2, text: `Lodging checked, score ${c.score_p2}: ${c.drop_reason}.` };
  return { ...base, step: 2, text: `Lodging checked: ${money(c.total_cad)} for two, score ${c.score_p2}. What's on is researched next.` };
}

// A catalogue drawer: the score as a big serif numeral, the trip beside it, the stage it reached underneath.
function passedRow({ r, st }) {
  const w = windowDays(r.window_id);
  const [num, ...panel] = scoreUI(st.score ?? r.score, st.c ? st.c.breakdown : r.breakdown, "Score", true);   // the candidate's latest pass, else pass 1
  const head = [num,   // the grid areas in .prow-sum place these: numeral and city on one line, then dates, class, fare line, stage
    el("b", { class: "city", text: r.city_name }),
    el("span", { class: "small", text: `${w.text} · ${w.pattern}` }),
    classPill(r.trip_class),
    el("span", { class: "prow-meta" }, el("span", { text: `${money(r.price_pp)} pp` }), ladderPill(r.ladder), el("span", { class: `stage${st.hit ? " hit" : ""}`, text: `Pass ${st.step}` })),
    el("span", { class: "prow-stage", text: st.text }),
    ...panel];
  const cls = `prow c-${r.trip_class}`;
  if (!st.c) return el("li", { class: cls }, el("div", { class: "prow-sum" }, ...head));
  const d = el("details", {}, el("summary", { class: "prow-sum" }, ...head, icon("i-chev", "ic chev")));
  lazyBrief(d, st.c.path_md, 3);
  return el("li", { class: cls }, d);
}

function renderPassed(latest, index) {
  const classes = latest.classes || {};
  const goods = Object.fromEntries((latest.cities || []).map((c) => [c.key, c.ladder ? c.ladder.good : null]));
  const idx = new Map(index.map((r) => [r.id, r]));
  const line = (cls) => classes[cls]?.candidate_threshold ?? 70;
  const items = (latest.windows || []).filter((r) => r.score >= line(r.trip_class || "dayoff"))
    .map((r) => ({ r, st: stage(r, goods[r.city], idx) }))
    .sort((a, b) => Boolean(b.st.hit) - Boolean(a.st.hit) || (b.st.score ?? b.r.score) - (a.st.score ?? a.r.score));
  const lines = [...new Set(Object.values(classes).map((c) => c.candidate_threshold))].join(" or ") || "70";
  $("passed-sec").hidden = false;
  $("passed-h").textContent = `Scored ${lines} or more`;
  $("passed-n").textContent = items.length === 1 ? "1 trip" : `${items.length} trips`;
  if (!items.length) {   // a quiet day collapses to one line
    $("passed-hint").textContent = "";
    $("passed").replaceChildren(el("p", { class: "quiet", text: "None today. Every route's fares sit near or above what they normally cost; quiet is the radar working." }));
    return;
  }
  $("passed-hint").textContent = "How far each one got: fares (pass 1), then real lodging near the centre (pass 2), then what is on for those dates (pass 3).";
  const box = el("div", {});
  for (const [cls, rs] of byClass(items, (x) => x.r.trip_class)) {
    const rows = rs.map(passedRow);
    box.append(groupHead(cls, rs.length), el("ul", { class: "plist" }, ...rows));
    reveal(rows);
  }
  $("passed").replaceChildren(box);
}

// ---- every city: its best deal (top score), the route's ladder, every weekend, price history ----
function cityCard(r, c, ctx) {
  const lad = c.ladder || {};
  const ladderLine = el("span", { class: "sub lad-line", text: `Typical for this route ${money(lad.typical)} pp · exceptional under ${money(lad.exceptional)}` });
  if (!r) {
    const card = el("article", { class: "city none", id: `city-${c.key}` }, el("div", { class: "nosum" },
      el("span", { class: "name", text: c.name }), ladderLine, el("span", { class: "sub", text: "No trip fits a window in this scan." })));
    Object.assign(card.dataset, { score: -999, price: 1e9, name: c.name });
    return card;
  }
  // A tray: the city in serif with its score numeral beside it, the figures in mono underneath, the class and ladder lines
  // at the bottom. Every line is one line in every tray, so the trays in a row are the same height.
  const [num, ...panel] = scoreUI(r.score, r.breakdown, "Score", true);
  const d = el("details", {});
  d.append(el("summary", {},
    el("span", { class: "row" },
      el("span", { class: "main" },
        el("span", { class: "name", text: c.name }),
        el("span", { class: "sub", text: `${r.airport} · ${r.airlines} · ${stopsText(r.stops)}` })),
      el("span", { class: "num" }, num)),
    el("span", { class: "fig" }, el("span", { class: "for2", text: money(r.total_cad) }), el("span", { class: "pp", text: `for two · flights ${money(r.price_pp)} pp` })),
    el("span", { class: "dates" }, el("span", { text: windowLabel(r.window_id) })),
    el("span", { class: "sub", text: `Leave ${wall(r.dates.out_dep)} · home ${wall(r.dates.back_arr)}` }),
    el("span", { class: "meta" }, el("span", { class: "ml" }, ladderPill(r.ladder), r.share != null ? el("span", { text: `${pct(r.share)} of typical` }) : null), classPill(r.trip_class), icon("i-chev", "ic chev")),
    ...panel));   // the route's ladder moves into the opened body: the word and the share already say it
  // The body is built at the first sign of interest (a hover, focus or touch on the summary; building all twenty at once
  // costs 100 ms), so it is in place before the tray opens and the height eases to its full size in one movement. When it
  // opens, the price line draws itself and its end dot lands.
  let built = false;
  const ensure = () => { if (!built) { built = true; d.append(cityBody(r, c, ctx)); } };
  for (const ev of ["pointerenter", "focusin", "touchstart"]) d.firstChild.addEventListener(ev, ensure, { once: true, passive: true });
  d.addEventListener("toggle", () => {
    ensure();
    if (!d.open || !MOTION) return;
    const line = d.querySelector(".spark .line"), dot = d.querySelector(".spark .dot");
    if (line) line.animate([{ strokeDasharray: 1, strokeDashoffset: 1 }, { strokeDasharray: 1, strokeDashoffset: 0 }], { duration: 800, easing: EASE });
    if (dot) dot.animate([{ opacity: 0 }, { opacity: 0, offset: 0.8 }, { opacity: 1 }], { duration: 1000, easing: "linear" });
  });
  const card = el("article", { class: `city c-${r.trip_class}`, id: `city-${c.key}` }, d);
  Object.assign(card.dataset, { score: r.score, price: r.total_cad, name: c.name });
  return card;
}

function cityBody(r, c, { series, windows }) {
  const body = el("div", { class: "body" });
  const lad = c.ladder || {};
  // history follows the card's class; older series files were a bare day-off list
  const all = Array.isArray(series[c.key]) ? { dayoff: series[c.key] } : (series[c.key] || {});
  const cls = (all[r.trip_class] || []).length ? r.trip_class : (all.dayoff ? "dayoff" : "weekend");
  const label = cls === "weekend" ? "Cheapest weekend fare per person, by scan day" : "Cheapest day-off fare per person, by scan day";
  const left = el("div", {}, el("h3", { class: "sub-h", text: label }), history(all[cls] || [], c.name));
  const right = el("div", {}, el("h3", { class: "sub-h", text: "Every weekend, best first" }));
  const ws = windows.filter((w) => w.city === c.key).sort((a, b) => b.score - a.score || a.total_cad - b.total_cad);
  const tbody = el("tbody");
  for (const w of ws) {
    tbody.append(el("tr", { class: `c-${w.trip_class}${w.window_id === r.window_id ? " is-best" : ""}` },
      el("th", { scope: "row" }, el("span", { text: windowLabel(w.window_id) }), classPill(w.trip_class),
        el("span", { class: "sub", text: `${w.airport} · ${w.airlines} · ${stopsText(w.stops)} · leave ${wall(w.dates.out_dep)}, home ${wall(w.dates.back_arr)} · ${money(w.price_pp)} pp` })),
      el("td", {}, ladderPill(w.ladder)),
      el("td", { class: "num", text: money(w.total_cad) }),
      el("td", { class: "num sc" }, ...scoreUI(w.score, w.breakdown, "Score", true))));   // the column head says Score; the label is for screen readers
  }
  right.append(el("table", { class: "wins" },
    el("thead", {}, el("tr", {}, ...["Trip", "Fare", "For two", "Score"].map((h, i) => el("th", { scope: "col", class: i > 1 ? "num" : null, text: h })))), tbody));
  body.append(left, right, el("p", { class: "links" },
    el("a", { href: flightsLink(r), rel: "noopener", target: "_blank" }, icon("i-plane"), "Open in Google Flights"),
    el("span", { class: "muted", text: ` · For two: flights ${money(r.flights_cad_2pax)}, lodging about ${money(r.lodging_cad)} (a good room rate until a closer look), transfers. This trip normally costs about ${money(r.typical_cad)}; flights on this route are typically ${money(lad.typical)} pp, exceptional under ${money(lad.exceptional)}.` })));
  return body;
}

// Re-sorting slides each tray from where it was to where it lands (400 ms, transform only); the first sort, at render, just places them.
function sortCards(by, animate = false) {
  const box = $("cities"), kids = [...box.children];
  const cmp = {
    score: (a, b) => b.dataset.score - a.dataset.score || a.dataset.price - b.dataset.price,
    price: (a, b) => a.dataset.price - b.dataset.price,
    city: (a, b) => a.dataset.name.localeCompare(b.dataset.name),
    mine: (a, b) => a.dataset.order - b.dataset.order,
  }[by];
  const before = animate && MOTION ? kids.map((k) => k.getBoundingClientRect()) : null;
  box.append(...kids.slice().sort(cmp));
  if (!before) return;
  kids.forEach((k, i) => {
    const a = before[i], b = k.getBoundingClientRect(), dx = a.left - b.left, dy = a.top - b.top;
    if (dx || dy) k.animate([{ transform: `translate(${dx}px, ${dy}px)` }, { transform: "none" }], { duration: 400, easing: EASE });
  });
}

function renderCities(latest, series) {
  $("cities-sec").hidden = false;
  const weeks = latest.classes?.dayoff?.min_weeks ?? 6;
  $("cities-hint").textContent = "Each city's best trip in this scan, judged against what that route normally costs. Tap a city for every weekend and its price history.";
  $("how").replaceChildren(el("summary", { text: "How trips are judged" }),
    el("p", { text: `Two kinds of trip. Needs a day off: scanned ${weeks} to ${latest.classes?.dayoff?.max_weeks ?? 16} weeks out so the time can be approved; leave from 7:30 pm the evening before, home by 4 pm on the last day off. No day off needed: the next 6 weeks, out Friday after 5:30 pm, home Sunday by 4 pm, non-stop only.` }),
    el("p", { text: "Fares are for two adults with a carry-on each, basic fares included. The score adds price (45 points: the complete trip against what the route normally costs), time there (20), convenience (10), city (15) and weather (10). 70 or more passes; a fare at or under the route's good gets a real lodging check; a final 80 with lodging in hand is a hit." }));
  const best = Object.fromEntries((latest.best_by_city || []).map((r) => [r.city, r]));
  const cities = latest.cities || [];
  if (!cities.length) {
    $("cities").replaceChildren(emptyCard("i-radar", "No cities in this scan.", "Every city is switched off in Settings."));
    return;
  }
  const ctx = { series, windows: latest.windows || [] };
  const cards = cities.map((c, i) => { const card = cityCard(best[c.key], c, ctx); card.dataset.order = i; return card; });   // cities.yaml order = "Mine"
  $("cities").replaceChildren(...cards);
  $("cities").removeAttribute("aria-busy");
  sortCards(document.querySelector("#sort input:checked").value);
  reveal(cards);
}

async function renderNotes(digests) {
  const box = $("notes");
  if (!digests.length) {
    box.replaceChildren(emptyCard("i-note", "No notes yet.", "A short note follows each daily scan during the learning run, with a weekly digest on Mondays."));
    return;
  }
  const [latest, ...rest] = digests;
  const md = await getText(latest.path);
  box.replaceChildren(el("article", { class: "slip page" }, md ? renderMd(md) : el("p", { class: "empty", text: "Note not found." })));
  if (!rest.length) return;
  const card = el("div", { class: "slip" });
  for (const n of rest) {
    const d = el("details", { class: "item" },
      el("summary", {}, el("span", { class: "date", text: dayOf(n.date, { weekday: "short", day: "numeric", month: "short" }) }), icon("i-chev", "ic chev")));
    d.addEventListener("toggle", async () => {
      if (!d.open || d.dataset.loaded) return;
      d.dataset.loaded = "1";
      const t = await getText(n.path);
      d.append(t ? renderMd(t) : el("p", { class: "empty", text: "Note not found." }));
    });
    card.append(d);
  }
  box.append(el("h3", { class: "sub-h", text: "Earlier notes" }), card);
}

function renderHealth(latest, stale) {
  const h = latest.health || {};
  const names = Object.fromEntries((latest.cities || []).map((c) => [c.key, c.name]));
  const items = [
    ["Last scan", latest.scan_ts ? when(latest.scan_ts) : "–", stale ? "bad" : "ok"],
    ["Mode", latest.mode === "dry-run" ? "learning run (no email)" : latest.mode],
    ["Coverage", `${h.coverage_pct ?? "–"}% of ${h.queries_planned ?? "–"} queries`, (h.coverage_pct ?? 100) < 80 ? "bad" : "ok"],
    ["Requests sent", `${h.queries_attempted ?? "–"} of ${h.budget_max ?? "–"} budget`],
    ["Fetch errors", h.fetch_error_count, h.fetch_error_count ? "bad" : "ok"],
    ["Blocked by Google", h.blocked ? "yes" : "no", h.blocked ? "bad" : "ok"],
    ["Candidates today", h.candidates ?? "–"],
    ["Lodging checks today", h.pass2_checks != null ? `${h.pass2_checks} (${h.serpapi_lookups ?? 0} lookups)` : "–"],
    ["SerpApi this month", `${h.serpapi_used_this_month ?? 0} of ${h.serpapi_cap ?? 200} lookups`],
    ["Cache hits", h.cache_hits],
    ["Skipped (budget)", h.budget_skipped],
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
    el("p", { class: "sheet-foot" }, "Every trip this scan logged, with the evidence behind each number: ",
      el("a", { href: "table.html", text: "Scoring table" }), " · ", el("a", { href: "data/history/latest.csv", download: "", text: "download CSV" })),
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
  $("sort").addEventListener("change", (e) => { store.set("radar.sort", e.target.value); sortCards(e.target.value, true); });
  // The frame sticks under the paper. A one-pixel sentinel at the paper's top edge tells the bar when to turn to paper (64 px
  // from the top), the frame when its words give way (the fallback where CSS cannot read the scroll) and when it is covered.
  const bar = $("bar"), frame = $("frame"), edge = document.querySelector(".frame-end");
  if ("IntersectionObserver" in window) {
    const watch = (rootMargin, node, cls) => new IntersectionObserver(([e]) => {
      node.classList.toggle(cls, !e.isIntersecting && e.boundingClientRect.top < (e.rootBounds ? e.rootBounds.top : 0));
    }, { rootMargin }).observe(edge);
    watch("-64px 0px 0px 0px", bar, "on-paper");
    watch("-50% 0px 0px 0px", frame, "past");
    watch("0px", frame, "gone");
  } else {
    const paper = () => bar.classList.toggle("on-paper", window.scrollY > frame.offsetHeight - 64);
    window.addEventListener("scroll", paper, { passive: true });
    paper();
  }
  const [latest, series, index, digests] = await Promise.all([
    getJSON("data/latest.json"), getJSON("data/series.json"), getJSON("hits/index.json"), getJSON("data/digests/index.json"),
  ]);
  if (!latest) {
    $("scan-age").textContent = "No scan yet";
    $("verdict-h").textContent = "No scan published yet.";
    $("lead").textContent = "The collector runs every morning at 04:17 Calgary and publishes its results here.";
    $("cities-sec").hidden = true;   // the skeleton has nothing to become
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

  const rows = (index || []).filter((r) => r.pass != null);   // v2 index rows only
  renderVerdict(latest, rows, stale);
  renderPassed(latest, rows);
  renderCities(latest, series || {});
  renderHealth(latest, stale);
  renderNotes(digests || []);
}

main();
