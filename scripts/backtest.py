"""The replay harness of the self-tuning loop (docs/TUNING-PLAN.md (a) and (b), D-82).

    python scripts/backtest.py [--config config/scoring.yaml] [--references config/references.yaml]
                               [--until YYYY-MM-DD] [--holdout-days 7] [--json]

Offline and deterministic: it reads data/history/*.jsonl, config/cities.yaml and the two config files, and never
the network. Every logged winner (one per city-weekend per scan day) is judged again under the given config: its
flights ladder (rolling ladders only ever see the days before the row's own), the price points of its complete
trip against the route's typical trip, and the candidate gate. The judgements are scored in hindsight against
the lowest fare each weekend went on to show, and the script prints the hindsight price score with its parts.
--until replays the history as it stood on that day, so any stored score can be re-scored later.
"""
import argparse
import json
import sys
import time
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from radar.config import Scoring, load_cities, load_references, load_scoring  # noqa: E402
from radar.itineraries import hotel_dates  # noqa: E402
from radar.score import is_candidate, price_component, typical_trip_cad  # noqa: E402
from radar.store import read_history, rolling_flights  # noqa: E402

NEAR = 1.10          # near the eventual low: at most 10% above the lowest winner fare that weekend ever showed
MIN_OBS = 3          # a weekend counts once it has been priced on at least 3 scan days
BETA = 0.5           # F0.5: a flag that proved right weighs twice a low that was caught
HOLDOUT_DAYS = 7     # the most recent scan days: reported, never used to pick a trial
LABELS_MIN = 30      # book/skip taps in data/labels.jsonl before they blend into the score
NEEDED = ("winner", "share", "total_cad", "nights", "components", "inputs", "out_arr", "back_dep", "trip_class")


def load_rows(root="data/history", until: str | None = None) -> list[dict]:
    """Every logged row, oldest day first; --until stops at that scan day.
    ponytail: the whole history every trial; keep only the last ~180 days if a trial nears the 2-minute budget."""
    rows = read_history(36500, root=root, today=date.fromisoformat(until) if until else date.today())
    return [r for r in rows if until is None or r["scan_date"] <= until]


def load_labels(path="data/labels.jsonl") -> list[dict]:
    p = Path(path)
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()] if p.exists() else []


def settings(s: Scoring) -> dict:
    """The price-judgment settings a score was computed under: the inputs stored beside every score."""
    return {"ladder_mode": s.ladder_mode, "rolling_ladder": dict(s.rolling_ladder),
            "rolling_window_days": s.rolling_window_days, "rolling_min_days": s.rolling_min_days,
            "ladder_exclude_ranges": [[a.isoformat(), b.isoformat()] for a, b in s.ladder_exclude_ranges],
            "price_curve": s.price_curve, "weights": dict(s.weights),
            "candidate_threshold": {k: v["candidate_threshold"] for k, v in s.trip_classes.items()}}


def judge(rows: list[dict], s: Scoring, refs: dict, cities: dict) -> dict[tuple, dict]:
    """Every v2 winner judged again under s: {(city, window_id, scan_date): {price_pp, good, score, candidate}}.
    Only the price judgment moves: the other components are the logged ones, scaled when a weight changes."""
    by_route: dict[str, list] = {}
    for r in rows:
        by_route.setdefault(r["city"], []).append(r)
    ladders, out = {}, {}
    for r in rows:
        if not all(r.get(k) is not None for k in NEEDED) or not r["winner"] or r["city"] not in cities:
            continue
        k = (r["city"], r["scan_date"])
        if k not in ladders:   # from rows before this scan day only (rolling_flights), so no judgement sees its future
            ladders[k] = rolling_flights(by_route[r["city"]], date.fromisoformat(r["scan_date"]), s, refs[r["city"]].flights)
        lad = ladders[k]
        check_in = hotel_dates(SimpleNamespace(arr=datetime.fromisoformat(r["out_arr"])),
                               SimpleNamespace(dep=datetime.fromisoformat(r["back_dep"])))[0]
        typical = typical_trip_cad(SimpleNamespace(nights=r["nights"], check_in=check_in), cities[r["city"]],
                                   replace(refs[r["city"]], flights=lad), s)
        price = price_component(r["total_cad"], typical, s)[1]
        w0 = r["inputs"]["weights"]
        score = round(price + sum(v * s.weights[c] / w0[c] for c, v in r["components"].items() if c != "price"))
        out[(r["city"], r["window_id"], r["scan_date"])] = {
            "price_pp": r["price_pp"], "good": r["price_pp"] <= lad["good"], "score": score,
            "candidate": is_candidate(r["price_pp"], score, lad["good"], s.trip_classes[r["trip_class"]]["candidate_threshold"]),
        }
    return out


def lows(rows: list[dict]) -> dict[tuple, tuple[int, int]]:
    """(city, window_id) -> (lowest winner price_pp, scan days priced) over the given rows."""
    low, days = {}, {}
    for r in rows:
        if r.get("winner"):
            k = (r["city"], r["window_id"])
            low[k] = min(low.get(k, r["price_pp"]), r["price_pp"])
            days.setdefault(k, set()).add(r["scan_date"])
    return {k: (low[k], len(days[k])) for k in low}


def f_half(tp: int, fp: int, fn: int) -> float:
    b2 = BETA ** 2
    return (1 + b2) * tp / ((1 + b2) * tp + b2 * fn + fp) if tp else 0.0


def _term(tp, fp, fn) -> dict:
    return {"f": round(f_half(tp, fp, fn), 4), "precision": round(tp / (tp + fp), 4) if tp + fp else None,
            "recall": round(tp / (tp + fn), 4) if tp + fn else None, "tp": tp, "fp": fp, "fn": fn}


def part(judged: dict, low: dict, days: set) -> dict:
    """The hindsight price score of the judgements made on `days`, against the lows in `low`: the mean of two F0.5
    terms, deal (candidates) and ladder (good-or-better calls), on a 0-100 scale."""
    c = {"deal": [0, 0, 0], "ladder": [0, 0, 0]}   # tp, fp, fn
    n = near_n = good_n = cand_n = 0
    for (city, wid, day), j in judged.items():
        lo = low.get((city, wid))
        if day not in days or lo is None or lo[1] < MIN_OBS:
            continue
        near = j["price_pp"] <= NEAR * lo[0]
        n, near_n, good_n, cand_n = n + 1, near_n + near, good_n + j["good"], cand_n + j["candidate"]
        for term, flag in (("deal", j["candidate"]), ("ladder", j["good"])):
            if flag and near:
                c[term][0] += 1
            elif flag:
                c[term][1] += 1
            elif near:
                c[term][2] += 1
    terms = {t: _term(*v) for t, v in c.items()}
    return {"score": round(50 * (terms["deal"]["f"] + terms["ladder"]["f"]), 2), **terms, "judgements": n,
            "near_low": near_n, "good_rate": round(good_n / n, 4) if n else 0.0,
            "candidate_rate": round(cand_n / n, 4) if n else 0.0}


def label_part(labels: list[dict], judged: dict, days: set) -> dict:
    """F0.5 on "book", a positive prediction being a candidate. Each tap joins the winner judged for its city and
    window on the latest scan day on or before the tap (docs/TUNING-PLAN.md (b))."""
    seen: dict[tuple, list] = {}
    for city, wid, day in judged:
        seen.setdefault((city, wid), []).append(day)
    tp = fp = fn = n = 0
    for lab in labels:
        before = [d for d in seen.get((lab["city"], lab["window_id"]), []) if d <= str(lab["ts"])[:10]]
        if not before or max(before) not in days:
            continue
        cand, book = judged[(lab["city"], lab["window_id"], max(before))]["candidate"], lab["label"] == "book"
        n, tp, fp, fn = n + 1, tp + (cand and book), fp + (cand and not book), fn + (book and not cand)
    return {"score": round(100 * f_half(tp, fp, fn), 2), **_term(tp, fp, fn), "labels": n}


def evaluate(rows: list[dict], s: Scoring, refs: dict, cities: dict, *, holdout_days: int = HOLDOUT_DAYS,
             labels: list[dict] = ()) -> dict:
    """The score of config s on the history, with its parts and inputs. Train = every scan day but the last
    holdout_days, scored as if the history ended there (its lows use train rows only); holdout = the last days,
    scored against everything known. Trials are picked on train alone, so the holdout never reaches selection."""
    days = sorted({r["scan_date"] for r in rows})
    cut = max(0, len(days) - holdout_days)
    train_days, hold_days = set(days[:cut]), set(days[cut:])
    judged = judge(rows, s, refs, cities)
    blend = len(labels) >= LABELS_MIN
    out = {"mode": "blend" if blend else "hindsight"}
    for name, d, low in (("train", train_days, lows([r for r in rows if r["scan_date"] in train_days])),
                         ("holdout", hold_days, lows(rows))):
        p = part(judged, low, d)
        if blend:   # William's taps blend in once there are 30: half hindsight, half labels
            lp = label_part(labels, judged, d)
            p = {**p, "hindsight": p["score"], "labels": lp, "score": round((p["score"] + lp["score"]) / 2, 2)}
        out[name] = p
    out["score"] = out["train"]["score"]
    span = lambda d: [min(d), max(d)] if d else None  # noqa: E731
    out["data"] = {"scan_days": len(days), "span": span(days), "train_days": span(train_days),
                   "holdout_days": span(hold_days), "rows": len(rows), "labels": len(labels)}
    out["rules"] = {"near": NEAR, "min_obs": MIN_OBS, "beta": BETA, "holdout_days": holdout_days}
    out["settings"] = settings(s)
    return out


def _line(name: str, p: dict, span) -> str:
    if not p["judgements"]:
        return f"{name:8} {'..'.join(span) if span else 'no days'}: no weekend with {MIN_OBS}+ scan days to judge"
    t = lambda x: f"F0.5 {x['f']:.3f} ({x['tp']} right, {x['fp']} wrong, {x['fn']} lows missed)"  # noqa: E731
    out = (f"{name:8} {span[0]}..{span[1]}: {p['score']:.2f} | deal {t(p['deal'])} | ladder {t(p['ladder'])} | "
           f"good-or-better {p['good_rate']:.1%} | candidates {p['candidate_rate']:.1%} | "
           f"{p['judgements']} judgements, {p['near_low']} near the low")
    if "labels" in p:
        out += f" | labels {p['labels']['score']:.2f} on {p['labels']['labels']} taps (hindsight {p['hindsight']:.2f})"
    return out


def report(ev: dict) -> str:
    d = ev["data"]
    head = (f"score={ev['score']:.2f} mode={ev['mode']} train={ev['train']['score']:.2f} "
            f"holdout={ev['holdout']['score']:.2f} rows={d['rows']} days={d['scan_days']}"
            + (f" ({d['span'][0]}..{d['span'][1]})" if d["span"] else "") + f" seconds={ev.get('seconds', 0)}")
    return "\n".join([head, _line("train", ev["train"], d["train_days"]), _line("holdout", ev["holdout"], d["holdout_days"])])


def load_world(config=None, references="config/references.yaml"):
    cities = {c.key: c for c in load_cities()}
    return load_scoring(config), load_references(references, keys=list(cities)), cities


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="backtest", description=__doc__.split("\n\n")[0])
    ap.add_argument("--config", help="default config/scoring.yaml")
    ap.add_argument("--references", default="config/references.yaml")
    ap.add_argument("--until", help="replay the history as it stood on this scan day (YYYY-MM-DD)")
    ap.add_argument("--holdout-days", type=int, default=HOLDOUT_DAYS)
    ap.add_argument("--json", action="store_true", help="the full breakdown")
    a = ap.parse_args(argv)
    t0 = time.time()
    s, refs, cities = load_world(a.config, a.references)
    ev = evaluate(load_rows(until=a.until), s, refs, cities, holdout_days=a.holdout_days, labels=load_labels())
    ev["seconds"] = round(time.time() - t0, 1)
    print(json.dumps(ev, indent=1) if a.json else report(ev))
    return 0


if __name__ == "__main__":
    sys.exit(main())
