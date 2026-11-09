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
    depart_to: datetime             # 12:00 on Day 1
    return_from: datetime           # 17:00 on Day N-1
    return_to: datetime             # 16:00 on Day N
    out_dates: tuple[date, date]    # (day before Day 1, Day 1)
    back_dates: tuple[date, date]   # (Day N-1, Day N)


def _at(d: date, h: int, m: int = 0) -> datetime:
    return datetime.combine(d, time(h, m), tzinfo=CALGARY)


def _window(pattern: str, first: date, n: int, holidays: set[date]) -> Window:
    days = tuple(first + i * DAY for i in range(n))
    return Window(
        id=f"{first.isoformat()}_{pattern}", days_off=days, window_nights=n - 1,
        vacation_days=sum(1 for d in days if d.weekday() < 5 and d not in holidays),
        depart_from=_at(first - DAY, 19, 30), depart_to=_at(first, 12),
        return_from=_at(days[-2], 17), return_to=_at(days[-1], 16),
        out_dates=(first - DAY, first), back_dates=(days[-2], days[-1]),
    )


def generate_windows(today: date, holidays: set[date], min_days: int = 3, max_days: int = 45) -> list[Window]:
    sat = today + timedelta(days=(5 - today.weekday()) % 7)
    out = []
    while sat <= today + timedelta(days=max_days + 7):
        out += [_window("fri-off", sat - DAY, 3, holidays), _window("mon-off", sat, 3, holidays)]
        if sat - 2 * DAY in holidays:
            out.append(_window("stat-thu-4d", sat - 2 * DAY, 4, holidays))
        if sat + 3 * DAY in holidays:
            out.append(_window("stat-tue-4d", sat, 4, holidays))
        sat += 7 * DAY
    return [w for w in out if min_days <= (w.days_off[0] - today).days <= max_days]


def scan_dates(windows: list[Window]) -> tuple[set[date], set[date]]:
    return {d for w in windows for d in w.out_dates}, {d for w in windows for d in w.back_dates}
