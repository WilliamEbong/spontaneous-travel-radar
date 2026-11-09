from datetime import date

import pytest

from radar.store import append_quotes, read_history, route_percentile


def test_append_and_read_roundtrip(tmp_path):
    p = append_quotes(date(2026, 11, 20), [{"city": "vancouver", "price_pp": 150}], root=tmp_path)
    append_quotes(date(2026, 11, 20), [{"city": "vancouver", "price_pp": 130}], root=tmp_path)
    rows = read_history(90, root=tmp_path, today=date(2026, 11, 21))
    assert len(rows) == 2 and p.name == "2026-11-20.jsonl"
    assert read_history(90, root=tmp_path, today=date(2027, 6, 1)) == []


def test_percentile_requires_min_days():
    hist = [{"scan_date": "2026-11-20", "city": "vancouver", "price_pp": 150}]
    assert route_percentile(120, "vancouver", hist) is None
    hist = [{"scan_date": f"2026-11-{d:02d}", "city": "vancouver", "price_pp": 100 + d} for d in range(1, 15)]
    assert route_percentile(105, "vancouver", hist) == pytest.approx(100 * 5 / 14)
