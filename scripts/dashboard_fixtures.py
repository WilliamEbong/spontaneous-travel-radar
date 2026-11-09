"""Build the dashboard's four test states as static sites, for the Playwright check (BUILD-PLAN-v2 T8).

    python scripts/dashboard_fixtures.py <out_dir>        then serve <out_dir> and open /<state>/

States: empty (day-one data: no trip near a deal), passed (trips at 70+, lodging checked, a near miss, no hit),
hits (one learning-run hit in each trip class), live (the same in live mode). Everything comes from the real
pipeline: an offline scan of the recorded fares (no network), pass 2 with made-up lodging near each centre,
and finalize on made-up research. Only the route ladders are lowered so the old fares look like deals.
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import radar.main as rm  # noqa: E402
from radar.config import load_references, load_scoring  # noqa: E402
from radar.hotels import LodgingCheck, Option  # noqa: E402
from radar.score import room_night_cad  # noqa: E402

ARGS = ["scan", "--offline", "--today", "2026-10-08", "--cities", "vancouver,las_vegas,new_orleans"]
LADDERS = {   # per state: city -> flights ladder that makes the recorded fares good or exceptional
    "passed": {"las_vegas": "{typical: 2600, good: 1700, exceptional: 1000}"},
    "hits": {"las_vegas": "{typical: 3800, good: 2400, exceptional: 1800}", "vancouver": "{typical: 3500, good: 2200, exceptional: 1700}"},
}
LADDERS["live"] = LADDERS["hits"]
RESEARCH = {"researched": "2026-10-08", "negatives": ["Rain likely on Saturday afternoon"], "airbnb": {"hint": "Lofts near the centre from about $260 a night"},
            "items": [{"name": "Neighbourhood jazz festival", "date": "Sat", "uniqueness": 3, "fit": 1, "price_cad": 0, "famous": False,
                       "reason": "Free outdoor stages, local players; nothing like it in Calgary that weekend"},
                      {"name": "Afrobeats night at a small club", "date": "Fri", "uniqueness": 2, "fit": 1, "price_cad": 25, "famous": False,
                       "reason": "Resident DJs, the kind of night William looks for"},
                      {"name": "Arena pop tour", "date": "Sat", "uniqueness": 0, "fit": 0.1, "price_cad": 160, "famous": True,
                       "reason": "Plays Calgary next month; a dislike anyway"}]}
NOTE = "# Daily note 2026-10-08\n\n- Health: 100% coverage, no errors.\n- Pass 3: two candidates researched, one hit in each trip class.\n- No change today.\n"


def fake_lodging(city, check_in, check_out, s, **_):
    """A central hotel at 95% of the route's good room rate and a fringe rental at 80%, so pass 2 has a real choice."""
    nights = (check_out - check_in).days
    good = nights * room_night_cad(city, load_references()[city.key], check_in, "good", s)
    opt = lambda kind, f, km, name: Option(kind, name, f"https://example.com/{city.key}/{kind}", round(good * f), "CAD", round(good * f),  # noqa: E731
                                           False, None, 4.5, 4 if kind == "hotel" else None, km, km > 3, "18% less than usual" if kind == "hotel" else None,
                                           "Deal" if kind == "hotel" else None, "3:00 PM" if kind == "hotel" else "Entire apartment, Sleeps 2")
    return LodgingCheck((opt("hotel", 0.95, 1.1, f"Central {city.name} Hotel"), opt("rental", 0.8, 4.2, f"{city.name} fringe loft")), None, 2)


def build(out: Path, state: str) -> None:
    d = out / state
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    shutil.copy(ROOT / "index.html", d)
    for sub in ("site", "config", "tests/fixtures/offline"):
        shutil.copytree(ROOT / sub, d / sub)
    refs = d / "config/references.yaml"
    text = refs.read_text(encoding="utf-8")
    for city, ladder in LADDERS.get(state, {}).items():
        head = f"{city}:\n"
        i = text.index(head)
        j = text.index("  flights: ", i)
        k = text.index("\n", j)
        text = text[:j] + f"  flights: {ladder}" + text[k:]
    refs.write_text(text, encoding="utf-8")
    if state == "live":
        p = d / "config/scoring.yaml"
        p.write_text(p.read_text(encoding="utf-8").replace("mode: dry-run ", "mode: live    ", 1), encoding="utf-8")
    import os
    os.chdir(d)
    rm.check_lodging = fake_lodging
    rm.MAX_CANDIDATES_PER_SCAN = 6
    assert rm.main(ARGS) == 0
    s = load_scoring()
    cands = sorted((json.loads(p.read_text()) for p in Path("hits/candidates").glob("*.json")), key=lambda h: -h["score"])
    if state != "empty":
        Path("data/digests").mkdir(parents=True, exist_ok=True)
        Path("data/digests/2026-10-08.md").write_text(NOTE, encoding="utf-8")
    research = Path("data/research/fixture.json")
    research.parent.mkdir(parents=True, exist_ok=True)
    if state == "passed" and cands:
        research.write_text(json.dumps({**RESEARCH, "items": RESEARCH["items"][2:]}), encoding="utf-8")
        strict = type(s)(**{**vars(s), "trip_classes": {k: {**v, "hit_threshold": 100} for k, v in s.trip_classes.items()}})
        from radar.hits import finalize
        finalize(cands[0]["id"], research, strict, rm.load_interests())
    if state in ("hits", "live"):
        research.write_text(json.dumps(RESEARCH), encoding="utf-8")
        for cls in ("weekend", "dayoff"):
            c = next(h for h in cands if h["trip_class"] == cls and h["status"] == "awaiting_pass3")
            rm.main(["finalize", c["id"], "--research", str(research)])
    rm.main(["export"])
    shutil.rmtree("tests")
    os.chdir(ROOT)


if __name__ == "__main__":
    out = Path(sys.argv[1]).resolve()
    for st in ("empty", "passed", "hits", "live"):
        build(out, st)
        idx = json.loads((out / st / "hits/index.json").read_text())
        latest = json.loads((out / st / "data/latest.json").read_text())
        print(st, "passed", sum(w["score"] >= 70 for w in latest["windows"]), "candidates", len(idx),
              "hits", [(r["trip_class"], r["mode"]) for r in idx if r["is_hit"]])
