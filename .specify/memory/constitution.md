# Spontaneous Travel Radar Constitution

## Core Principles

### I. Zero new spend (NON-NEGOTIABLE)
Free tiers only: SerpApi free (250/month, capped in code at 60), Ticketmaster Discovery, Open-Meteo,
GitHub Actions and Pages on a public repo. No proxies, paid APIs or hosting upgrades. A step that
would cost money stops and is reported instead.

### II. Claude usage is scarce
No daily Claude runs. One weekly digest routine in month one (cheapest model, disabled after four
runs) and a hit routine that stays disabled until month one ends. Routines read pre-computed JSON only.

### III. The trip-window rule is the only hard filter
Evaluated in America/Edmonton: depart 19:30 the evening before Day 1 to 12:00 Day 1; land 17:00 on
Day N-1 to 16:00 on Day N. Two or more connections are dropped. Everything else is a soft score.

### IV. Realistic prices for two
Two adults, CAD, taxes in, `carry_on_bags=1`, `exclude_basic_economy=True` on every flight query.
Prices are one-way sums; a round-trip price is never attached to an independently chosen return leg.

### V. Ponytail simplicity, one check per module
Stdlib and the named libraries (fast-flights pinned, pyyaml, httpx, tzdata) first. No abstraction for
a single use. Each non-trivial module has one small pytest file using recorded fixtures, no network.

## Operating constraints

- Month one is a learning run: `config/scoring.yaml: mode: dry-run`; candidates go to `hits/dry-run/`.
- Secrets live only in `.env` (gitignored) and Actions secrets. Never in code or committed data.
- `data/latest.json` is written atomically; a fetch failure is recorded in health, never fatal.
- History is append-only JSONL per day; no binary database is committed.

## Governance

`BUILD-PLAN.md` and the design in `docs/superpowers/specs/` are the source of truth for scope;
the Spec Kit artifacts in `specs/001-spontaneous-travel-radar/` point at them.
Changes to these principles need William's approval.

**Version**: 1.0.0 | **Ratified**: 2026-11-09 | **Last Amended**: 2026-11-09
