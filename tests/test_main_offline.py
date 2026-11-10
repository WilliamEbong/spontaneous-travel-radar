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
    for r in hist:                                                     # D-76: every number behind the score is kept
        assert set(r["components"]) == {"price", "time", "convenience", "city", "weather"}
        assert abs(sum(r["components"].values()) - r["score"]) <= 0.5 and isinstance(r["inputs"], dict) and r["inputs"]
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


def test_scan_writes_a_scoring_csv_per_day(tmp_path, monkeypatch):
    """D-77: one CSV beside each day's JSONL (same rows, the points columns add up to the score, the evidence lines are
    the breakdown's), latest.csv is the newest day's copy, index.json lists the days."""
    import csv
    setup(tmp_path, monkeypatch)
    assert radar_main.main(ARGS) == 0
    hist = (tmp_path / "data/history/2026-10-08.jsonl").read_text(encoding="utf-8").splitlines()
    raw = (tmp_path / "data/history/2026-10-08.csv").read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")                                             # BOM: Excel reads the degree sign
    rows = list(csv.DictReader(raw.decode("utf-8-sig").splitlines()))
    from radar.export import CRITERIA, CSV_COLUMNS
    assert len(rows) == len(hist) and list(rows[0]) == CSV_COLUMNS
    jl = [json.loads(line) for line in hist]
    for r, src in zip(rows, jl):
        assert abs(sum(float(r[f"{k}_pts"]) for k in CRITERIA) - float(r["score"])) <= 0.5
        assert r["price_input"].startswith("complete trip $") and r["weather_input"].endswith("of 30 days")
        assert r["city"] == src["inputs"]["city_name"] and r["candidate"] in ("yes", "no") and r["winner"] in ("yes", "no")
        assert int(r["total_for_two"]) == src["total_cad"] and int(r["lodging_estimate"]) == src["lodging_cad"]
        assert float(r["typical_trip"]) == src["typical_cad"] and r["dates"].startswith(src["out_dep"][:10])
    assert '"' in raw.decode("utf-8-sig").splitlines()[1] and "\r" not in raw.decode("utf-8-sig")   # text quoted, LF
    assert (tmp_path / "data/history/latest.csv").read_bytes() == raw
    index = json.loads((tmp_path / "data/history/index.json").read_text(encoding="utf-8"))
    assert index == [{"date": "2026-10-08", "path": "data/history/2026-10-08.csv", "rows": len(hist)}]
    assert radar_main.main(["export"]) == 0                                                # rebuilds the same files
    assert (tmp_path / "data/history/2026-10-08.csv").read_bytes() == raw


def test_csv_row_tolerates_rows_from_before_the_components():
    """A v1 row (no totals) and a v2 row without components (before D-76) flatten with blanks, never an error."""
    from radar.export import csv_row
    base = {"scan_date": "2026-11-09", "city": "new_york", "window_id": "2026-12-25_fri-off", "trip_class": "dayoff",
            "out_dep": "2026-12-25T07:25:00-06:00", "back_arr": "2026-12-26T22:47:00-06:00", "airlines": "DL+AA",
            "stops_out": 1, "stops_back": 1, "flights_cad_2pax": 2790, "price_pp": 1395, "score": 20, "candidate": False,
            "winner": False, "price_pts": -13.25}
    v1 = csv_row(base)
    assert v1["city"] == "New York" and v1["dates"] == "2026-12-25 to 2026-12-26 (1 night)" and v1["price_pts"] == -13.25
    assert v1["total_for_two"] is None and v1["typical_trip"] is None and v1["weather_pts"] is None and v1["weather_input"] is None
    v2 = csv_row({**base, "total_cad": 2852, "share": 1.7098, "nights": 2, "pass": 1, "final_score": None})
    assert v2["typical_trip"] == 1668 and v2["price_input"] is None and v2["pass"] == 1 and v2["winner"] == "no"


def test_rows_carry_a_score_breakdown(tmp_path, monkeypatch):
    """D-75: every latest.json row explains its score, criterion by criterion, and the points add up to it."""
    setup(tmp_path, monkeypatch)
    assert radar_main.main(ARGS) == 0
    latest = json.loads((tmp_path / "data/latest.json").read_text())
    rows = latest["windows"] + latest["best_by_city"]
    assert rows
    for r in rows:
        bd = r["breakdown"]
        assert [b["key"] for b in bd] == ["price", "time", "convenience", "city", "weather"]
        assert abs(sum(b["points"] for b in bd) - r["score"]) <= 0.5
        assert all(b["label"] and b["input"] and b["max"] > 0 for b in bd)
        assert bd[4]["input"].endswith("of 30 days")     # offline: climate normals, never a forecast
