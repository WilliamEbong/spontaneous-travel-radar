# Spontaneous Travel Radar Constitution

## Core Principles

### I. Zero new spend (NON-NEGOTIABLE)
Free tiers only: SerpApi free (250/month, capped in code at 200), Open-Meteo, Google Flights through
fast-flights, GitHub Actions and Pages on a public repo, Claude routines on William's subscription.
No proxies, paid APIs or hosting upgrades. A step that would cost money stops and is reported instead.

### II. Claude usage is scarce
One daily routine (`radar-daily`, Opus in month one) that stops as soon as there is nothing to do.
Its research pass runs on candidates only (at most three a day, cached seven days). Routines read
pre-computed JSON and repo files; arithmetic and file layout live in code (`radar.main finalize`).

### III. The trip-window rule is the only hard filter
Evaluated in America/Edmonton, one rule per trip class (D-50, D-52). Day-off trips: leave from 19:30
the evening before Day 1 through 23:59 on Day 1, home by 16:00 on the last day off. Weekend trips:
leave Friday 17:30 through Saturday 12:00, home by Sunday 16:00, non-stop, 3 h or less in the air.
Two or more connections are dropped. Everything else is a soft score.

### IV. Realistic prices for two
Two adults, CAD, taxes in, `carry_on_bags=1` on every flight query, basic fares allowed (AC and
WestJet Basic include a carry-on; Google prices the bag for Flair). Prices are one-way sums. A trip
is judged by its complete cost for two (flights, lodging, transfers) against what its route
normally costs (`config/references.yaml`), never against a fixed budget.

### V. Ponytail simplicity, one check per module
Stdlib and the named libraries (fast-flights pinned, pyyaml, httpx, tzdata) first. No abstraction for
a single use. Each non-trivial module has one small pytest file using recorded fixtures, no network.

## Operating constraints

- Month one is a learning run: `config/scoring.yaml: mode: dry-run`; nothing is emailed, hits and
  near misses show on the dashboard.
- Secrets live only in `.env` (gitignored) and Actions secrets. Never in code or committed data.
- `data/latest.json` is written atomically; a fetch failure is recorded in health, never fatal.
- History is append-only JSONL per day; no binary database is committed.

## Governance

`BUILD-PLAN-v2.md` (its "What William decided" section), `BUILD-PLAN.md` and the design in
`docs/superpowers/specs/` are the source of truth for scope; the Spec Kit artifacts in `specs/` point
at them. Changes to these principles need William's approval. v1.1.0 records his v2 decisions of
2026-11-09 (relative prices, basic fares, Ticketmaster removed, three passes).

**Version**: 1.1.0 | **Ratified**: 2026-11-09 | **Last Amended**: 2026-11-09
