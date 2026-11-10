"""JSON the dashboard and the daily routine read: latest, series, indexes, weekly summary. All writes atomic."""
import csv
import io
import json
import os
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from radar.config import City, Reference
from radar.score import Scored, breakdown, breakdown_of


def write_json(path, obj) -> None:
    """Temp file + os.replace: a crash never leaves a partial file (Review Focus 3)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1), encoding="utf-8")
    os.replace(tmp, p)


def _row(x: Scored, city: City, passes: dict) -> dict:
    t = x.trip
    pass_, cid = passes.get(id(x), (1, None))
    return {
        "city": t.city_key, "city_name": city.name, "airport": t.airport, "window_id": t.window_id,
        "trip_class": t.trip_class,
        "dates": {"out_dep": t.out.dep.isoformat(), "out_arr": t.out.arr.isoformat(),
                  "back_dep": t.back.dep.isoformat(), "back_arr": t.back.arr.isoformat(),
                  "check_in": t.check_in.isoformat(), "check_out": t.check_out.isoformat(), "nights": t.nights},
        "airlines": "+".join(dict.fromkeys(t.out.airlines + t.back.airlines)),
        "flights_cad_2pax": t.flights_cad_2pax, "price_pp": x.price_pp, "ladder": x.ladder,
        "lodging_cad": round(x.lodging_cad), "total_cad": round(x.total_cad), "typical_cad": round(x.typical_cad),
        "share": x.share, "score": x.score, "candidate": x.candidate, "pass": pass_, "final_score": None,
        "candidate_id": cid, "history_pct": None if x.history_pct is None else round(x.history_pct, 1),
        "hours_on_ground": round(t.hours_on_ground, 1), "stops": [t.out.stops, t.back.stops],
        "breakdown": breakdown_of(x),   # the pass-1 score, criterion by criterion (D-75)
    }


def write_latest(winners: list[Scored], cities: list[City], refs: dict[str, Reference], health: dict, *, scan_date: date,
                 scan_ts: str, mode: str, candidates: list[str], passes: dict, classes: dict | None = None,
                 path="data/latest.json") -> None:
    """windows: the top-scoring trip per city-window (both classes); best_by_city: each city's top score (FR-315).
    passes: id(winner) -> (pass reached, candidate id). Top-level keys are the v1 ones (hits stays, now always empty:
    hits come from the routine's pass 3 and are listed in hits/index.json)."""
    by_key = {c.key: c for c in cities}
    order = lambda r: (-r["score"], r["total_cad"])  # noqa: E731
    rows = sorted((_row(x, by_key[x.trip.city_key], passes) for x in winners), key=order)
    best: dict[str, dict] = {}
    for r in rows:
        best.setdefault(r["city"], r)
    write_json(path, {
        "scan_date": scan_date.isoformat(), "scan_ts": scan_ts, "mode": mode,
        "best_by_city": sorted(best.values(), key=order), "windows": rows,
        "cities": [{"key": c.key, "name": c.name, "tier": c.tier, "rank": c.rank, "ladder": refs[c.key].flights,
                    "confidence": refs[c.key].confidence, "nonstop": refs[c.key].nonstop} for c in cities],
        "hits": [], "candidates": candidates, "health": health,
        "classes": classes or {},   # per class: enabled, thresholds, and the day-off lead time, for the page's copy
    })


def dayoff_rows(history: list[dict]) -> list[dict]:
    """Rows logged before the trip classes existed have no trip_class and were all day-off trips."""
    return [r for r in history if r.get("trip_class", "dayoff") == "dayoff"]


def write_series(history: list[dict], path="data/series.json", days: int = 30) -> None:
    """{city: {trip_class: [[scan_date, cheapest price_pp that day], ...]}} for the last `days` scan days, one line per
    class (a weekend card's history must not mix with day-off fares: different lead times and rules)."""
    lo: dict[str, dict[str, dict[str, int]]] = defaultdict(lambda: defaultdict(dict))
    for r in history:
        d = lo[r["city"]][r.get("trip_class", "dayoff")]
        d[r["scan_date"]] = min(d.get(r["scan_date"], r["price_pp"]), r["price_pp"])
    write_json(path, {c: {k: sorted(v.items())[-days:] for k, v in sorted(cls.items())} for c, cls in sorted(lo.items())})


def hit_files(root="hits"):
    """(path, dict) for every v2 file under hits/ (candidates, near misses, hits); older formats are skipped."""
    for p in sorted(Path(root).glob("**/*.json")):
        if p.name != "index.json":
            h = json.loads(p.read_text(encoding="utf-8"))
            if "pass1" in h:
                yield p, h


def write_hits_index(root="hits") -> None:
    """One row per candidate id: the pass-3 result when it exists, else the candidate file (stage candidate, or
    near_miss when it was dropped after pass 2)."""
    rows: dict[str, dict] = {}
    for p, h in hit_files(root):
        if h["id"] in rows and rows[h["id"]]["pass"] == 3:
            continue
        p3 = h.get("pass3")
        rows[h["id"]] = {
            "id": h["id"], "city": h["city"], "city_name": h["city_name"], "window_id": h["window_id"],
            "trip_class": h["trip_class"], "mode": h["mode"], "stage": h["stage"], "status": h["status"],
            "is_hit": h["is_hit"], "scan_date": h["scan_date"], "pass": 3 if p3 else 2,
            "score_p1": h["pass1"]["score"], "score_p2": h["pass2"]["score"], "events_pts": p3["events_pts"] if p3 else None,
            "final_score": h["final_score"], "score": h["score"], "hit_threshold": h["hit_threshold"],
            "flights_cad_2pax": h["flights"]["cad_2pax"], "price_pp": h["flights"]["price_pp"], "ladder": h["ladder"]["label"],
            "total_cad": h["total_cad"], "lodging_source": (p3 or h["pass2"])["lodging_source"],
            "drop_reason": h.get("drop_reason"), "created": h["created"],
            "path_json": p.as_posix(), "path_md": p.with_suffix(".md").as_posix(),
            "breakdown": h.get("breakdown"),   # the latest pass's rows (None for a file written before D-75)
        }
    write_json(Path(root) / "index.json", sorted(rows.values(), key=lambda r: r["created"], reverse=True))


def write_digests_index(root="data/digests") -> None:
    files = sorted(Path(root).glob("*.md"), reverse=True)
    write_json(Path(root) / "index.json", [{"date": p.stem, "path": p.as_posix()} for p in files])


# ---- scoring table (D-77): one CSV per scan day, flat, for the table page and for Excel ----

CRITERIA = ("price", "time", "convenience", "city", "weather")
CSV_COLUMNS = ["scan_date", "city", "trip_class", "window_id", "dates", "airlines", "stops_out", "stops_back", "flights_pp",
               "flights_for_two", "lodging_estimate", "total_for_two", "typical_trip", "share",
               *[f"{k}_{part}" for k in CRITERIA for part in ("pts", "input")],
               "score", "pass", "final_score", "candidate", "winner"]


def csv_row(r: dict) -> dict:
    """A history row flattened: the evidence lines are the same `breakdown` lines the dashboard shows. A row logged
    before D-76 (no components or inputs) keeps its price points and leaves the other criteria blank."""
    inputs, comps, total, share = r.get("inputs"), r.get("components"), r.get("total_cad"), r.get("share")   # v1 rows: none
    typical = r.get("typical_cad") or (round(total / share) if total and share else None)
    lines = {}
    if inputs and comps and typical:
        lines = {b["key"]: b["input"] for b in breakdown(inputs, comps, total_cad=total, typical_cad=typical, share=share)}
    pts = {k: (comps or {}).get(k, r.get("price_pts") if k == "price" else None) for k in CRITERIA}
    yes = lambda v: "yes" if v else "no"  # noqa: E731
    nights = r.get("nights") or (date.fromisoformat(r["back_arr"][:10]) - date.fromisoformat(r["out_dep"][:10])).days
    return {
        "scan_date": r["scan_date"], "city": (inputs or {}).get("city_name") or r["city"].replace("_", " ").title(),
        "trip_class": r.get("trip_class", "dayoff"), "window_id": r["window_id"],
        "dates": f"{r['out_dep'][:10]} to {r['back_arr'][:10]} ({nights} night{'s' if nights != 1 else ''})", "airlines": r["airlines"],
        "stops_out": r["stops_out"], "stops_back": r["stops_back"], "flights_pp": r["price_pp"], "flights_for_two": r["flights_cad_2pax"],
        "lodging_estimate": r.get("lodging_cad"), "total_for_two": total, "typical_trip": typical, "share": share,
        **{f"{k}_pts": pts[k] for k in CRITERIA}, **{f"{k}_input": lines.get(k) for k in CRITERIA},
        "score": r["score"], "pass": r.get("pass", 1), "final_score": r.get("final_score"),
        "candidate": yes(r.get("candidate")), "winner": yes(r.get("winner")),
    }


def write_csv(path, rows: list[dict]) -> None:
    """UTF-8 with a BOM (Excel then reads the accents and the degree sign), text fields quoted, atomic like write_json."""
    buf = io.StringIO()
    w = csv.DictWriter(buf, CSV_COLUMNS, quoting=csv.QUOTE_NONNUMERIC, lineterminator="\n")
    w.writeheader()
    w.writerows({k: ("" if v is None else v) for k, v in csv_row(r).items()} for r in rows)
    p = Path(path)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_bytes(buf.getvalue().encode("utf-8-sig"))   # bytes: text mode on Windows would turn the LF into CRLF
    os.replace(tmp, p)


def write_history_csvs(root="data/history") -> list[dict]:
    """Every scan day's CSV beside its JSONL, latest.csv (the newest day) and index.json (newest first). Rebuilt
    whole each time: the lines come from the current code, so a wording change reaches every day's file."""
    index, newest = [], None
    for p in sorted(Path(root).glob("*.jsonl"), reverse=True):
        rows = [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]
        write_csv(p.with_suffix(".csv"), rows)
        newest = rows if newest is None else newest
        index.append({"date": p.stem, "path": p.with_suffix(".csv").as_posix(), "rows": len(rows)})
    if newest is not None:
        write_csv(Path(root) / "latest.csv", newest)
    write_json(Path(root) / "index.json", index)
    return index


def _pct(sorted_vals: list, q: float):
    return sorted_vals[min(len(sorted_vals) - 1, int(q * len(sorted_vals)))] if sorted_vals else None


def write_weekly_summary(history: list[dict], hits_root="hits", path="data/weekly-summary.json",
                         latest_path="data/latest.json", today: date | None = None) -> None:
    """Compact input for the daily routine: what reached each pass, ladder spread, fares vs the ladders, health."""
    today = today or date.today()
    since = (today - timedelta(days=7)).isoformat()
    week = [r for r in history if r["scan_date"] >= since]   # both classes: both allow basic fares since v2 (D-70)
    winners = [r for r in week if r.get("winner")]
    ladders: dict[str, Counter] = defaultdict(Counter)
    prices: dict[str, list[int]] = defaultdict(list)
    shares: dict[str, list[float]] = defaultdict(list)
    nonstop: dict[str, list[bool]] = defaultdict(list)
    for r in winners:
        ladders[r["city"]][r.get("ladder", r.get("band"))] += 1
        if r.get("share") is not None:
            shares[r["city"]].append(r["share"])
    for r in week:
        prices[r["city"]].append(r["price_pp"])
        nonstop[r["city"]].append(r["stops_out"] == 0 and r["stops_back"] == 0)
    files = [h for _, h in hit_files(hits_root) if h["scan_date"] >= since]
    latest = {h["id"]: h for h in sorted(files, key=lambda h: h.get("pass3") is not None)}   # pass 3 overrides the candidate
    stages = Counter(h["stage"] for h in latest.values())
    latest_json = json.loads(Path(latest_path).read_text(encoding="utf-8")) if Path(latest_path).exists() else {}
    cities = sorted(set(prices))
    q = lambda v, x: _pct(sorted(v), x)  # noqa: E731
    write_json(path, {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "period": [since, today.isoformat()], "scan_days": len({r["scan_date"] for r in week}),
        "history_days_total": len({r["scan_date"] for r in history}),
        "passes": {"candidates": len(latest), "awaiting_pass3": stages["candidate"], "near_misses": stages["near_miss"],
                   "hits": stages["hit"], "pass2_lookups": sum(h["pass2"]["searches"] for h in latest.values())},
        "hits": [{"id": h["id"], "final_score": h["final_score"], "total_cad": h["total_cad"], "trip_class": h["trip_class"]}
                 for h in latest.values() if h["is_hit"]],
        "near_misses": [{"id": h["id"], "score": h["score"], "pass": 3 if h.get("pass3") else 2, "why": h.get("drop_reason")}
                        for h in latest.values() if h["stage"] == "near_miss"],
        "ladder_distribution": {c: dict(ladders[c]) for c in cities},
        "share_of_typical": {c: {"min": min(shares[c]), "p25": q(shares[c], 0.25), "p50": q(shares[c], 0.5)}
                             for c in cities if shares[c]},
        "price_pp": {c: {"min": min(prices[c]), "p10": q(prices[c], 0.1), "p25": q(prices[c], 0.25),
                         "p50": q(prices[c], 0.5), "p90": q(prices[c], 0.9)} for c in cities},
        "nonstop_share": {c: round(sum(nonstop[c]) / len(nonstop[c]), 2) for c in cities},
        "request_health": latest_json.get("health", {}),
    })
