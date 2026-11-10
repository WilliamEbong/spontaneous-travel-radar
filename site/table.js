// Travel Radar scoring table (D-77): one scan day's CSV (data/history/<day>.csv) as a sortable, filterable table.
// Vanilla JS, no build step; every cell goes in via textContent.
"use strict";

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

const PATTERN = { "fri-off": "Fri off", "mon-off": "Mon off", "stat-thu-4d": "Thu stat, 4 days", "stat-tue-4d": "Tue stat, 4 days", weekend: "Fri to Sun" };
const CLASS = { weekend: "No day off needed", dayoff: "Needs a day off" };
const CRITERIA = [["price", "Price"], ["time", "Time there"], ["convenience", "Convenience"], ["city", "City"], ["weather", "Weather"]];
const money = (s) => (s === "" ? "–" : "$" + Math.round(Number(s)).toLocaleString("en-CA"));
const num = (s) => (s === "" ? null : Number(s));
const pts = (s) => (s === "" ? "–" : (Number.isInteger(Number(s)) ? s : Number(s).toFixed(1)).replace("-", "−"));
const dayOf = (d) => new Intl.DateTimeFormat("en-GB", { timeZone: "UTC", weekday: "short", day: "numeric", month: "short" }).format(new Date(d + "T12:00:00Z"));
function stopsText(out, back) {
  if (!out && !back) return "non-stop";
  if (out && back) return `${out} stop each way`;
  return out ? `${out} stop out` : `${back} stop back`;
}

// RFC 4180: quoted fields may hold commas, quotes ("") and newlines. Returns one object per row, keyed by the header.
function parseCSV(text) {
  const rows = [[]];
  let field = "", quoted = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (quoted) {
      if (c !== '"') field += c;
      else if (text[i + 1] === '"') { field += '"'; i++; }
      else quoted = false;
    } else if (c === '"') quoted = true;
    else if (c === ",") { rows[rows.length - 1].push(field); field = ""; }
    else if (c === "\n") { rows[rows.length - 1].push(field); field = ""; rows.push([]); }
    else if (c !== "\r") field += c;
  }
  if (field !== "" || rows[rows.length - 1].length) rows[rows.length - 1].push(field);
  if (!rows[rows.length - 1].length) rows.pop();
  const [head, ...body] = rows;
  return body.map((r) => Object.fromEntries(head.map((h, i) => [h, r[i] ?? ""])));
}

// ---- columns: [header, cell builder, class]. The five criteria show the points and, under them, the evidence line. ----
let MAX = {};   // points per criterion, from the dashboard's breakdown rows (config/scoring.yaml weights)
const COLUMNS = [
  ["City", (r) => r.city, "c-city"],
  ["Class", (r) => el("span", { class: `cls cls-${r.trip_class}`, text: CLASS[r.trip_class] || r.trip_class })],
  ["Window", (r) => PATTERN[r.window_id.split("_")[1]] || r.window_id],
  ["Dates", (r) => r.dates],
  ["Flights", (r) => `${r.airlines} · ${stopsText(num(r.stops_out), num(r.stops_back))}`],
  ["Fare pp", (r) => money(r.flights_pp), "num"],
  ["Flights for two", (r) => money(r.flights_for_two), "num"],
  ["Lodging est.", (r) => money(r.lodging_estimate), "num"],
  ["Total for two", (r) => money(r.total_for_two), "num"],
  ["Typical trip", (r) => money(r.typical_trip), "num"],
  ["Share", (r) => (r.share === "" ? "–" : `${Math.round(Number(r.share) * 100)}%`), "num"],
  ...CRITERIA.map(([k, label]) => [label, (r) => el("span", { class: "crit" },
    el("b", { text: pts(r[`${k}_pts`]) + (MAX[k] != null && r[`${k}_pts`] !== "" ? ` / ${MAX[k]}` : "") }),
    r[`${k}_input`] ? el("span", { class: "in", text: r[`${k}_input`] }) : null), "c-crit"]),
  ["Score", (r) => el("b", { text: r.score }), "num c-score"],
  ["Pass", (r) => r.pass || "1", "num"],
  ["Final", (r) => r.final_score || "–", "num"],
  ["Candidate", (r) => r.candidate],
  ["Winner", (r) => r.winner],
];
const SORT = {
  score: (a, b) => num(b.score) - num(a.score) || (num(a.total_for_two) ?? num(a.flights_for_two)) - (num(b.total_for_two) ?? num(b.flights_for_two)),
  price: (a, b) => (num(a.total_for_two) ?? num(a.flights_for_two)) - (num(b.total_for_two) ?? num(b.flights_for_two)) || num(b.score) - num(a.score),
  city: (a, b) => a.city.localeCompare(b.city) || num(b.score) - num(a.score),
  class: (a, b) => (a.trip_class === "weekend" ? 0 : 1) - (b.trip_class === "weekend" ? 0 : 1) || num(b.score) - num(a.score),
};

let rows = [];
function render() {
  const by = document.querySelector("#sort input:checked").value;
  const q = $("q").value.trim().toLowerCase();
  const shown = rows.filter((r) => !q || r._text.includes(q)).sort(SORT[by]);
  const tbody = el("tbody");
  for (const r of shown) {
    const tr = el("tr", { class: `c-${r.trip_class}${r.winner === "yes" ? " is-winner" : ""}` });
    COLUMNS.forEach(([, cell, cls], i) => tr.append(el(i ? "td" : "th", { scope: i ? null : "row", class: cls }, cell(r))));
    tbody.append(tr);
  }
  $("tbl").tBodies[0].replaceWith(tbody);
  $("count").textContent = q ? `${shown.length} of ${rows.length} trips` : `${rows.length} trips`;
}

async function load(day, path) {
  const text = await getText(path);
  const tbl = $("tbl");
  if (text == null) {
    rows = [];
    tbl.tBodies[0].replaceChildren(el("tr", {}, el("td", { colspan: COLUMNS.length, class: "empty-cell", text: "This day's table could not be loaded." })));
    $("count").textContent = "";
    return;
  }
  rows = parseCSV(text.replace(/^﻿/, ""));
  for (const r of rows) r._text = Object.values(r).join(" ").toLowerCase();
  tbl.tHead.replaceChildren(el("tr", {}, ...COLUMNS.map(([h, , cls]) => el("th", { scope: "col", class: cls, text: h }))));
  $("dl").href = path;
  $("dl").download = `travel-radar-${day}.csv`;
  $("hint").textContent = `Every trip the scan of ${dayOf(day)} logged, one row each: the evidence behind each number, the points it earned per criterion, and the score they add up to. Scroll sideways for the full row; the city stays put. Rows from before the numbers were kept show the score and the price points only.`;
  render();
}

async function main() {
  const [index, latest] = await Promise.all([getJSON("data/history/index.json"), getJSON("data/latest.json")]);
  const bd = ((latest && latest.windows) || []).find((w) => w.breakdown);
  if (bd) MAX = Object.fromEntries(bd.breakdown.filter((b) => b.max).map((b) => [b.key, b.max]));
  const sel = $("day");
  if (!index || !index.length) {
    sel.replaceChildren(el("option", { text: "No scan yet" }));
    sel.disabled = true;
    $("tbl").tBodies[0].replaceChildren(el("tr", {}, el("td", { colspan: COLUMNS.length, class: "empty-cell",
      text: "No scoring table yet. The first scan after this page went live writes one, at 04:17 Calgary." })));
    $("hint").textContent = "Each scan writes a table of every trip it logged: the evidence behind each number, the points per criterion, and the score.";
    $("dl").hidden = true;
    return;
  }
  sel.replaceChildren(...index.map((d) => el("option", { value: d.date, text: `${dayOf(d.date)} · ${d.rows} trips` })));
  const wanted = new URLSearchParams(location.search).get("day");
  if (index.some((d) => d.date === wanted)) sel.value = wanted;
  const paths = Object.fromEntries(index.map((d) => [d.date, d.path]));
  const pick = () => { history.replaceState(null, "", `?day=${sel.value}`); load(sel.value, paths[sel.value]); };
  sel.addEventListener("change", pick);
  $("sort").addEventListener("change", render);
  $("q").addEventListener("input", render);
  pick();
}

main();
