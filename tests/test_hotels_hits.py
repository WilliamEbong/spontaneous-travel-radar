import json
from dataclasses import replace
from datetime import date

import pytest

from radar.config import load_scoring
from radar.hits import finalize_hit, previous_hit, should_realert, write_hit
from radar.hotels import HotelCheck, check_hotels, parse_properties
from tests.conftest import city, load_fixture

DEC = date(2026, 12, 1)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


@pytest.fixture
def fake_serpapi(monkeypatch):
    class Counter:
        calls = 0

    def fake_get(url, params=None, timeout=None):
        Counter.calls += 1
        return FakeResponse(load_fixture("serpapi_hotels_chicago.json"))

    monkeypatch.setattr("radar.hotels.httpx.get", fake_get)
    return Counter


def test_cap_blocks_before_the_call(tmp_path, monkeypatch, fake_serpapi):
    (tmp_path / "usage.json").write_text(json.dumps({"2026-12": 60}))
    monkeypatch.setattr("radar.hotels.USAGE_PATH", tmp_path / "usage.json")
    hc = check_hotels(city("chicago"), date(2026, 12, 4), 2, load_scoring(), api_key="x", cache_dir=tmp_path, today=DEC)
    assert hc.skipped == "cap" and hc.options == () and fake_serpapi.calls == 0          # Review Focus 4


def test_cap_at_59_allows_exactly_one_of_three_neighbourhoods(tmp_path, monkeypatch, fake_serpapi):
    (tmp_path / "usage.json").write_text(json.dumps({"2026-12": 59}))
    monkeypatch.setattr("radar.hotels.USAGE_PATH", tmp_path / "usage.json")
    hc = check_hotels(city("chicago"), date(2026, 12, 4), 2, load_scoring(), api_key="x", cache_dir=tmp_path, today=DEC)
    assert fake_serpapi.calls == 1 and hc.skipped == "cap" and len(hc.options) >= 1
    assert json.loads((tmp_path / "usage.json").read_text())["2026-12"] == 60


def test_no_key_never_calls(tmp_path, fake_serpapi):
    hc = check_hotels(city("chicago"), date(2026, 12, 4), 2, load_scoring(), api_key=None, cache_dir=tmp_path)
    assert hc.skipped == "no-key" and fake_serpapi.calls == 0


def test_parse_fixture_filters_and_sorts():
    hc = parse_properties(load_fixture("serpapi_hotels_chicago.json"), city("chicago"), 2, load_scoring())
    assert 1 <= len(hc.options) <= 3 and hc.band in {"amazing", "good", "average", "bad"}
    assert all(o.stars >= 4 and o.rating >= 4.3 for o in hc.options)
    assert list(hc.options) == sorted(hc.options, key=lambda o: o.total_pre_tax)
    assert all(o.free_cancel in (True, False, None) for o in hc.options)


def test_finalize_hit_enforces_all_gates(scored_vancouver):
    s = load_scoring()
    van = city("vancouver")
    ok, is_hit, _ = finalize_hit(scored_vancouver, van, HotelCheck((), None, "no-key"), s, previous=None)
    assert is_hit == (ok.score >= s.score_threshold and ok.total_cad <= van.bar_cad) and is_hit
    _, again, reason = finalize_hit(scored_vancouver, van, HotelCheck((), None, "no-key"), s,
                                    previous={"price": {"flights_cad_2pax": scored_vancouver.trip.flights_cad_2pax}})
    assert not again and reason == "realert"


def test_finalize_hit_uses_real_lodging(scored_vancouver):
    opts = parse_properties(load_fixture("serpapi_hotels_chicago.json"), city("chicago"), 2, load_scoring()).options
    hc = HotelCheck(opts, "bad", None)
    x, is_hit, reason = finalize_hit(scored_vancouver, city("vancouver"), hc, load_scoring(), None)
    assert x.lodging_source == "serpapi" and x.lodging_cad == pytest.approx((opts[0].total_all_in or opts[0].total_pre_tax) * 1.40)
    assert not is_hit and reason == "bar"


def test_write_hit_goes_to_dry_run(tmp_path, scored_vancouver):
    s = replace(load_scoring(), mode="dry-run")
    j, m = write_hit(scored_vancouver, city("vancouver"), HotelCheck((), None, "no-key"), [], (7.0, "forecast"), s, root=tmp_path)
    hit = json.loads(j.read_text())
    assert "dry-run" in str(j) and hit["hotels"]["skipped"] == "no-key" and hit["is_hit"]
    assert "Google Flights" in m.read_text(encoding="utf-8")
    assert previous_hit("vancouver", scored_vancouver.trip.window_id, root=tmp_path)["id"] == hit["id"]


def test_realert_only_on_15pct_drop():
    assert not should_realert({"price": {"flights_cad_2pax": 300}}, {"price": {"flights_cad_2pax": 320}}, 15)
    assert should_realert({"price": {"flights_cad_2pax": 250}}, {"price": {"flights_cad_2pax": 320}}, 15)


def test_same_day_rerun_does_not_see_its_own_hit(tmp_path, scored_vancouver):
    s = replace(load_scoring(), mode="dry-run")
    j, _ = write_hit(scored_vancouver, city("vancouver"), HotelCheck((), None, "no-key"), [], (7.0, "forecast"), s,
                     root=tmp_path, scan_date=date(2026, 11, 10))
    wid = scored_vancouver.trip.window_id
    assert previous_hit("vancouver", wid, root=tmp_path, exclude_id=j.stem) is None


def test_brief_neutralises_markdown_in_api_names(tmp_path, scored_vancouver):
    from radar.events import Event
    s = replace(load_scoring(), mode="dry-run")
    evil = Event("[Tickets](https://phish.example) **now**", date(2026, 12, 5), "Music", "Arena", "")
    _, m = write_hit(scored_vancouver, city("vancouver"), HotelCheck((), None, "no-key"), [evil], (7.0, "forecast"), s, root=tmp_path)
    text = m.read_text(encoding="utf-8")
    assert "](https://phish.example)" not in text and "**now**" not in text
