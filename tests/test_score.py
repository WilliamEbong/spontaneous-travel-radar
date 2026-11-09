from dataclasses import replace
from datetime import date

import pytest

from radar.config import load_scoring
from radar.itineraries import Trip
from radar.score import (best_per_window, is_candidate, ladder_label, price_points, rescore, score_trip, season, time_points,
                         typical_trip_cad, worth_flying)
from tests.conftest import city, make_leg, ref

S = load_scoring()


def test_price_points_through_the_anchors():
    c = S.price_curve
    assert [price_points(x, c) for x in (0.4, 0.6, 0.75, 1.0, 1.3)] == pytest.approx([45, 45, 25, 0, -10])
    assert price_points(0.675, c) == pytest.approx(35) and price_points(0.875, c) == pytest.approx(12.5)
    assert price_points(1.6, c) == pytest.approx(-20)          # past 1.30 the slope continues (D-59)
    assert price_points(2.2, c) == pytest.approx(-40) and price_points(9, c) == -40   # floor


def test_vancouver_worked_example(vancouver_trip_fixture):
    """Acceptance check 1: research doc, complete-trip ladder, Vancouver in January, two people, 2 nights, transit $40,
    weather 4, time 20, convenience 10, city 12. The doc's 'good about 74' is an arithmetic slip: the decided anchors
    give 70.6 (D-60); $650 gives 83 and the exceptional trip 91 (the doc: about 90)."""
    c, r = city("vancouver"), ref("vancouver")
    jan = replace(vancouver_trip_fixture, check_in=date(2027, 1, 15), check_out=date(2027, 1, 17))
    assert typical_trip_cad(jan, c, r, S) == pytest.approx(985.1)

    def trip(flights_2pax, lodging):
        x = score_trip(replace(jan, flights_cad_2pax=flights_2pax), c, r, S, weather_score=4, history_pct=None, lodging_cad=lodging)
        assert (x.components.time, x.components.convenience, x.components.city, x.components.weather) == (20, 10, 12, 4)
        return x

    good = trip(300, 2 * 170 * 1.185)
    assert good.total_cad == pytest.approx(742.9) and sum(vars(good.components).values()) == pytest.approx(70.6, abs=0.05)
    assert trip(240, 370).total_cad == 650 and trip(240, 370).score == 83
    exceptional = trip(240, 2 * 130 * 1.185)
    assert exceptional.score == 91 and abs(exceptional.score - 90) <= 2
    est = score_trip(jan, c, r, S, weather_score=4, history_pct=None)        # pass 1: the good room rate (D-58)
    assert est.lodging_cad == pytest.approx(2 * 170 * 1.185) and est.lodging_source == "estimate"


def test_cheaper_above_typical_trip_wins_despite_fewer_hours():
    """Acceptance check 2, the day-one bug: Toronto 21-23 Nov, 01:20 out / 12:10 back at $1,357 pp kept 34.9 h on the
    ground, 07:30 out / 06:15 back at $1,002 pp kept 22.8 h. Both far above typical; the cheaper must win."""
    c, r = city("toronto"), ref("toronto")
    out = make_leg("YYC", "YYZ", "2026-11-21T07:30", "2026-11-21T13:20", "America/Edmonton", "America/Toronto", 1000)
    back = make_leg("YYZ", "YYC", "2026-11-23T06:15", "2026-11-23T08:45", "America/Toronto", "America/Edmonton", 1004)

    def trip(price_2pax, hours):
        t = Trip("toronto", "YYZ", "2026-11-21_mon-off", out, back, price_2pax, date(2026, 11, 21), date(2026, 11, 23), 2, hours, 49.5)
        return score_trip(t, c, r, S, weather_score=5, history_pct=None)

    dear, cheap = trip(2714, 34.9), trip(2004, 22.8)
    assert dear.share > cheap.share > 1.3 and dear.ladder == cheap.ladder == "above"
    assert dear.components.time > cheap.components.time
    assert best_per_window([dear, cheap]) == [cheap]
    a, b = trip(1000, 30), trip(1100, 30)                   # just above typical: the cheaper scores higher too
    assert 1 < a.share < b.share < 1.3 and a.score > b.score


def test_candidate_rule_at_the_line():
    """Acceptance check 5: flights at the route's good with score 69 is not a candidate, 70 is."""
    good = ref("vancouver").flights["good"]
    assert not is_candidate(good, 69, good, 70) and is_candidate(good, 70, good, 70)
    assert not is_candidate(good + 1, 99, good, 70)


def test_score_trip_marks_candidates_per_class(vancouver_trip_fixture):
    c, r = city("vancouver"), ref("vancouver")
    great = replace(vancouver_trip_fixture, flights_cad_2pax=2 * 120)
    x = score_trip(great, c, r, S, weather_score=8, history_pct=None)
    assert x.ladder == "exceptional" and x.score >= 70 and x.candidate
    strict = replace(S, trip_classes={**S.trip_classes, "dayoff": {**S.trip_classes["dayoff"], "candidate_threshold": x.score + 1}})
    assert not score_trip(great, c, r, strict, weather_score=8, history_pct=None).candidate
    assert score_trip(replace(great, trip_class="weekend"), c, r, strict, weather_score=8, history_pct=None).candidate


def test_ladder_label_and_season():
    f = {"typical": 200, "good": 150, "exceptional": 120}
    assert [ladder_label(p, f) for p in (120, 121, 150, 200, 201)] == ["exceptional", "good", "good", "typical", "above"]
    assert [season(date(2026, m, 1)) for m in (3, 4, 10, 11)] == ["winter", "summer", "summer", "winter"]


def test_usd_rooms_convert_and_tax():
    """New York, a US city: the typical room is USD, x 1.40, x 1.16 per night (the US default tax)."""
    c, r = city("new_york"), ref("new_york")
    t = Trip("new_york", "EWR", "2026-12-04_fri-off", None, None, 0, date(2026, 12, 4), date(2026, 12, 6), 2, 30, 49.5)
    room = r.rooms["winter"]["typical"]
    assert c.hotel_tax == 1.16 and typical_trip_cad(t, c, r, S) == pytest.approx(2 * r.flights["typical"] + 2 * room * 1.40 * 1.16 + 4 * 23)


def test_rescore_moves_only_price_and_convenience(scored_vancouver):
    x = scored_vancouver
    comps = {k: getattr(x.components, k) for k in ("price", "time", "convenience", "city", "weather")}
    kw = dict(flights_cad=x.trip.flights_cad_2pax, transfers=40, typical_cad=x.typical_cad, conv_pts=x.conv_pts, s=S)
    same = rescore(comps, lodging_cad=x.lodging_cad, fringe=False, **kw)
    assert same["score"] == x.score and same["total_cad"] == pytest.approx(x.total_cad)
    fringe = rescore(comps, lodging_cad=x.lodging_cad, fringe=True, **kw)
    assert fringe["components"]["convenience"] == pytest.approx(7) and fringe["components"]["time"] == pytest.approx(comps["time"])
    dearer = rescore(comps, lodging_cad=x.lodging_cad + 300, fringe=False, **kw)
    assert dearer["share"] > same["share"] and dearer["score"] < same["score"]


def test_time_curve_is_linear_between_its_anchors():
    curve = {"zero_at": 0.4, "full_at": 0.9}
    assert [time_points(r * 100, 100, curve) for r in (0.3, 0.4, 0.65, 0.9, 1.0)] == pytest.approx([0, 0, 0.5, 1, 1])


def test_floor_drops_a_trip_with_too_little_time(vancouver_trip_fixture):
    assert worth_flying(vancouver_trip_fixture, S)
    assert not worth_flying(replace(vancouver_trip_fixture, hours_on_ground=0.09 * 49.5), S)


def test_connection_costs_convenience(nyc_one_stop_trip):
    x = score_trip(nyc_one_stop_trip, city("new_york"), ref("new_york"), S, weather_score=5, history_pct=None)
    assert x.conv_pts == 5 and x.components.convenience == 5 and x.ladder == "typical" and not x.candidate


def test_best_per_window_keeps_one(vancouver_trip_fixture, nyc_one_stop_trip):
    a = score_trip(vancouver_trip_fixture, city("vancouver"), ref("vancouver"), S, weather_score=5, history_pct=None)
    b = score_trip(vancouver_trip_fixture, city("vancouver"), ref("vancouver"), S, weather_score=9, history_pct=None)
    c = score_trip(nyc_one_stop_trip, city("new_york"), ref("new_york"), S, weather_score=5, history_pct=None)
    best = best_per_window([a, b, c])
    assert len(best) == 2 and b in best and c in best
