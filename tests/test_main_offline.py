import json
import shutil
from pathlib import Path

from radar import main as radar_main
from radar.flights import FetchError

ROOT = Path(__file__).resolve().parents[1]
ARGS = ["scan", "--offline", "--today", "2026-10-08", "--cities", "vancouver,las_vegas,new_orleans"]


def setup(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    shutil.copytree(ROOT / "tests/fixtures/offline", tmp_path / "tests/fixtures/offline")
    shutil.copytree(ROOT / "config", tmp_path / "config")


def test_offline_scan_writes_latest_and_history(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    assert radar_main.main(ARGS) == 0
    latest = json.loads((tmp_path / "data/latest.json").read_text())
    assert latest["mode"] == "dry-run" and len(latest["best_by_city"]) >= 1
    assert "no_nonstop" in latest["health"] and 0 < latest["health"]["coverage_pct"] <= 100
    assert latest["health"]["queries_attempted"] == 0                 # offline never touches the network
    assert (tmp_path / "data/history/2026-10-08.jsonl").exists()
    ids = [(b["city"], b["window_id"]) for b in latest["windows"]]
    assert len(ids) == len(set(ids))                                   # one winner per city-window
    assert len({b["city"] for b in latest["best_by_city"]}) == len(latest["best_by_city"])
    for b in latest["best_by_city"]:                                   # v2: each city's best deal = its top score
        assert all((b["score"], -b["total_cad"]) >= (w["score"], -w["total_cad"]) for w in latest["windows"] if w["city"] == b["city"])
    assert all(c["ladder"]["exceptional"] < c["ladder"]["good"] < c["ladder"]["typical"] for c in latest["cities"])
    for f in ("data/series.json", "data/weekly-summary.json", "hits/index.json", "data/digests/index.json"):
        assert (tmp_path / f).exists(), f
    hist = [json.loads(line) for line in (tmp_path / "data/history/2026-10-08.jsonl").read_text().splitlines()]
    assert all(-100 <= r["price_pts"] <= 45 and abs(r["score"] - r["price_pts"]) <= 100 for r in hist)  # backtest input
    for r in hist + latest["windows"] + latest["best_by_city"]:       # acceptance check 9
        assert r["ladder"] in ("exceptional", "good", "typical", "above") and r["share"] > 0 and r["pass"] in (1, 2)
        assert "final_score" in r and r["final_score"] is None
    assert all("band" not in r and "bar_cad" not in r for r in hist + latest["windows"])
    assert {r["trip_class"] for r in hist} == {"dayoff", "weekend"}                     # both classes, every row (D-52)
    assert all(r["trip_class"] == ("weekend" if r["window_id"].endswith("_weekend") else "dayoff")
               for r in latest["windows"] + latest["best_by_city"])
    wk = [r for r in hist if r["trip_class"] == "weekend"]
    assert wk and all(r["stops_out"] == r["stops_back"] == 0 and r["city"] != "new_orleans" for r in wk)
    assert all(r["window_id"] >= "2026-11-19" for r in hist if r["trip_class"] == "dayoff")   # Day 1 at least 6 weeks out
    n = len(hist)
    assert n > 0 and radar_main.main(ARGS) == 0                        # a re-run replaces the day, no duplicates
    assert len((tmp_path / "data/history/2026-10-08.jsonl").read_text().splitlines()) == n


def test_settings_files_steer_the_scan(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    assert radar_main.main(ARGS) == 0
    before = json.loads((tmp_path / "data/latest.json").read_text())
    p = tmp_path / "config/cities.yaml"
    p.write_text(p.read_text(encoding="utf-8").replace("key: las_vegas\n", "key: las_vegas\n    enabled: false\n", 1), encoding="utf-8")
    (tmp_path / "config/days_off.yaml").write_text("extra: []\nblocked: [2026-11-21]\n", encoding="utf-8")
    assert radar_main.main(ARGS) == 0
    latest = json.loads((tmp_path / "data/latest.json").read_text())
    assert "las_vegas" not in {c["key"] for c in latest["cities"]}                  # a disabled city is out of the scan
    assert all(r["city"] != "las_vegas" for r in latest["best_by_city"] + latest["windows"])
    assert latest["health"]["windows"] < before["health"]["windows"]              # the blocked Saturday removed windows
    assert latest["health"]["queries_planned"] < before["health"]["queries_planned"]


def test_fetch_error_is_recorded_not_fatal(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    real = radar_main.fetch_leg

    def flaky(q, budget, **kw):
        if q.dest == "LAS" or q.origin == "LAS":
            raise FetchError("RuntimeError: unusual traffic")
        return real(q, budget, **kw)

    monkeypatch.setattr(radar_main, "fetch_leg", flaky)
    assert radar_main.main(ARGS) == 0                                  # Review Focus 3
    latest = json.loads((tmp_path / "data/latest.json").read_text())
    assert latest["health"]["fetch_errors"] and latest["health"]["fetch_errors"][0]["route"].count("LAS") == 1
    assert all(b["city"] != "las_vegas" for b in latest["best_by_city"])
    assert not list(tmp_path.glob("data/*.tmp"))


def test_candidates_get_pass_two_and_a_file(tmp_path, monkeypatch):
    """With the candidate line lowered so the offline fares qualify, the top three get a lodging check (faked: no
    network), a candidate file each, pass 2 on their rows; a re-run the next day reuses them (7-day dedupe)."""
    from radar.hotels import LodgingCheck
    setup(tmp_path, monkeypatch)
    p = tmp_path / "config/scoring.yaml"
    p.write_text(p.read_text(encoding="utf-8").replace("candidate_threshold: 70", "candidate_threshold: 0"), encoding="utf-8")
    r = tmp_path / "config/references.yaml"
    r.write_text(r.read_text(encoding="utf-8").replace("good: ", "good: 9").replace("typical: ", "typical: 99"), encoding="utf-8")
    calls = []
    monkeypatch.setattr(radar_main, "check_lodging", lambda *a, **k: calls.append((a[0].key, a[1].isoformat())) or LodgingCheck((), "no-key", 0))
    assert radar_main.main(ARGS) == 0
    latest = json.loads((tmp_path / "data/latest.json").read_text())
    assert len(calls) == 3 == len(latest["candidates"]) and latest["health"]["pass2_checks"] == 3
    files = sorted((tmp_path / "hits/candidates").glob("*.json"))
    assert [f.stem for f in files] == sorted(latest["candidates"])
    passed = [w for w in latest["windows"] if w["pass"] == 2]
    assert sorted(w["candidate_id"] for w in passed) == sorted(latest["candidates"])
    index = json.loads((tmp_path / "hits/index.json").read_text())
    assert {i["id"] for i in index} == set(latest["candidates"]) and all(i["stage"] in ("candidate", "near_miss") for i in index)
    calls.clear()
    assert radar_main.main(ARGS) == 0                   # same day again: its own files count only once their check completed
    assert len(calls) == 3
    assert all(json.loads(f.read_text())["status"] == "dropped" for f in files)   # no key: no lodging check, retried next scan
    for f in files:                                     # as if the lodging check had completed and pass 3 had run
        h = json.loads(f.read_text())
        h["pass2"]["skipped"], h["status"] = None, "done"
        f.write_text(json.dumps(h))
    calls.clear()
    done = {(h["city"], h["dates"]["check_in"]) for h in (json.loads(f.read_text()) for f in files)}
    assert radar_main.main(ARGS) == 0 and len(calls) == 3 and not done & set(calls)   # a same-day re-run spends nothing on them
    calls.clear()
    day1 = {(h["city"], h["window_id"]): h["id"] for h in (json.loads(f.read_text()) for f in files)}
    assert radar_main.main(ARGS[:3] + ["2026-10-09"] + ARGS[4:]) == 0
    latest = json.loads((tmp_path / "data/latest.json").read_text())
    again = [w for w in latest["windows"] if (w["city"], w["window_id"]) in day1]
    assert again and all(w["pass"] == 2 and w["candidate_id"] == day1[(w["city"], w["window_id"])] for w in again)
    assert len(calls) == 3                              # reused ones take no slot: the three checks went to new city-windows
