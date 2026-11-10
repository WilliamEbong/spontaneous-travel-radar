"""Append-only JSONL quote history (data/history/YYYY-MM-DD.jsonl) and the route percentile."""
import json
from datetime import date, timedelta
from pathlib import Path

from radar.score import Scored, components_dict


def quote_row(x: Scored, scan_date: date, scan_ts: str, winner: bool, *, pass_: int = 1, candidate_id: str | None = None) -> dict:
    """One logged quote. score/share/price_pts are pass 1 (lodging estimated); pass says how far the trip got in this
    scan (2 = real lodging checked), candidate_id names its file in hits/candidates/; final_score is pass 3, which the
    routine writes to hits/ only, so it stays null here (FR-309)."""
    t = x.trip
    return {
        "scan_date": scan_date.isoformat(), "scan_ts": scan_ts, "city": t.city_key, "airport": t.airport,
        "window_id": t.window_id, "trip_class": t.trip_class, "out_dep": t.out.dep.isoformat(), "out_arr": t.out.arr.isoformat(),
        "back_dep": t.back.dep.isoformat(), "back_arr": t.back.arr.isoformat(),
        "airlines": "+".join(dict.fromkeys(t.out.airlines + t.back.airlines)),
        "stops_out": t.out.stops, "stops_back": t.back.stops, "flights_cad_2pax": t.flights_cad_2pax,
        "price_pp": x.price_pp, "ladder": x.ladder, "nights": t.nights, "total_cad": round(x.total_cad),
        "lodging_cad": round(x.lodging_cad), "typical_cad": round(x.typical_cad),   # the price line's figures (scoring table)
        "share": x.share, "score": x.score, "candidate": x.candidate, "winner": winner,
        "pass": pass_, "final_score": None, "candidate_id": candidate_id,
        # the backtest (docs/TUNING-PLAN.md) re-scores a variant as score - price_pts + new price points
        "price_pts": round(x.components.price, 2),
        "history_pct": None if x.history_pct is None else round(x.history_pct, 1),
        # every number behind the score and what it was computed from, so a later re-score or a display change never
        # needs the fares fetched again (William, 2026-11-10: "save not just the score but the numbers and reasons")
        "components": components_dict(x), "inputs": x.inputs,
    }


def append_quotes(day: date, rows: list[dict], root="data/history") -> Path:
    p = Path(root) / f"{day.isoformat()}.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.writelines(json.dumps(r, separators=(",", ":")) + "\n" for r in rows)
    return p


def read_history(days: int = 90, root="data/history", today: date | None = None) -> list[dict]:
    since = (today or date.today()) - timedelta(days=days)
    rows = []
    for p in sorted(Path(root).glob("*.jsonl")):
        if date.fromisoformat(p.stem) >= since:
            rows += [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]
    return rows


def route_percentile(price_pp: int, city_key: str, history: list[dict], *, min_days: int = 14) -> float | None:
    """% of this city's logged prices <= price_pp; None until min_days distinct scan days exist."""
    prices = [r["price_pp"] for r in history if r.get("city") == city_key]
    if len({r["scan_date"] for r in history if r.get("city") == city_key}) < min_days:
        return None
    return 100 * sum(p <= price_pp for p in prices) / len(prices)
