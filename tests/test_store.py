from datetime import date

import pytest

from radar.store import read_history, route_percentile, write_day


def test_write_and_read_roundtrip(tmp_path):
    p = write_day(date(2026, 11, 20), [{"city": "vancouver", "price_pp": 150}, {"city": "vancouver", "price_pp": 130}], root=tmp_path)
    rows = read_history(90, root=tmp_path, today=date(2026, 11, 21))
    assert len(rows) == 2 and p.name == "2026-11-20.jsonl"
    assert read_history(90, root=tmp_path, today=date(2027, 6, 1)) == []


def test_percentile_requires_min_days():
    hist = [{"scan_date": "2026-11-20", "city": "vancouver", "price_pp": 150}]
    assert route_percentile(120, "vancouver", hist) is None
    hist = [{"scan_date": f"2026-11-{d:02d}", "city": "vancouver", "price_pp": 100 + d} for d in range(1, 15)]
    assert route_percentile(105, "vancouver", hist) == pytest.approx(100 * 5 / 14)


def test_replacing_a_day_is_atomic(tmp_path, monkeypatch):
    """data/history/<day>.jsonl is committed and read by every later scan. A crash while the day is being rewritten
    must leave the previous file whole: before the fix the scan deleted it, then appended row by row, so a kill
    mid-write left a truncated line that made read_history (and so the next scan) raise."""
    from radar import store
    day = date(2026, 11, 20)
    before = [{"city": "vancouver", "price_pp": 150}, {"city": "chicago", "price_pp": 300}]
    p = store.write_day(day, before, root=tmp_path)
    real, calls = store.json.dumps, []

    def dying_dumps(*a, **k):
        calls.append(1)
        if len(calls) == 2:
            raise KeyboardInterrupt
        return real(*a, **k)

    monkeypatch.setattr(store.json, "dumps", dying_dumps)
    with pytest.raises(KeyboardInterrupt):
        store.write_day(day, [{"city": "vancouver", "price_pp": 140}, {"city": "chicago", "price_pp": 290}], root=tmp_path)
    monkeypatch.undo()
    assert read_history(90, root=tmp_path, today=day) == before and p.name == "2026-11-20.jsonl"
