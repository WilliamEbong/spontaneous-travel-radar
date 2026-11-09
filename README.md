# Spontaneous Travel Radar

A free tracker that watches fares for two from Calgary (YYC) to 20 North American cities, keeps only
trips that fit a one-vacation-day weekend (leave after 7:30pm the evening before, home by 4pm on the
last day off), scores complete trips (flights, two nights, context), logs every quote, and shows the
best of them on a static dashboard. Month one is a dry-run learning period: no alerts.

- Dashboard: https://williamebong.github.io/spontaneous-travel-radar/
- Design: `docs/superpowers/specs/2026-11-09-spontaneous-travel-radar-design.md`
- Build plan: `BUILD-PLAN.md`; build decisions: `docs/notes/decisions.md`
- Config: `config/` (cities, holidays, scoring, airlines)

Run locally (Python 3.12):

```
uv venv --python 3.12 .venv
uv pip install --python .venv -e ".[dev]"
.venv\Scripts\python -m radar.main scan --offline
.venv\Scripts\python -m pytest -q
```

Constraints that shape everything: $0 new spend, minimal Claude usage, two adults, home in Calgary by
4pm on the last day off.
