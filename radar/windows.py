"""Day-off blocks -> trip windows (design section 4), all times in Calgary local time."""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

CALGARY = ZoneInfo("America/Edmonton")
DAY = timedelta(days=1)


@dataclass(frozen=True)
class Window:
    id: str                         # "<day1 ISO>_<pattern>"
    days_off: tuple[date, ...]      # consecutive, len 3 or 4
    window_nights: int              # len(days_off) - 1; hotel nights come from the itinerary
    vacation_days: int              # weekdays in the block that are not stats
    depart_from: datetime           # 19:30 the evening before Day 1
    depart_to: datetime             # 23:59 on Day 1 (soft since D-50: the time score charges for late starts)
    return_from: datetime           # 17:00 on Day N-1
    return_to: datetime             # 16:00 on Day N
    out_dates: tuple[date, date]    # (day before Day 1, Day 1)
    back_dates: tuple[date, date]   # (Day N-1, Day N)
    trip_class: str = "dayoff"      # "dayoff" | "weekend" (D-52)


def _at(d: date, h: int, m: int = 0) -> datetime:
    return datetime.combine(d, time(h, m), tzinfo=CALGARY)


def _window(pattern: str, first: date, n: int, holidays: set[date]) -> Window:
    days = tuple(first + i * DAY for i in range(n))
    return Window(
        id=f"{first.isoformat()}_{pattern}", days_off=days, window_nights=n - 1,
        vacation_days=sum(1 for d in days if d.weekday() < 5 and d not in holidays),
        depart_from=_at(first - DAY, 19, 30), depart_to=_at(first, 23, 59),
        return_from=_at(days[-2], 17), return_to=_at(days[-1], 16),
        out_dates=(first - DAY, first), back_dates=(days[-2], days[-1]),
    )


def generate_windows(today: date, holidays: set[date], min_days: int = 3, max_days: int = 45,
                     extra: set[date] = frozenset(), blocked: set[date] = frozenset()) -> list[Window]:
    """extra: vacation days William marked on the dashboard, treated like stats (they create or extend
    blocks and cost no vacation day); blocked: no window may include one of these dates."""
    holidays = set(holidays) | set(extra)
    sat = today + timedelta(days=(5 - today.weekday()) % 7)
    out = []
    while sat <= today + timedelta(days=max_days + 7):
        out += [_window("fri-off", sat - DAY, 3, holidays), _window("mon-off", sat, 3, holidays)]
        if sat - 2 * DAY in holidays:
            out.append(_window("stat-thu-4d", sat - 2 * DAY, 4, holidays))
        if sat + 3 * DAY in holidays:
            out.append(_window("stat-tue-4d", sat, 4, holidays))
        sat += 7 * DAY
    return [w for w in out if min_days <= (w.days_off[0] - today).days <= max_days and blocked.isdisjoint(w.days_off)]


def _hm(s: str) -> tuple[int, int]:
    h, m = s.split(":")
    return int(h), int(m)


def weekend_windows(today: date, min_days: int, max_days: int, depart_from: str, depart_to: str,
                    blocked: set[date] = frozenset()) -> list[Window]:
    """No day off: leave Friday from depart_from through Saturday depart_to, home in Calgary by Sunday 16:00.
    Id and range use the Friday; a blocked Friday, Saturday or Sunday drops the weekend."""
    fri = today + timedelta(days=(4 - today.weekday()) % 7)
    out = []
    while (fri - today).days <= max_days:
        sat, sun = fri + DAY, fri + 2 * DAY
        if (fri - today).days >= min_days and blocked.isdisjoint((fri, sat, sun)):
            out.append(Window(
                id=f"{fri.isoformat()}_weekend", days_off=(sat, sun), window_nights=1, vacation_days=0,
                depart_from=_at(fri, *_hm(depart_from)), depart_to=_at(sat, *_hm(depart_to)),
                return_from=_at(sat, 17), return_to=_at(sun, 16),
                out_dates=(fri, sat), back_dates=(sat, sun), trip_class="weekend",
            ))
        fri += 7 * DAY
    return out


def class_windows(today: date, s, holidays: set[date], extra: set[date] = frozenset(),
                  blocked: set[date] = frozenset()) -> list[Window]:
    """Both trip classes from config/scoring.yaml: day-off blocks far enough out to get time approved,
    plus weekend-only trips close in (when switched on)."""
    lo = 7 * s.dayoff_min_weeks
    out = generate_windows(today, holidays, lo, lo + 7 * s.trip_classes["dayoff"]["span_weeks"], extra=extra, blocked=blocked)
    if s.weekend_trips:
        wk = s.trip_classes["weekend"]
        out += weekend_windows(today, wk["min_days"], wk["max_days"], wk["depart_from"], wk["depart_to"], blocked)
    return out


def scan_dates(windows: list[Window]) -> tuple[set[date], set[date]]:
    return {d for w in windows for d in w.out_dates}, {d for w in windows for d in w.back_dates}
