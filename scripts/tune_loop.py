"""The nightly self-tuning step (docs/TUNING-PLAN.md (c), D-82), run once a day by radar-daily (PROMPT-daily.md T).

    python scripts/tune_loop.py --date YYYY-MM-DD [--try "key=value[,key=value]" ...]   one night
    python scripts/tune_loop.py --summary [--days 7] [--date YYYY-MM-DD]                  lines for the Monday note
    python scripts/tune_loop.py --surface                                                 what it may change

Autoresearch's shape: a fixed harness (scripts/backtest.py), one editable surface (SURFACE, inside
config/scoring.yaml), one number (the hindsight price score on the train days), a fixed budget per trial (2 minutes),
keep a change when the number beats the current one by MARGIN without crossing a guardrail, revert it otherwise.
It works from whatever history is on disk and never assumes today's scan has landed. A night writes
docs/tuning-log.md (every trial), data/tuning/runs.jsonl (every score with its inputs and parts) and, when something
was kept, config/scoring.yaml; the routine commits them (auto_apply in config/tuning.yaml).
"""
import argparse
import json
import re
import sys
import time
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from radar.config import Scoring, load_scoring  # noqa: E402
from scripts.backtest import LABELS_MIN, evaluate, load_labels, load_rows, load_world, settings  # noqa: E402

MIN_DAYS = 14          # scan days in data/history before the loop starts (the ladders' own minimum)
MARGIN = 1.0           # points on the 0-100 score a trial must win by; less is noise (a few judgements flipping)
TRIAL_SECONDS = 120    # the fixed budget per trial
GUARDRAILS = {"good_rate": (0.05, 0.30), "candidate_rate": (0.005, 0.03)}   # never flag everything, never nothing
GUARD_WORDS = {"good_rate": "trips called good or better", "candidate_rate": "trips sent for a closer look"}
SURFACE = {   # key: (low, high, step). William's limits; a trial moves one key one step
    "rolling_ladder.good": (15, 35, 5),
    "rolling_ladder.typical": (40, 60, 5),
    "rolling_window_days": (30, 90, 15),
    "price_curve.share_0": (0.50, 0.70, 0.05),
    "price_curve.share_1": (0.65, 0.85, 0.05),
    "price_curve.share_2": (0.95, 1.05, 0.05),
    "dayoff.candidate_threshold": (65, 80, 2),
    "weekend.candidate_threshold": (65, 80, 2),
}
WEIGHTS = {"weights.price": (40, 50, 2), "weights.time": (15, 25, 2), "weights.convenience": (5, 15, 2),
           "weights.city": (10, 20, 2), "weights.weather": (5, 15, 2)}   # only once data/labels.jsonl has 30 rows
PLAIN = {
    "rolling_ladder.good": "a good fare is the cheapest {v}% of each route's recent fares",
    "rolling_ladder.typical": "a route's normal price is the fare {v}% of its recent fares are under",
    "rolling_window_days": "the ladders look back {v} days",
    "price_curve.share_0": "a trip earns full price points at {p} of a normal trip or less",
    "price_curve.share_1": "the middle price step sits at {p} of a normal trip",
    "price_curve.share_2": "a trip at {p} of a normal trip earns no price points",
    "dayoff.candidate_threshold": "a day-off trip needs {v} points for a closer look",
    "weekend.candidate_threshold": "a weekend trip needs {v} points for a closer look",
}
CONFIG, TUNING, LOG, RUNS, HISTORY = "config/scoring.yaml", "config/tuning.yaml", "docs/tuning-log.md", "data/tuning/runs.jsonl", "data/history"


def bounds(key: str) -> tuple:
    return SURFACE.get(key) or WEIGHTS[key]


def get(s: Scoring, key: str):
    head, _, tail = key.partition(".")
    if head == "rolling_ladder":
        return s.rolling_ladder[tail]
    if head == "rolling_window_days":
        return s.rolling_window_days
    if head == "price_curve":
        return s.price_curve["points"][int(tail[-1])][0]
    if head == "weights":
        return s.weights[tail]
    return s.trip_classes[head][tail]


def with_values(s: Scoring, values: dict) -> Scoring:
    rl, w, days = dict(s.rolling_ladder), dict(s.weights), s.rolling_window_days
    pts, tc = [list(p) for p in s.price_curve["points"]], {k: dict(v) for k, v in s.trip_classes.items()}
    for key, v in values.items():
        head, _, tail = key.partition(".")
        if head == "rolling_ladder":
            rl[tail] = v
        elif head == "rolling_window_days":
            days = v
        elif head == "price_curve":
            pts[int(tail[-1])][0] = v
        elif head == "weights":
            w[tail] = v
        else:
            tc[head][tail] = v
    return replace(s, rolling_ladder=rl, rolling_window_days=days, price_curve={**s.price_curve, "points": pts},
                   weights=w, trip_classes=tc)


def valid(s: Scoring) -> bool:
    rl, xs = s.rolling_ladder, [x for x, _ in s.price_curve["points"]]
    return rl["exceptional"] < rl["good"] < rl["typical"] and xs == sorted(set(xs)) and sum(s.weights.values()) == 100


def movable(s: Scoring, labels_on: bool, frozen=()) -> list[str]:
    """The keys the loop may move tonight: the surface, plus the weights once William's taps count; never a frozen
    key, nor one William set outside its bounds by hand (his choice stands)."""
    keys = list(SURFACE) + (list(WEIGHTS) if labels_on else [])
    return [k for k in keys if k not in frozen and bounds(k)[0] <= get(s, k) <= bounds(k)[1]]


def neighbours(s: Scoring, keys: list[str]) -> list[dict]:
    """Every one-step move from s: one key up or down, or two weights traded (the total stays 100)."""
    moves = []
    for key in (k for k in keys if k in SURFACE):
        lo, hi, step = SURFACE[key]
        moves += [{key: v} for v in (round(get(s, key) - step, 2), round(get(s, key) + step, 2)) if lo <= v <= hi]
    wk = [k for k in keys if k in WEIGHTS]
    for a in wk:
        for b in wk:
            m = {a: get(s, a) + WEIGHTS[a][2], b: get(s, b) - WEIGHTS[b][2]}
            if a != b and all(bounds(k)[0] <= v <= bounds(k)[1] for k, v in m.items()):
                moves.append(m)
    return [m for m in moves if valid(with_values(s, m))]


def parse_try(text: str, s: Scoring, keys: list[str]) -> dict:
    """The routine's own proposal, "key=value[,key=value]", held to the same surface and bounds as the menu."""
    move = {}
    for part in text.split(","):
        key, _, raw = part.partition("=")
        key = key.strip()
        if key not in keys:
            raise ValueError(f"{key!r} is not on tonight's surface ({', '.join(keys)})")
        lo, hi, step = bounds(key)
        v = float(raw)
        v = int(v) if isinstance(step, int) and v == int(v) else round(v, 2)
        if not lo <= v <= hi or (isinstance(step, int) and not isinstance(v, int)):
            raise ValueError(f"{key}={raw.strip()} is outside {lo} to {hi}")
        move[key] = v
    if not valid(with_values(s, move)):
        raise ValueError("breaks the ladder order, the price-curve order or the weights' total of 100")
    return move


def _fmt(v) -> str:
    return f"{v:.2f}" if isinstance(v, float) else str(v)


def describe(move: dict, s: Scoring) -> str:
    return ", ".join(f"{k} {_fmt(get(s, k))} → {_fmt(v)}" for k, v in move.items())


def plain(key: str, v) -> str:
    if key in WEIGHTS:
        return f"{key.split('.')[1]} is worth {v} of the 100 points"
    return PLAIN[key].format(v=v, p=f"{v:.0%}" if isinstance(v, float) else v)


def guard(new: dict, cur: dict) -> str:
    """'' when no guardrail rate moved further outside its band than the current config's; else the reason."""
    for rate, (lo, hi) in GUARDRAILS.items():
        dist = lambda x: max(lo - x, 0.0, x - hi)  # noqa: E731
        if dist(new[rate]) > dist(cur[rate]) + 1e-9:
            return f"guardrail: {GUARD_WORDS[rate]} {new[rate]:.1%}, band {lo:.1%} to {hi:.1%}"
    return ""


def key_of(s: Scoring) -> str:
    return json.dumps(settings(s), sort_keys=True)


def _trial_view(ev: dict) -> dict:
    return {"score": ev["score"], "train": ev["train"], "holdout": ev["holdout"]}


def run_night(rows, s0: Scoring, refs, cities, *, day: date, budget: int, keys: list[str], labels=(),
              proposals=()) -> dict:
    """One night: proposals first, then one-step moves from the current config in a date-rotated order. Each trial
    is judged on the train days only; the holdout can only veto the whole night at the end."""
    ev = lambda s: evaluate(rows, s, refs, cities, labels=labels)  # noqa: E731
    cur, cur_ev = s0, ev(s0)
    start, seen, trials, pending, tries = cur_ev, {key_of(s0)}, [], list(proposals), {}
    while len(trials) < budget:
        if pending:
            move, source = pending.pop(0), "routine"
            if not valid(with_values(cur, move)):
                continue
        else:
            fresh = [m for m in neighbours(cur, keys) if key_of(with_values(cur, m)) not in seen]
            if not fresh:
                break
            least = min(tries.get(tuple(sorted(m)), 0) for m in fresh)   # spread the night over the keys
            fresh = [m for m in fresh if tries.get(tuple(sorted(m)), 0) == least]
            move, source = fresh[day.toordinal() % len(fresh)], "menu"
        tries[tuple(sorted(move))] = tries.get(tuple(sorted(move)), 0) + 1
        cand = with_values(cur, move)
        seen.add(key_of(cand))
        t0 = time.time()
        new = ev(cand)
        secs = round(time.time() - t0, 2)
        why = guard(new["train"], cur_ev["train"])
        if secs > TRIAL_SECONDS:
            why = f"over the {TRIAL_SECONDS}-second budget"
        elif not why and new["score"] < cur_ev["score"] + MARGIN:
            why = f"not better by {MARGIN:g}"
        trials.append({"n": len(trials) + 1, "source": source, "change": describe(move, cur), "move": move,
                       "was": {k: get(cur, k) for k in move}, "before": _trial_view(cur_ev), "after": _trial_view(new),
                       "kept": not why, "why": why or f"better by {new['score'] - cur_ev['score']:.2f}", "seconds": secs})
        if not why:
            cur, cur_ev = cand, new
        if secs > TRIAL_SECONDS:
            break
    vetoed = cur is not s0 and cur_ev["holdout"]["score"] < start["holdout"]["score"] - MARGIN
    return {"start": start, "final": start if vetoed else cur_ev, "config": s0 if vetoed else cur,
            "trials": trials, "vetoed": vetoed}


# ---- config/scoring.yaml: only the changed lines, comments kept, read back before it counts ----

def _sub(text: str, pattern: str, value: str, key: str) -> str:
    new, n = re.subn(pattern, lambda m: m.group(1) + value, text, count=1, flags=re.M)
    if n != 1:
        raise ValueError(f"{CONFIG} has no line for {key}, so nothing was changed")
    return new


def _set_in_class(text: str, cls: str, key: str, value) -> str:
    lines = text.split("\n")
    start = next((i for i, line in enumerate(lines) if line.startswith(f"  {cls}:")), None)
    for i in range(start + 1 if start is not None else len(lines), len(lines)):
        if not re.match(r"^(    |\s*$|\s*#)", lines[i]):
            break
        m = re.match(rf"^(    {key}:[ \t]*)\S+(.*)$", lines[i])
        if m:
            lines[i] = m.group(1) + str(value) + m.group(2)
            return "\n".join(lines)
    raise ValueError(f"{CONFIG} has no trip_classes.{cls}.{key} line, so nothing was changed")


def edit_yaml(text: str, changes: dict, s: Scoring) -> str:
    for key in changes:
        head, _, tail = key.partition(".")
        if head == "rolling_ladder":
            text = _sub(text, rf"^(rolling_ladder:[ \t]*\{{[^}}\n]*\b{tail}:[ \t]*)\d+", str(s.rolling_ladder[tail]), key)
        elif head == "rolling_window_days":
            text = _sub(text, r"^(rolling_window_days:[ \t]*)\d+", str(s.rolling_window_days), key)
        elif head == "price_curve":
            pts = ", ".join(f"[{x:.2f}, {y:g}]" for x, y in s.price_curve["points"])
            text = _sub(text, r"^([ \t]+points:[ \t]*)\[\[[^#\n]*\]\]", f"[{pts}]", key)
        elif head == "weights":
            text = _sub(text, r"^(weights:[ \t]*)\{[^}\n]*\}", "{" + ", ".join(f"{k}: {v}" for k, v in s.weights.items()) + "}", key)
        else:
            text = _set_in_class(text, head, tail, s.trip_classes[head][tail])
    return text


def write_config(path: str, s: Scoring, changes: dict) -> None:
    p = Path(path)
    before = p.read_text(encoding="utf-8")
    p.write_text(edit_yaml(before, changes, s), encoding="utf-8", newline="")
    if load_scoring(path) != s:   # the file must read back as exactly the kept config, or it stays as it was
        p.write_text(before, encoding="utf-8", newline="")
        raise ValueError(f"{path} did not read back as the kept config, so nothing was changed")


# ---- logs ----

LOG_HEAD = """# Tuning log

Every trial of the nightly self-tuning loop (`scripts/tune_loop.py`, `docs/TUNING-PLAN.md`, D-82), newest last.
Score: the hindsight price score on the train days, 0 to 100, higher is better; a trial is kept only when it wins by
1 point or more without crossing a guardrail. Holdout: the same score on the last 7 scan days, never used to pick a
trial (it can only veto a whole night). Parts: deal and ladder F0.5 (candidates, good-or-better calls), the share of
judged trips called good or better and sent for a closer look. Undo a kept change: revert its `tune:` commit.

| date | # | change | score | holdout | parts after | result |
|---|---|---|---|---|---|---|
"""


def _parts(p: dict) -> str:
    return (f"deal {p['deal']['f']:.2f}, ladder {p['ladder']['f']:.2f}, good {p['good_rate']:.0%}, "
            f"closer look {p['candidate_rate']:.1%}, n {p['judgements']}")


def append_log(day: date, res: dict, *, changed: bool, auto_apply: bool, path: str = LOG) -> None:
    p = Path(path)
    out = [] if p.exists() else [LOG_HEAD]
    for t in res["trials"]:
        b, a = t["before"], t["after"]
        out.append(f"| {day} | {t['n']} | {t['change']}{' (routine)' if t['source'] == 'routine' else ''} | "
                   f"{b['score']:.2f} → {a['score']:.2f} | {b['holdout']['score']:.2f} → {a['holdout']['score']:.2f} | "
                   f"{_parts(a['train'])} | {'kept' if t['kept'] else 'reverted'}: {t['why']} |")
    s, f, d = res["start"], res["final"], res["start"]["data"]
    kept = sum(t["kept"] for t in res["trials"])
    outcome = ("vetoed: worse on the holdout, nothing changed" if res["vetoed"] else
               ("live on main" if auto_apply else "pull request") if changed else "no change")
    out.append(f"| {day} | night | {len(res['trials'])} trials, {kept} kept: {outcome} | {s['score']:.2f} → {f['score']:.2f} | "
               f"{s['holdout']['score']:.2f} → {f['holdout']['score']:.2f} | {s['mode']}, {d['scan_days']} scan days "
               f"{d['span'][0]} to {d['span'][1]} | |")
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8", newline="") as fh:
        fh.write("\n".join(out) + "\n")


def _view(ev: dict) -> dict:
    return {"settings": ev["settings"], "score": ev["score"], "train": ev["train"], "holdout": ev["holdout"]}


def append_run(day: date, res: dict, *, changed: bool, auto_apply: bool, path: str = RUNS) -> dict:
    """One line per night: every score with its inputs (settings, data span, rules) and its parts, so any result can be
    explained and re-scored later with `scripts/backtest.py --until <span end>` and the settings."""
    kept = [] if res["vetoed"] else [{"change": t["change"], "move": t["move"], "was": t["was"]} for t in res["trials"] if t["kept"]]
    rec = {"date": day.isoformat(), "mode": res["start"]["mode"], "data": res["start"]["data"], "rules": res["start"]["rules"],
           "start": _view(res["start"]), "trials": res["trials"], "final": _view(res["final"]), "kept": kept,
           "vetoed": res["vetoed"], "config_changed": changed, "auto_apply": auto_apply}
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8", newline="") as fh:
        fh.write(json.dumps(rec, separators=(",", ":"), ensure_ascii=False) + "\n")
    return rec


def read_runs(path: str = RUNS) -> list[dict]:
    p = Path(path)
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()] if p.exists() else []


def scan_days(root: str = HISTORY) -> int:
    return len(list(Path(root).glob("*.jsonl")))


def load_tuning(path: str = TUNING) -> dict:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not isinstance(raw.get("auto_apply"), bool):
        raise ValueError(f"{path}: auto_apply must be true or false")
    if not isinstance(raw.get("trials_per_night"), int) or not 10 <= raw["trials_per_night"] <= 20:
        raise ValueError(f"{path}: trials_per_night must be a whole number from 10 to 20")
    frozen = raw.get("frozen") or []
    if not isinstance(frozen, list) or any(k not in SURFACE and k not in WEIGHTS for k in frozen):
        raise ValueError(f"{path}: frozen must list keys from `python scripts/tune_loop.py --surface`")
    return {**raw, "frozen": frozen}


# ---- the Monday note ----

def _day(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d:%b} {d.day}"


def summary(days: int = 7, end: date | None = None) -> str:
    recs, n = read_runs(), scan_days()
    if not recs:
        return (f"Self-tuning: still collecting prices, {n} of {MIN_DAYS} days; it starts on its own after that."
                if n < MIN_DAYS else "Self-tuning: has not run yet.")
    end = end or date.fromisoformat(recs[-1]["date"])
    first = end - timedelta(days=days - 1)
    week = [r for r in recs if first.isoformat() <= r["date"] <= end.isoformat()]
    if not week:
        return f"Self-tuning: did not run between {_day(first.isoformat())} and {_day(end.isoformat())}."
    kept = [(r["date"], k) for r in week for k in r["kept"]]
    lines = [f"Self-tuning, {_day(week[0]['date'])} to {_day(week[-1]['date'])}: {len(week)} night{'s' * (len(week) > 1)}, "
             f"{sum(len(r['trials']) for r in week)} changes tried, {len(kept)} kept."]
    was = lambda v: f"{v:.0%}" if isinstance(v, float) else str(v)  # noqa: E731
    for d, k in kept:
        lines.append(f"- {_day(d)}: " + "; ".join(f"{plain(key, v)} (was {was(k['was'][key])})" for key, v in k["move"].items()) + ".")
    a, b = week[0]["start"], week[-1]["final"]
    lines.append(f"Hindsight score (did its good-fare and closer-look calls land near each weekend's lowest price; "
                 f"0 to 100, higher is better): {a['score']:.0f} "
                 f"on {_day(week[0]['date'])}, {b['score']:.0f} on {_day(week[-1]['date'])}; on the most recent week, "
                 f"which it never learns from: {a['holdout']['score']:.0f} then {b['holdout']['score']:.0f}.")
    if any(r["vetoed"] for r in week):
        lines.append("A night's changes were undone because they did worse on the most recent week.")
    return "\n".join(lines)


def surface_text(s: Scoring, labels_on: bool, frozen) -> str:
    keys = movable(s, labels_on, frozen)
    out = []
    for k in list(SURFACE) + list(WEIGHTS):
        lo, hi, step = bounds(k)
        status = ("movable" if k in keys else "frozen (config/tuning.yaml)" if k in frozen else
                  f"locked until data/labels.jsonl has {LABELS_MIN} rows" if k in WEIGHTS and not labels_on else
                  "left alone: set outside its bounds by hand")
        out.append(f"{k} = {_fmt(get(s, k))}  bounds {lo} to {hi}, step {step}: {status}")
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="tune_loop", description=__doc__.split("\n\n")[0])
    ap.add_argument("--date", help="tonight's date, YYYY-MM-DD (the routine's <date>)")
    ap.add_argument("--try", dest="tries", action="append", default=[], help='a trial of your own, "key=value[,key=value]"')
    ap.add_argument("--summary", action="store_true", help="plain lines for the Monday note")
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--surface", action="store_true", help="the keys, bounds and what may move tonight")
    a = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")   # the arrows and dashes in the output, also on a Windows console
    day = date.fromisoformat(a.date) if a.date else None
    if a.summary:
        print(summary(a.days, day))
        return 0
    cfg, labels = load_tuning(), load_labels()
    if a.surface:
        print(surface_text(load_scoring(), len(labels) >= LABELS_MIN, cfg["frozen"]))
        return 0
    day = day or date.today()
    n = scan_days()
    if n < MIN_DAYS:
        print(f"collecting, {n} of {MIN_DAYS} days")
        return 0
    if any(r["date"] == day.isoformat() for r in read_runs()):
        print(f"already ran {day}")
        return 0
    s0, refs, cities = load_world()
    keys = movable(s0, len(labels) >= LABELS_MIN, cfg["frozen"])
    proposals = []
    for t in a.tries:
        try:
            proposals.append(parse_try(t, s0, keys))
        except ValueError as e:
            print(f"refused --try {t}: {e}")
    res = run_night(load_rows(), s0, refs, cities, day=day, budget=cfg["trials_per_night"], keys=keys, labels=labels,
                    proposals=proposals)
    changes = {k: get(res["config"], k) for k in list(SURFACE) + list(WEIGHTS) if get(res["config"], k) != get(s0, k)}
    if changes:
        write_config(CONFIG, res["config"], changes)
    append_log(day, res, changed=bool(changes), auto_apply=cfg["auto_apply"])
    rec = append_run(day, res, changed=bool(changes), auto_apply=cfg["auto_apply"])
    d = rec["data"]
    print(f"self-tuning {day}: {d['scan_days']} scan days ({d['span'][0]} to {d['span'][1]}), mode {rec['mode']}, "
          f"{len(res['trials'])} trials, {sum(t['kept'] for t in res['trials'])} kept{', night vetoed by the holdout' if res['vetoed'] else ''}")
    print(f"  start {res['start']['score']:.2f} (holdout {res['start']['holdout']['score']:.2f})")
    for t in res["trials"]:
        print(f"  #{t['n']} {t['change']}: {t['after']['score']:.2f}, {'kept' if t['kept'] else 'reverted'} ({t['why']})")
    print(f"  final {res['final']['score']:.2f} (holdout {res['final']['holdout']['score']:.2f})")
    print(f"CONFIG_CHANGED={'yes' if changes else 'no'}")
    print(f"AUTO_APPLY={'true' if cfg['auto_apply'] else 'false'}")
    if changes:
        print(f"COMMIT_MESSAGE=tune: {day}: {'; '.join(k['change'] for k in rec['kept'])} "
              f"(score {res['start']['score']:.1f} → {res['final']['score']:.1f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
