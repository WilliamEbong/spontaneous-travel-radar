from datetime import date

from radar.config import load_airline_surcharges, load_cities, load_holidays, load_scoring


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
