import json
import shutil
from pathlib import Path

from radar import main as radar_main
from radar.flights import FetchError

ROOT = Path(__file__).resolve().parents[1]
ARGS = ["scan", "--offline", "--today", "2026-11-10", "--cities", "vancouver,las_vegas,new_orleans"]


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
    assert (tmp_path / "data/history/2026-11-10.jsonl").exists()
    ids = [(b["city"], b["window_id"]) for b in latest["windows"]]
    assert len(ids) == len(set(ids))                                   # one winner per city-window
    assert len({b["city"] for b in latest["best_by_city"]}) == len(latest["best_by_city"])
    for b in latest["best_by_city"]:                                   # design 6.3: cheapest fare per city
        assert all(b["flights_cad_2pax"] <= w["flights_cad_2pax"] for w in latest["windows"] if w["city"] == b["city"])
    for f in ("data/series.json", "data/weekly-summary.json", "hits/index.json", "data/digests/index.json"):
        assert (tmp_path / f).exists(), f
    hist = [json.loads(line) for line in (tmp_path / "data/history/2026-11-10.jsonl").read_text().splitlines()]
    assert all(0 <= r["price_pts"] <= 40 and abs(r["score"] - r["price_pts"]) <= 100 for r in hist)  # backtest input
    n = len(hist)
    assert n > 0 and radar_main.main(ARGS) == 0                        # a re-run replaces the day, no duplicates
    assert len((tmp_path / "data/history/2026-11-10.jsonl").read_text().splitlines()) == n


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
