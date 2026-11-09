# Plan: Spontaneous Travel Radar

The implementation plan is `BUILD-PLAN.md` at the repo root (Codex-reviewed; interfaces, tests and
file layout per task). This file records where it lives and what changed during the build.

- Stack: Python 3.12, fast-flights 3.1.0 (fetch only; own payload parser, see
  `docs/notes/day-one-smoke.md`), pyyaml, httpx, tzdata, pytest; GitHub Actions cron with a Pages
  artifact deploy; vanilla HTML/JS dashboard.
- Build-time decisions: `docs/notes/decisions.md`.
