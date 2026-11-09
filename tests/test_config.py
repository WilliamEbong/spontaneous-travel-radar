from datetime import date
from pathlib import Path

import pytest

from radar.config import load_airline_surcharges, load_cities, load_days_off, load_holidays, load_references, load_scoring


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
        assert len(c.climate) == 12 and c.hotel_tax == {"vancouver": 1.185}.get(c.key, {"CA": 1.15, "US": 1.16, "MX": 1.19}[c.country])


def test_every_city_has_a_valid_ladder():
    refs = load_references(keys=[c.key for c in load_cities()])
    assert len(refs) == 20 and refs["vancouver"].flights == {"typical": 200, "good": 150, "exceptional": 120}
    assert refs["vancouver"].rooms["winter"]["source"].startswith("research")
    assert refs["new_orleans"].nonstop == "none" and refs["new_orleans"].confidence == "low"


@pytest.mark.parametrize("edit, msg", [
    (("flights: {typical: 200, good: 150, exceptional: 120}", "flights: {typical: 200, good: 120, exceptional: 150}"), "exceptional < good < typical"),
    (("    winter: {typical: 230, good: 170, exceptional: 130, source: research", "    spring: {typical: 230, good: 170, exceptional: 130, source: research"),
     "winter and summer"),
])
def test_ladder_validation(tmp_path, edit, msg):
    p = tmp_path / "r.yaml"
    p.write_text(Path("config/references.yaml").read_text(encoding="utf-8").replace(*edit, 1), encoding="utf-8")
    with pytest.raises(ValueError, match=msg):
        load_references(p)
    with pytest.raises(ValueError, match="no ladder for atlantis"):
        load_references(keys=["vancouver", "atlantis"])


def test_holidays_selected_calendar():
    hs = load_holidays()
    assert date(2027, 2, 15) in hs      # Family Day (alberta default)


def test_scoring_v2_shape():
    s = load_scoring()
    assert s.mode == "dry-run" and sum(s.weights.values()) == 100 and "events" not in s.weights
    assert s.weights["price"] == s.price_curve["points"][0][1] == 45 and s.cap_cad is None and s.serpapi_monthly_cap == 200
    classes = {c: (v["enabled"], v["candidate_threshold"], v["hit_threshold"]) for c, v in s.trip_classes.items()}
    assert classes == {"dayoff": (True, 70, 80), "weekend": (True, 70, 80)}
    assert load_airline_surcharges()["F8"] == 110


def test_bad_class_setting_fails_loudly(tmp_path):
    p = tmp_path / "s.yaml"
    p.write_text(Path("config/scoring.yaml").read_text(encoding="utf-8").replace("    hit_threshold: 80    # Settings panel: final", "    hit_threshold: high  # final", 1), encoding="utf-8")
    with pytest.raises(ValueError, match="dayoff.hit_threshold"):
        load_scoring(p)


def test_missing_field_names_the_city(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text("cities:\n  - key: atlantis\n    name: Atlantis\n")
    try:
        load_cities(p)
    except ValueError as e:
        assert "atlantis" in str(e)
    else:
        raise AssertionError("expected ValueError")
