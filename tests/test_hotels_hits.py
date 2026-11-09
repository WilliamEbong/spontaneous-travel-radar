import json
from dataclasses import replace
from datetime import date, timedelta

import pytest

from radar.config import load_scoring
from radar.hits import candidate_id, fare_dropped, pass2, previous_candidate, write_candidate
from radar.hotels import LodgingCheck, Option, check_lodging, parse_options, search
from radar.itineraries import Trip
from radar.score import score_trip
from tests.conftest import city, load_fixture, make_leg, ref

S = load_scoring()
JAN15, JAN17 = date(2027, 1, 15), date(2027, 1, 17)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return json.loads(json.dumps(self.payload))


@pytest.fixture
def fake_serpapi(monkeypatch, tmp_path):
    class Counter:
        calls = 0

    def fake_get(url, params=None, timeout=None):
        Counter.calls += 1
        name = "serpapi_rentals_vancouver.json" if params.get("vacation_rentals") else "serpapi_hotels_vancouver.json"
        return FakeResponse(load_fixture(name))

    monkeypatch.setattr("radar.hotels.httpx.get", fake_get)
    monkeypatch.setattr("radar.hotels.USAGE_PATH", tmp_path / "usage.json")
    return Counter


def test_hotels_fixture_keeps_rated_central_four_and_five_stars():
    """Live SerpApi response, downtown Vancouver 15-17 Jan 2027 (2026-11-09)."""
    opts = parse_options(load_fixture("serpapi_hotels_vancouver.json"), city("vancouver"), "hotel", S)
    names = {o.name for o in opts}
    assert opts and all(o.rating >= 4.3 and o.stars >= 4 and o.km <= 6 for o in opts)
    assert "Hotel Belmont Vancouver" not in names                                  # rated 4.0
    q = next(o for o in opts if o.name.startswith("Quality Inn"))
    assert q.total == 247 and not q.taxes_estimated and q.nightly_pre_tax == 104 and q.deal == "17% less than usual"
    assert all(not o.fringe for o in opts)                                         # all within 3 km of the centre


def test_rentals_fixture_needs_a_price_and_a_rating():
    opts = parse_options(load_fixture("serpapi_rentals_vancouver.json"), city("vancouver"), "rental", S)
    assert opts and all(o.kind == "rental" and o.rating >= 4.3 and o.total > 0 for o in opts)
    assert not any(o.name.startswith("Urban Loft") for o in opts)                  # rated 4.0
    assert not any(o.name.startswith("Cute cozy") for o in opts)                   # no price for those dates
    assert opts[0].detail.startswith("Entire apartment")


def test_distance_cut_and_fringe():
    c = city("vancouver")
    def prop(lat, lon):
        return {"name": f"{lat}", "overall_rating": 4.5, "extracted_hotel_class": 4, "gps_coordinates": {"latitude": lat, "longitude": lon},
                "total_rate": {"extracted_after_taxes_fees": 400}}
    payload = {"properties": [prop(c.lat, c.lon), prop(c.lat + 0.036, c.lon), prop(c.lat + 0.072, c.lon), {**prop(c.lat, c.lon), "gps_coordinates": {}}]}
    opts = parse_options(payload, c, "hotel", S)                                    # 0, 4.0 and 8.0 km north; one without GPS
    assert [(round(o.km), o.fringe) for o in opts] == [(0, False), (4, True)]


def test_check_lodging_runs_both_searches_once_and_caches(tmp_path, fake_serpapi):
    hc = check_lodging(city("vancouver"), JAN15, JAN17, S, api_key="x", cache_dir=tmp_path, today=date(2026, 11, 20))
    assert fake_serpapi.calls == 2 and hc.searches == 2 and hc.skipped is None
    assert {o.kind for o in hc.options} == {"hotel", "rental"} and list(hc.options) == sorted(hc.options, key=lambda o: o.total_cad)
    again = check_lodging(city("vancouver"), JAN15, JAN17, S, api_key="x", cache_dir=tmp_path, today=date(2026, 11, 20))
    assert fake_serpapi.calls == 2 and again.searches == 0 and again.options == hc.options
    assert json.loads((tmp_path / "usage.json").read_text()) == {"2026-11": 2}


def test_no_key_never_calls(tmp_path, fake_serpapi):
    hc = check_lodging(city("vancouver"), JAN15, JAN17, S, api_key=None, cache_dir=tmp_path)
    assert hc.skipped == "no-key" and hc.options == () and fake_serpapi.calls == 0


def test_error_is_recorded_not_retried(tmp_path, monkeypatch):
    import httpx
    calls = []
    monkeypatch.setattr("radar.hotels.USAGE_PATH", tmp_path / "usage.json")
    monkeypatch.setattr("radar.hotels.httpx.get", lambda *a, **k: calls.append(1) or (_ for _ in ()).throw(httpx.ConnectError("down")))
    payload, why, spent = search(city("vancouver"), JAN15, JAN17, "hotel", S, api_key="x", cache_dir=tmp_path)
    assert (payload, why, spent) == (None, "error", 1) and len(calls) == 1


def test_cap_holds_over_a_simulated_month(tmp_path, fake_serpapi):
    """Acceptance check 7: day after day of candidates, never a lookup past the 200 cap."""
    c, spent = city("vancouver"), 0
    for day in range(130):                                                       # 2 lookups per check, more checks than the cap allows
        d = JAN15 + timedelta(days=day)
        hc = check_lodging(c, d, d + timedelta(days=2), S, api_key="x", cache_dir=tmp_path / str(day), today=date(2026, 12, 1))
        spent += hc.searches
    assert fake_serpapi.calls == spent == 200 == S.serpapi_monthly_cap
    assert json.loads((tmp_path / "usage.json").read_text()) == {"2026-12": 200}
    assert hc.skipped == "quota" and hc.searches == 0
    hc = check_lodging(c, JAN15, JAN17, S, api_key="x", cache_dir=tmp_path / "jan", today=date(2027, 1, 2))
    assert hc.searches == 2                                                      # a new month starts at zero


def _nyc_nonstop(price_2pax=640):
    out = make_leg("YYC", "EWR", "2026-12-04T08:00", "2026-12-04T14:00", "America/Edmonton", "America/New_York", price_2pax // 2)
    back = make_leg("EWR", "YYC", "2026-12-06T09:00", "2026-12-06T12:00", "America/New_York", "America/Edmonton", price_2pax // 2)
    t = Trip("new_york", "EWR", "2026-12-04_fri-off", out, back, price_2pax, date(2026, 12, 4), date(2026, 12, 6), 2, 32.0, 49.5)
    return score_trip(t, city("new_york"), ref("new_york"), S, weather_score=6, history_pct=None)


def _opt(kind, total_cad, km, name):
    return Option(kind=kind, name=name, link=f"https://example.com/{kind}", total=total_cad, currency="CAD", total_cad=total_cad,
                  taxes_estimated=False, nightly_pre_tax=None, rating=4.6, stars=4 if kind == "hotel" else None, km=km,
                  fringe=km > 3, deal=None, deal_label=None, detail="")


def test_central_hotel_beats_cheaper_fringe_rental_when_price_saturates():
    """Acceptance check 6: an exceptional New York fare, this trip's typical cost pinned at $2,500; a central hotel at $650
    and a fringe rental at $550 both put the complete trip under 60% of typical (full price points), so the 3
    convenience points decide. Both stay listed."""
    x = replace(_nyc_nonstop(), typical_cad=2500.0)
    p2 = pass2(x, city("new_york"), LodgingCheck((_opt("rental", 550, 4.5, "Fringe loft"), _opt("hotel", 650, 1.2, "Central hotel")), None, 2), S)
    names = [o["name"] for o in p2["options"]]
    assert names == ["Central hotel", "Fringe loft"] and p2["chosen"] == 0 and p2["lodging_source"] == "hotel"
    assert p2["options"][0]["trip_score"] - p2["options"][1]["trip_score"] == 3 and p2["lodging_cad"] == 650
    assert p2["share"] < 0.6 and p2["total_cad"] == 640 + 650 + 4 * 23


def test_cheaper_option_wins_when_price_still_counts():
    x = _nyc_nonstop(1100)
    p2 = pass2(x, city("new_york"), LodgingCheck((_opt("hotel", 1200, 1.0, "Dear"), _opt("hotel", 700, 1.0, "Cheap")), None, 2), S)
    assert p2["options"][0]["name"] == "Cheap" and p2["options"][0]["trip_score"] > p2["options"][1]["trip_score"]


def test_no_lodging_keeps_the_pass1_numbers(scored_vancouver):
    p2 = pass2(scored_vancouver, city("vancouver"), LodgingCheck((), "quota", 0), S)
    assert p2["chosen"] is None and p2["score"] == scored_vancouver.score and p2["lodging_source"] == "estimate" and p2["skipped"] == "quota"


def test_candidate_file_status_and_dedupe(tmp_path):
    x, c = _nyc_nonstop(), city("new_york")
    p2 = pass2(x, c, LodgingCheck((_opt("hotel", 650, 1.2, "Central [hotel](https://evil.example) **now**"),), None, 0), S)  # cached: 0 lookups
    j, m = write_candidate(x, c, ref("new_york"), p2, (6.0, "normals"), S, scan_date=date(2026, 11, 10), root=tmp_path)
    cand = json.loads(j.read_text())
    assert j.name == "2026-11-10_new_york_2026-12-04_fri-off.json" == candidate_id(date(2026, 11, 10), "new_york", "2026-12-04_fri-off") + ".json"
    assert cand["status"] == "awaiting_pass3" and cand["stage"] == "candidate" and cand["pass3"] is None and cand["final_score"] is None
    assert cand["pass1"]["lodging_source"] == "estimate" and cand["pass2"]["lodging_source"] == "hotel" and cand["score"] == p2["score"]
    assert cand["ladder"]["label"] == "exceptional" and cand["class_label"] == "Needs a day off"
    brief = m.read_text(encoding="utf-8")
    assert "](https://evil.example)" not in brief and "**now**" not in brief and "## Lodging options" in brief
    assert previous_candidate("new_york", "2026-12-04_fri-off", today=date(2026, 11, 10), root=tmp_path)["id"] == cand["id"]  # today's own
    assert previous_candidate("new_york", "2026-12-04_fri-off", today=date(2026, 11, 11), root=tmp_path) is None   # missed by pass 3
    j.write_text(json.dumps({**cand, "status": "done"}))
    prev = previous_candidate("new_york", "2026-12-04_fri-off", today=date(2026, 11, 12), root=tmp_path)
    assert prev["id"] == cand["id"] and not fare_dropped(640, prev, 15) and fare_dropped(540, prev, 15)
    assert previous_candidate("new_york", "2026-12-04_fri-off", today=date(2026, 11, 18), root=tmp_path) is None   # older than 7 days
    assert previous_candidate("new_york", "2026-12-04_fri-off", today=date(2026, 11, 10), root=tmp_path, exclude_id=cand["id"]) is None


def test_candidate_that_cannot_reach_the_hit_line_is_dropped(tmp_path):
    x, c = _nyc_nonstop(), city("new_york")
    p2 = pass2(x, c, LodgingCheck((_opt("hotel", 3000, 1.0, "Palace"),), None, 2), S)
    assert p2["score"] + 10 < 80
    cand = json.loads(write_candidate(x, c, ref("new_york"), p2, (6.0, "normals"), S, scan_date=date(2026, 11, 10), root=tmp_path)[0].read_text())
    assert cand["status"] == "dropped" and cand["stage"] == "near_miss" and "cannot reach" in cand["drop_reason"]
    capped = replace(S, cap_cad=1000)
    p2 = pass2(x, c, LodgingCheck((_opt("hotel", 650, 1.0, "Central"),), None, 2), capped)
    cand = json.loads(write_candidate(x, c, ref("new_york"), p2, (6.0, "normals"), capped, scan_date=date(2026, 11, 11), root=tmp_path)[0].read_text())
    assert cand["status"] == "dropped" and "cap" in cand["drop_reason"]
    p2 = pass2(x, c, LodgingCheck((), "quota", 0), S)                           # review finding 1: no check, no research
    cand = json.loads(write_candidate(x, c, ref("new_york"), p2, (6.0, "normals"), S, scan_date=date(2026, 11, 12), root=tmp_path)[0].read_text())
    assert cand["status"] == "dropped" and "no lodging check (quota)" in cand["drop_reason"]


def test_brief_links_are_https_only():
    from radar.hits import _link
    assert _link("Hotel", "https://example.com/a?b=1") == "[Hotel](https://example.com/a?b=1)"
    assert _link("Hotel", "https://x.example/a)[Win](https://evil.example") == "Hotel"   # cannot open a second link
    assert _link("Loft", "") == "Loft" and _link("Loft", "http://x.example") == "Loft"
