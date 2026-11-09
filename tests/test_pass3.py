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
    cheap = {"total_cad": 500, "link": "https://www.airbnb.ca/rooms/1", "title": "Loft"}
    h = json.loads(finalize(cand["id"], research(tmp_path, [], cheap), S, I, root=tmp_path).read_text())
    assert h["pass3"]["lodging_source"] == "airbnb" and h["pass3"]["lodging_cad"] == 500 and h["pass3"]["score"] > cand["pass2"]["score"]
    assert "Airbnb beat it" in Path(tmp_path, "near-miss" if not h["is_hit"] else "dry-run", f"{cand['id']}.md").read_text(encoding="utf-8")
    h = json.loads(finalize(cand["id"], research(tmp_path, [], {"hint": "lofts from about $300 a night"}), S, I, root=tmp_path).read_text())
    assert h["pass3"]["lodging_source"] == "hotel" and h["pass3"]["score"] == cand["pass2"]["score"]


@pytest.mark.parametrize("item, airbnb, msg", [
    ({**ITEMS[0], "fit": 2}, None, "fit 0-1"),
    ({k: v for k, v in ITEMS[0].items() if k != "price_cad"}, None, "price_cad"),
    (ITEMS[0], {"total_cad": 400, "link": "http://x"}, "https link"),
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
