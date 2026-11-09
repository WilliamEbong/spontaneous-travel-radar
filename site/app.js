// Travel Radar dashboard: vanilla JS, reads the JSON the collector commits. All data text goes in via textContent.
"use strict";

const TZ = "America/Edmonton";
const STALE_HOURS = 30;

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

const money = (n) => (n == null ? "–" : "$" + Math.round(n).toLocaleString("en-CA"));
const fmt = (iso, opts) => new Intl.DateTimeFormat("en-CA", { timeZone: TZ, ...opts }).format(new Date(iso));
const when = (iso) => fmt(iso, { weekday: "short", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
const day = (d) => new Intl.DateTimeFormat("en-CA", { timeZone: "UTC", month: "short", day: "numeric" }).format(new Date(d + "T12:00:00Z"));

function bandPill(band) {
  return el("span", { class: `pill band-${band}`, text: band });
}

function flightsLink(r) {
  const apt = r.airport.split("/")[0];
  const q = `Flights to ${apt} from YYC on ${r.dates.out_dep.slice(0, 10)} through ${r.dates.back_dep.slice(0, 10)}`;
  return "https://www.google.com/travel/flights?q=" + encodeURIComponent(q);
}

// ---- sparkline: 2px line, end dot, crosshair + tooltip on hover/focus (dataviz skill) ----
const tip = () => $("tip");
function showTip(x, y, value, label) {
  const t = tip();
  t.replaceChildren(el("strong", { text: value }), " ", el("span", { class: "small", text: label }));
  t.hidden = false;
  const w = t.offsetWidth;
  t.style.left = Math.min(window.innerWidth - w - 8, Math.max(8, x - w / 2)) + "px";
  t.style.top = y - 40 + "px";
}
function hideTip() { tip().hidden = true; }

function sparkline(points, cityName) {
  const W = 120, H = 32, P = 4;
  if (!points || !points.length) return el("span", { class: "small", text: "no history yet" });
  const vals = points.map((p) => p[1]);
  const lo = Math.min(...vals), hi = Math.max(...vals);
  const x = (i) => (points.length === 1 ? W - P : P + (i * (W - 2 * P)) / (points.length - 1));
  const y = (v) => (hi === lo ? H / 2 : P + ((hi - v) * (H - 2 * P)) / (hi - lo));
  const last = points[points.length - 1];
  const svg = svgEl("svg", { class: "spark", width: W, height: H, viewBox: `0 0 ${W} ${H}`, tabindex: "0", role: "img",
    "aria-label": `${cityName}: cheapest fare per person over ${points.length} scan days, latest ${money(last[1])}, low ${money(lo)}, high ${money(hi)}` });
  const cross = svgEl("line", { class: "cross", y1: 0, y2: H, visibility: "hidden" });
  svg.append(cross);
  if (points.length > 1) svg.append(svgEl("path", { class: "line", d: points.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p[1]).toFixed(1)}`).join("") }));
  svg.append(svgEl("circle", { class: "dot", cx: x(points.length - 1), cy: y(last[1]), r: 4 }));
  const at = (i) => {
    const r = svg.getBoundingClientRect();
    cross.setAttribute("x1", x(i)); cross.setAttribute("x2", x(i)); cross.setAttribute("visibility", "visible");
    showTip(r.left + (x(i) / W) * r.width, r.top, money(points[i][1]) + " pp", day(points[i][0]));
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

// ---- tiny, safe markdown for the templated briefs: headings, bullets, **bold**, [text](https://...) ----
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
function renderMd(md) {
  const box = el("div", { class: "brief" });
  let ul = null;
  for (const line of md.split("\n")) {
    if (line.startsWith("- ")) {
      if (!ul) box.append((ul = el("ul")));
      const li = el("li"); inline(li, line.slice(2)); ul.append(li);
      continue;
    }
    ul = null;
    if (!line.trim()) continue;
    const h = line.match(/^(#{1,2}) (.*)/);
    const n = el(h ? (h[1].length === 1 ? "h3" : "h4") : "p");
    inline(n, h ? h[2] : line);
    box.append(n);
  }
  return box;
}
const hitLabel = (r) => ` · ${r.id.slice(r.id.indexOf(r.city) + r.city.length + 1).replace("_", " ")} · score ${r.score} · trip ${money(r.total_cad)}`;
function briefList(rows, emptyText, label = hitLabel) {
  if (!rows.length) return el("p", { class: "empty", text: emptyText });
  const card = el("div", { class: "card" });
  for (const r of rows) {
    const d = el("details", { class: "item" },
      el("summary", {}, el("span", { class: "city", text: r.city_name }), label(r)));
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

// ---- sections ----
function renderBest(latest, series) {
  const rows = latest.best_by_city || [];
  if (!rows.length) return $("best").replaceChildren(el("p", { class: "empty", text: "No in-window trips found in the last scan." }));
  const head = ["City", "Trip (Calgary time)", "Flights for 2", "Band", "vs history", "Score", "Trip total", "Last 30 days"];
  const tbody = el("tbody");
  for (const r of rows) {
    const stops = r.stops.every((s) => s === 0) ? "non-stop" : `${r.stops.join("/")} stops`;
    const cells = [
      el("td", { class: "lead" }, el("span", { class: "city", text: r.city_name }), el("div", { class: "small", text: `${r.airport} · ${r.airlines} · ${stops}` })),
      el("td", { "data-label": head[1] }, el("span", {},
        el("span", { text: `Leave ${when(r.dates.out_dep)}` }), el("br"),
        el("span", { text: `Home ${when(r.dates.back_arr)}` }), el("br"),
        el("a", { href: flightsLink(r), rel: "noopener", target: "_blank", class: "small", text: "Google Flights" }))),
      el("td", { "data-label": head[2], class: "num" }, el("span", {}, el("span", { text: money(r.flights_cad_2pax) }), el("div", { class: "small", text: `${money(r.price_pp)} pp` }))),
      el("td", { "data-label": head[3] }, bandPill(r.band)),
      el("td", { "data-label": head[4], class: "num", text: r.history_pct == null ? "building" : `${Math.round(r.history_pct)}th pct` }),
      el("td", { "data-label": head[5], class: "num", text: String(r.score) }),
      el("td", { "data-label": head[6], class: "num" }, el("span", {}, el("span", { text: money(r.total_cad) }), el("div", { class: "small", text: `bar ${money(r.bar_cad)}` }))),
      el("td", { "data-label": head[7] }, sparkline(series[r.city], r.city_name)),
    ];
    tbody.append(el("tr", {}, ...cells));
  }
  const thead = el("thead", {}, el("tr", {}, ...head.map((h, i) => el("th", { class: [2, 4, 5, 6].includes(i) ? "num" : null, scope: "col", text: h }))));
  $("best").replaceChildren(el("div", { class: "card" }, el("table", { class: "stack" }, thead, tbody)));
}

function renderHealth(latest) {
  const h = latest.health || {};
  const names = Object.fromEntries((latest.cities || []).map((c) => [c.key, c.name]));
  const items = [
    ["Last scan", latest.scan_ts ? when(latest.scan_ts) : "–"],
    ["Mode", latest.mode === "dry-run" ? "dry-run (learning, no alerts)" : latest.mode],
    ["Host", h.host], ["Duration", h.duration_s != null ? `${Math.round(h.duration_s / 60)} min` : "–"],
    ["Coverage", `${h.coverage_pct ?? "–"}% of ${h.queries_planned ?? "–"} queries`],
    ["Requests sent", `${h.queries_attempted ?? "–"} of ${h.budget_max ?? "–"} budget`],
    ["Cache hits", h.cache_hits], ["Skipped (budget)", h.budget_skipped],
    ["Fetch errors", h.fetch_error_count, h.fetch_error_count ? "bad" : "ok"],
    ["Blocked by Google", h.blocked ? "yes" : "no", h.blocked ? "bad" : "ok"],
    ["SerpApi this month", `${h.serpapi_used_this_month ?? 0} of ${h.serpapi_cap ?? 60}`],
    ["Events", h.events_source],
    ["No non-stop found", (h.no_nonstop || []).map((k) => names[k] || k).join(", ") || "none"],
  ];
  const dl = el("dl", { class: "health card" });
  for (const [k, v, st] of items) dl.append(el("div", {}, el("dt", { text: k }), el("dd", { class: st ? `status-${st}` : null, text: v == null ? "–" : String(v) })));
  const errs = (h.fetch_errors || []).slice(0, 5);
  $("health").replaceChildren(dl, errs.length
    ? el("ul", { class: "small" }, ...errs.map((e) => el("li", { text: `${e.route} ${e.day}: ${e.error}` })))
    : "");
}

function renderHistory(series, cities) {
  const names = Object.fromEntries((cities || []).map((c) => [c.key, c.name]));
  const days = [...new Set(Object.values(series).flat().map((p) => p[0]))].sort().slice(-10);
  if (!days.length) return $("history").replaceChildren(el("p", { class: "empty", text: "No history yet." }));
  const thead = el("thead", {}, el("tr", {}, el("th", { scope: "col", text: "City" }), ...days.map((d) => el("th", { class: "num", scope: "col", text: day(d) }))));
  const tbody = el("tbody");
  for (const [city, pts] of Object.entries(series)) {
    const m = Object.fromEntries(pts);
    tbody.append(el("tr", {}, el("th", { scope: "row", text: names[city] || city }), ...days.map((d) => el("td", { class: "num", text: m[d] ? money(m[d]) : "–" }))));
  }
  $("history").replaceChildren(el("div", { class: "card", style: "overflow-x:auto" }, el("table", {}, thead, tbody)));
}

async function main() {
  const [latest, series, hits, digests] = await Promise.all([
    getJSON("data/latest.json"), getJSON("data/series.json"), getJSON("hits/index.json"), getJSON("data/digests/index.json"),
  ]);
  if (!latest) {
    $("scan-meta").textContent = "No scan has been published yet.";
    return;
  }
  const ageH = (Date.now() - new Date(latest.scan_ts)) / 3.6e6;
  $("scan-meta").textContent = `Last scan ${when(latest.scan_ts)} (${ageH < 1 ? "under an hour" : Math.round(ageH) + " h"} ago)`;
  const notes = [];
  if (ageH > STALE_HOURS) notes.push(`The last scan is ${Math.round(ageH)} hours old: the daily run may have failed.`);
  if (latest.mode === "dry-run") notes.push("Learning run: everything is logged, nothing alerts.");
  if (notes.length) { $("banner").textContent = notes.join(" "); $("banner").hidden = false; }

  renderBest(latest, series || {});
  const all = hits || [];
  $("hits").replaceChildren(briefList(all.filter((h) => h.mode === "live" && h.is_hit), "No live hits yet."));
  $("dry").replaceChildren(briefList(all.filter((h) => h.mode === "dry-run").sort((a, b) => b.is_hit - a.is_hit), "Nothing would have fired yet."));
  $("digests").replaceChildren((digests || []).length
    ? briefList(digests.map((d) => ({ city_name: `Week of ${d.date}`, path_md: d.path })), "", () => "")
    : el("p", { class: "empty", text: "No digests yet (first one on a Monday)." }));
  renderHealth(latest);
  renderHistory(series || {}, latest.cities);
}

main();
