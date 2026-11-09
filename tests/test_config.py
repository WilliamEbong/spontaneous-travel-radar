from datetime import date
from pathlib import Path

import pytest

from radar.config import load_airline_surcharges, load_cities, load_days_off, load_holidays, load_scoring


def test_enabled_defaults_true_and_must_be_a_bool(tmp_path):
    assert all(c.enabled for c in load_cities())
    src = Path("config/cities.yaml").read_text(encoding="utf-8")
    p = tmp_path / "c.yaml"
    p.write_text(src.replace("key: vancouver\n", "key: vancouver\n    enabled: false\n", 1), encoding="utf-8")
    assert not next(c for c in load_cities(p) if c.key == "vancouver").enabled
    p.write_text(src.replace("key: vancouver\n", "key: vancouver\n    enabled: nope\n", 1), encoding="utf-8")
    with pytest.raises(ValueError, match="vancouver: enabled"):
        load_cities(p)


def test_days_off_repo_file_and_both_date_forms(tmp_path):
    extra, blocked = load_days_off()
    assert isinstance(extra, set) and isinstance(blocked, set)
    p = tmp_path / "d.yaml"
    p.write_text("extra: [2026-12-24, '2026-12-31']\nblocked:\n", encoding="utf-8")   # bare YAML date, quoted ISO string, empty key
    assert load_days_off(p) == ({date(2026, 12, 24), date(2026, 12, 31)}, set())


@pytest.mark.parametrize("text, msg", [
    ("extra: 2026-12-24\n", "must be a list"),
    ("extra: ['someday']\n", "invalid date"),
    ("extra: [2026-12-24]\nblocked: [2026-12-24]\n", "both extra and blocked"),
    ("extra: []\nvacation: []\n", "only the keys"),
])
def test_days_off_bad_file_fails_loudly(tmp_path, text, msg):
    p = tmp_path / "d.yaml"
    p.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match=msg):
        load_days_off(p)


def test_cities_load_and_are_consistent():
    cities = load_cities()
    assert len(cities) == 20
    keys = {c.key for c in cities}
    assert {"vancouver", "new_york", "mexico_city"} <= keys
    assert sum(len(c.airports) for c in cities) == 28
    for c in cities:
        assert c.flight_group in {"yvr", "sea_pdx", "medium", "yyz", "yul_ord", "nyc_tier2"}
        assert c.hotel_group in {"cheap", "mid", "expensive"}
        assert len(c.climate) == 12 and c.bar_cad % 50 == 0


def test_holidays_selected_calendar():
    hs = load_holidays()
    assert date(2027, 2, 15) in hs      # Family Day (alberta default)


def test_scoring_bands_monotonic():
    s = load_scoring()
    for g, b in s.flight_bands.items():
        assert b["amazing"] < b["good"] < b["average"], g
    assert s.mode == "dry-run" and sum(s.weights.values()) == 100
    assert load_airline_surcharges()["F8"] == 110


def test_missing_field_names_the_city(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text("cities:\n  - key: atlantis\n    name: Atlantis\n")
    try:
        load_cities(p)
    except ValueError as e:
        assert "atlantis" in str(e)
    else:
        raise AssertionError("expected ValueError")
