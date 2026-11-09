"""JSON the dashboard and the daily routine read: latest, series, indexes, weekly summary. All writes atomic."""
import json
import os
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from radar.config import City, Reference
from radar.score import Scored


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
    """{city: [[scan_date, cheapest price_pp that day], ...]} for the last `days` scan days, day-off trips only (the
    sparkline compares like with like: weekend trips are short-lead and non-stop only)."""
    lo: dict[str, dict[str, int]] = defaultdict(dict)
    for r in dayoff_rows(history):
        d = lo[r["city"]]
        d[r["scan_date"]] = min(d.get(r["scan_date"], r["price_pp"]), r["price_pp"])
    write_json(path, {c: sorted(v.items())[-days:] for c, v in sorted(lo.items())})


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
        }
    write_json(Path(root) / "index.json", sorted(rows.values(), key=lambda r: r["created"], reverse=True))


def write_digests_index(root="data/digests") -> None:
    files = sorted(Path(root).glob("*.md"), reverse=True)
    write_json(Path(root) / "index.json", [{"date": p.stem, "path": p.as_posix()} for p in files])


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
