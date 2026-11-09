from datetime import date, datetime

from radar.windows import CALGARY, generate_windows, scan_dates


def test_extra_day_off_counts_like_a_stat():
    ws = generate_windows(date(2026, 11, 20), set(), extra={date(2026, 12, 10)})   # a Thursday taken as vacation
    w = next(w for w in ws if w.id == "2026-12-10_stat-thu-4d")
    assert w.days_off == (date(2026, 12, 10), date(2026, 12, 11), date(2026, 12, 12), date(2026, 12, 13))
    assert w.vacation_days == 1                                                      # only the Friday still costs a day
    assert "2026-12-10_stat-thu-4d" not in {w.id for w in generate_windows(date(2026, 11, 20), set())}


def test_blocked_date_drops_every_window_touching_it():
    ws = generate_windows(date(2026, 11, 20), set(), blocked={date(2026, 12, 12)})  # a Saturday
    ids = {w.id for w in ws}
    assert ws and all(date(2026, 12, 12) not in w.days_off for w in ws)
    assert not ids & {"2026-12-11_fri-off", "2026-12-12_mon-off"} and "2026-12-18_fri-off" in ids


def test_plain_weekend_two_patterns():
    ws = generate_windows(date(2026, 11, 10), set())
    ids = {w.id for w in ws}
    assert "2026-11-20_fri-off" in ids and "2026-11-21_mon-off" in ids
    w = next(w for w in ws if w.id == "2026-11-20_fri-off")
    assert w.window_nights == 2 and w.vacation_days == 1
    assert w.depart_from == datetime(2026, 11, 19, 19, 30, tzinfo=CALGARY)
    assert w.depart_to == datetime(2026, 11, 20, 12, 0, tzinfo=CALGARY)
    assert w.return_from == datetime(2026, 11, 21, 17, 0, tzinfo=CALGARY)
    assert w.return_to == datetime(2026, 11, 22, 16, 0, tzinfo=CALGARY)


def test_monday_stat_costs_no_vacation_day():
    ws = generate_windows(date(2027, 1, 20), {date(2027, 2, 15)})
    w = next(w for w in ws if w.id == "2027-02-13_mon-off")
    assert w.vacation_days == 0


def test_good_friday_costs_no_vacation_day():
    ws = generate_windows(date(2027, 3, 1), {date(2027, 3, 26)})
    w = next(w for w in ws if w.id == "2027-03-26_fri-off")
    assert w.vacation_days == 0 and w.days_off == (date(2027, 3, 26), date(2027, 3, 27), date(2027, 3, 28))


def test_thursday_stat_makes_four_day_block():
    ws = generate_windows(date(2027, 6, 10), {date(2027, 7, 1)})
    w = next(w for w in ws if w.id == "2027-07-01_stat-thu-4d")
    assert w.days_off == (date(2027, 7, 1), date(2027, 7, 2), date(2027, 7, 3), date(2027, 7, 4))
    assert w.window_nights == 3 and w.vacation_days == 1
    assert w.depart_from == datetime(2027, 6, 30, 19, 30, tzinfo=CALGARY)
    assert w.return_to == datetime(2027, 7, 4, 16, 0, tzinfo=CALGARY)


def test_tuesday_stat_makes_four_day_block():
    ws = generate_windows(date(2027, 12, 1), {date(2027, 12, 27), date(2027, 12, 28)})
    w = next(w for w in ws if w.id == "2027-12-25_stat-tue-4d")
    assert w.days_off[-1] == date(2027, 12, 28) and w.vacation_days == 0


def test_lookahead_bounds():
    ws = generate_windows(date(2026, 11, 10), set(), 3, 45)
    assert ws and all(3 <= (w.days_off[0] - date(2026, 11, 10)).days <= 45 for w in ws)


def test_scan_dates_shared():
    ws = generate_windows(date(2026, 11, 10), set())
    outs, backs = scan_dates([w for w in ws if w.days_off[0] in (date(2026, 11, 20), date(2026, 11, 21))])
    assert outs == {date(2026, 11, 19), date(2026, 11, 20), date(2026, 11, 21)}
    assert backs == {date(2026, 11, 21), date(2026, 11, 22), date(2026, 11, 23)}
