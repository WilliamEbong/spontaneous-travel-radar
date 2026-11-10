import json
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from radar.config import load_interests, load_scoring
from radar.export import write_hits_index
from radar.hits import affordability, finalize, pass2, write_candidate
from radar.hotels import LodgingCheck
from tests.conftest import city, ref
from tests.test_hotels_hits import _nyc_nonstop, _opt

S, I = load_scoring(), load_interests()
ITEMS = [
    {"name": "Free block party", "date": "2026-12-05", "uniqueness": 3, "fit": 1, "price_cad": 0, "famous": False, "reason": "Brooklyn street festival"},
    {"name": "Jazz trio at Smalls", "date": "2026-12-04", "uniqueness": 2, "fit": 1, "price_cad": 25, "famous": False, "reason": "Village jazz club"},
    {"name": "Famous rapper", "uniqueness": 2, "fit": 1, "price_cad": 90, "famous": True, "reason": "big name, small room"},
    {"name": "Arena pop show", "uniqueness": 1, "fit": 0.2, "price_cad": 180, "famous": True, "reason": "arena, too dear"},
]   # points 3 + 1.6 + 0.6 + 0 = 5.2


def candidate(tmp_path, lodging=650, scan=date(2026, 11, 10), s=S):
    x, c = _nyc_nonstop(), city("new_york")
    p2 = pass2(x, c, LodgingCheck((_opt("hotel", lodging, 1.2, "Central hotel"),), None, 2), s)
    j, _ = write_candidate(x, c, ref("new_york"), p2, (6.0, "normals"), s, scan_date=scan, root=tmp_path)
    return json.loads(j.read_text())


def research(tmp_path, items=ITEMS, airbnb=None):
    p = tmp_path / "research.json"
    p.write_text(json.dumps({"researched": "2026-11-10", "items": items, "negatives": ["Transit strike talk"], "airbnb": airbnb}))
    return p


def test_affordability_lines():
    assert [affordability(p, False, I) for p in (0, 30, 31, 60, 61)] == [1.0, 0.8, 0.6, 0.6, 0.0]
    assert affordability(100, True, I) == 0.3 and affordability(101, True, I) == 0.0 and affordability(90, False, I) == 0.0


def test_interests_file_is_valid_and_strict(tmp_path):
    assert "jazz" in I["music_love"] and I["concert_price_cad"] == {"lesser_known": 60, "famous": 100}
    p = tmp_path / "i.yaml"
    p.write_text(Path("config/interests.yaml").read_text(encoding="utf-8").replace("lesser_known: 60", "lesser_known: 160"), encoding="utf-8")
    with pytest.raises(ValueError, match="lesser_known < famous"):
        load_interests(p)


def test_finalize_adds_whats_on_and_files_a_dry_run_hit(tmp_path):
    cand = candidate(tmp_path)
    out = finalize(cand["id"], research(tmp_path), S, I, root=tmp_path)
    h = json.loads(out.read_text())
    assert out.parent.name == "dry-run" and h["is_hit"] and h["stage"] == "hit" and h["status"] == "done"
    assert h["pass3"]["events_pts"] == 5.2 and h["final_score"] == round(cand["pass2"]["score"] + 5.2) >= 80
    assert [i["points"] for i in h["pass3"]["items"]] == [3.0, 1.6, 0.6, 0.0]
    assert json.loads((tmp_path / "candidates" / f"{cand['id']}.json").read_text())["status"] == "done"
    brief = out.with_suffix(".md").read_text(encoding="utf-8")
    assert "## What's on" in brief and "Watch: Transit strike talk" in brief and f"**Final: {h['final_score']}**" in brief
    write_hits_index(tmp_path)
    (row,) = json.loads((tmp_path / "index.json").read_text())
    assert row["pass"] == 3 and row["stage"] == "hit" and row["events_pts"] == 5.2 and row["path_json"].endswith(f"dry-run/{cand['id']}.json")


def test_live_hit_goes_to_hits_and_a_short_one_to_near_miss(tmp_path):
    live = replace(S, mode="live")
    cand = candidate(tmp_path, s=live)
    assert finalize(cand["id"], research(tmp_path), live, I, root=tmp_path).parent == tmp_path
    strict = replace(S, trip_classes={**S.trip_classes, "dayoff": {**S.trip_classes["dayoff"], "hit_threshold": 110}})
    cand = candidate(tmp_path, scan=date(2026, 11, 11), s=strict)
    out = finalize(cand["id"], research(tmp_path, items=[]), strict, I, root=tmp_path)
    h = json.loads(out.read_text())
    assert out.parent.name == "near-miss" and not h["is_hit"] and h["pass3"]["events_pts"] == 0 and "Nothing that passes" in out.with_suffix(".md").read_text(encoding="utf-8")


def test_events_cap_at_ten(tmp_path):
    cand = candidate(tmp_path)
    many = [{**ITEMS[0], "name": f"Festival {i}"} for i in range(6)]          # 6 x 3 = 18
    assert json.loads(finalize(cand["id"], research(tmp_path, many), S, I, root=tmp_path).read_text())["pass3"]["events_pts"] == 10


def test_concrete_airbnb_price_rescores_a_hint_does_not(tmp_path):
    cand = candidate(tmp_path, lodging=1500)
    dates = {"check_in": cand["dates"]["check_in"], "check_out": cand["dates"]["check_out"]}
    cheap = {"total_cad": 500, "link": "https://www.airbnb.ca/rooms/1", "title": "Loft", **dates}
    other = {**cheap, "check_out": cand["dates"]["check_in"]}                 # review finding 2: a cached total for other dates
    h = json.loads(finalize(cand["id"], research(tmp_path, [], other), S, I, root=tmp_path).read_text())
    assert h["pass3"]["lodging_source"] == "hotel" and not h["pass3"]["airbnb_used"]
    h = json.loads(finalize(cand["id"], research(tmp_path, [], cheap), S, I, root=tmp_path).read_text())
    assert h["pass3"]["lodging_source"] == "airbnb" and h["pass3"]["lodging_cad"] == 500 and h["pass3"]["score"] > cand["pass2"]["score"]
    assert "Airbnb beat it" in Path(tmp_path, "near-miss" if not h["is_hit"] else "dry-run", f"{cand['id']}.md").read_text(encoding="utf-8")
    h = json.loads(finalize(cand["id"], research(tmp_path, [], {"hint": "lofts from about $300 a night"}), S, I, root=tmp_path).read_text())
    assert h["pass3"]["lodging_source"] == "hotel" and h["pass3"]["score"] == cand["pass2"]["score"]


def test_no_real_lodging_is_never_a_hit(tmp_path):
    """Review finding 1: pass 2 found nothing acceptable, so the lodging is still the pass-1 estimate."""
    x, c = _nyc_nonstop(), city("new_york")
    cand = json.loads(write_candidate(x, c, ref("new_york"), pass2(x, c, LodgingCheck((), None, 2), S), (6.0, "normals"), S,
                                      scan_date=date(2026, 11, 10), root=tmp_path)[0].read_text())
    assert cand["status"] == "awaiting_pass3" and cand["pass2"]["lodging_source"] == "estimate"
    h = json.loads(finalize(cand["id"], research(tmp_path), S, I, root=tmp_path).read_text())
    assert not h["is_hit"] and h["final_score"] >= 80 and "no real lodging" in h["drop_reason"]
    airbnb = {"total_cad": 600, "link": "https://www.airbnb.ca/rooms/2", **{k: cand["dates"][k] for k in ("check_in", "check_out")}}
    h = json.loads(finalize(cand["id"], research(tmp_path, airbnb=airbnb), S, I, root=tmp_path).read_text())
    assert h["is_hit"] and h["pass3"]["lodging_source"] == "airbnb"                 # a concrete Airbnb total is real lodging
    assert not (tmp_path / "near-miss" / f"{cand['id']}.json").exists()            # review finding 5: the old verdict is gone


def test_weekly_summary_counts_each_candidates_lookups_once(tmp_path):
    from radar.export import write_weekly_summary
    cand = candidate(tmp_path)
    finalize(cand["id"], research(tmp_path), S, I, root=tmp_path)
    write_weekly_summary([], hits_root=tmp_path, path=tmp_path / "w.json", latest_path=tmp_path / "none.json", today=date(2026, 11, 12))
    assert json.loads((tmp_path / "w.json").read_text())["passes"]["pass2_lookups"] == 2   # review finding 6


@pytest.mark.parametrize("item, airbnb, msg", [
    ({**ITEMS[0], "fit": 2}, None, "fit 0-1"),
    ({k: v for k, v in ITEMS[0].items() if k != "price_cad"}, None, "price_cad"),
    (ITEMS[0], {"total_cad": 400, "link": "http://x"}, "https link"),
    ("Jazz festival", None, "item 0"),                                            # review finding 8
    (ITEMS[0], "not found", "airbnb must be an object"),
])
def test_bad_research_file_is_refused(tmp_path, item, airbnb, msg):
    cand = candidate(tmp_path)
    with pytest.raises(ValueError, match=msg):
        finalize(cand["id"], research(tmp_path, [item], airbnb), S, I, root=tmp_path)


def test_finalize_cli(tmp_path, monkeypatch):
    import shutil

    from radar import main as radar_main
    shutil.copytree(Path("config").resolve(), tmp_path / "config")
    monkeypatch.chdir(tmp_path)
    cand = candidate(tmp_path / "hits")
    r = research(tmp_path)
    assert radar_main.main(["finalize", cand["id"], "--research", str(r)]) == 0
    assert json.loads((tmp_path / "hits/index.json").read_text())[0]["pass"] == 3


def test_breakdown_follows_the_passes(tmp_path):
    """D-75: pass 2 adds the lodging row (no points of its own) and pass 3 the what's-on row; each pass's rows add up
    to that pass's score, and a cheaper Airbnb re-renders the price and lodging lines."""
    cand = candidate(tmp_path, lodging=1500)
    p1, p2 = cand["pass1"]["breakdown"], cand["pass2"]["breakdown"]
    assert [r["key"] for r in p1] == ["price", "time", "convenience", "city", "weather"]
    assert [r["key"] for r in p2] == [*(r["key"] for r in p1), "lodging"] and cand["breakdown"] == p2
    assert abs(sum(r["points"] for r in p1) - cand["pass1"]["score"]) <= 0.5
    assert abs(sum(r["points"] for r in p2 if r["points"] is not None) - cand["pass2"]["score"]) <= 0.5
    assert p2[-1]["input"].startswith("Central hotel, hotel, $750 a night all-in, total $1,500") and p2[-1]["points"] is None
    assert p2[2]["input"] == "non-stop both ways · central room"
    dates = {"check_in": cand["dates"]["check_in"], "check_out": cand["dates"]["check_out"]}
    airbnb = {"total_cad": 500, "link": "https://www.airbnb.ca/rooms/1", "title": "Loft", **dates}
    h = json.loads(finalize(cand["id"], research(tmp_path, airbnb=airbnb), S, I, root=tmp_path).read_text())
    p3 = h["pass3"]["breakdown"]
    assert [r["key"] for r in p3][-2:] == ["lodging", "whats_on"] and h["breakdown"] == p3
    assert p3[-1]["points"] == h["pass3"]["events_pts"] == 5.2 and p3[-1]["max"] == 10
    assert p3[-1]["input"] == "+5.2: Free block party (+3), Jazz trio at Smalls (+1.6), Famous rapper (+0.6)"
    assert p3[-2]["input"] == "Airbnb: Loft, $250 a night all-in, total $500" and "$1,232 for two" in p3[0]["input"]
    assert abs(sum(r["points"] for r in p3 if r["points"] is not None) - h["final_score"]) <= 0.5
    write_hits_index(tmp_path)
    assert json.loads((tmp_path / "index.json").read_text())[0]["breakdown"] == p3
