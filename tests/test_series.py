import json

from radar.export import write_series


def test_series_is_per_trip_class(tmp_path):
    rows = [
        {"city": "vancouver", "scan_date": "2026-11-09", "price_pp": 446, "trip_class": "dayoff"},
        {"city": "vancouver", "scan_date": "2026-11-09", "price_pp": 500, "trip_class": "dayoff"},
        {"city": "vancouver", "scan_date": "2026-11-09", "price_pp": 234, "trip_class": "weekend"},
        {"city": "toronto", "scan_date": "2026-11-09", "price_pp": 820},  # pre-class row counts as day-off
    ]
    path = tmp_path / "series.json"
    write_series(rows, path=path)
    s = json.loads(path.read_text(encoding="utf-8"))
    assert s["vancouver"] == {"dayoff": [["2026-11-09", 446]], "weekend": [["2026-11-09", 234]]}
    assert s["toronto"] == {"dayoff": [["2026-11-09", 820]]}
