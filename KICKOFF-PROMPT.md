# Kickoff prompt for the build session

Paste everything below the line into a fresh Claude Code session (Opus 5.5) opened on the folder `C:\Users\Owner\OneDrive\Documents\Spontaneous Travel`.

---

Build the Spontaneous Travel Radar. Work in this folder: `C:\Users\Owner\OneDrive\Documents\Spontaneous Travel`.

Read these two files first, in this order, before doing anything else:
1. `docs/superpowers/specs/2026-11-09-spontaneous-travel-radar-design.md` (the design: what and why)
2. `BUILD-PLAN.md` (the step-by-step plan: how; it has a Codex review section at the end whose accepted changes are already folded in)

Then execute `BUILD-PLAN.md` task by task, in order, starting with Task 0 (the `fast-flights` smoke test). Riskiest thing first; do not skip it.

Rules that apply (from my `~/.claude/CLAUDE.md`):
- This is a new app build, so it is a Spec Kit project: run the `specify init` sequence in Task 1 exactly as written, then drive the work through the speckit-* skills (constitution once, then specify → plan → tasks → implement → converge), feeding `BUILD-PLAN.md` into speckit-plan and speckit-tasks. Do not use superpowers brainstorming, writing-plans, executing-plans or subagent-driven-development here.
- Ponytail: stdlib and the named libraries first, no abstraction for a single use, shortest working diff, one small runnable check per non-trivial module. Mark deliberate corner-cuts with a `# ponytail:` comment.
- Before writing code against `fast-flights`, SerpApi, Ticketmaster or Open-Meteo, fetch current docs with the context7 MCP tools (or the vendor page). Do not guess signatures.
- After building the dashboard, verify it with the playwright MCP tools (localhost and the live Pages URL): snapshot, confirm the table and health panel render, no console errors, no horizontal scroll at 375 px. State what was verified.
- Commit after every task with conventional-commit messages (`feat:`, `chore:`, `ci:`, `docs:`, `test:`).

Hard constraints (never trade these away):
- $0 new spend: free tiers only (SerpApi free, Ticketmaster Discovery, Open-Meteo, GitHub Actions and Pages on a public repo). No proxies, no paid APIs. If a step would cost money, stop and tell me instead.
- Minimal Claude usage: no daily Claude runs. One weekly digest routine (cheapest model) and a hit routine that stays inert until month one ends.
- Two adults, prices in CAD with carry-on included (`Passengers(adults=2)`, `currency="CAD"`, `carry_on_bags=1`, `exclude_basic_economy=True`).
- The trip-window rule from the design §4 is the only hard filter; everything else is a soft score.
- Month one is a learning run: `config/scoring.yaml` stays `mode: dry-run`.

Make decisions yourself and log them in `docs/notes/decisions.md`. Stop and report to me only on a real blocker. Known possible blockers:
- `gh` not authenticated → tell me to run `gh auth login`.
- Missing API keys → I need to create free accounts at serpapi.com (free tier, 250 searches/month) and developer.ticketmaster.com, then put `SERPAPI_KEY` and `TICKETMASTER_KEY` in `.env`. Build everything else while waiting; the collector must run without them (hotel check reports `skipped: no-key`, events return empty).
- Google blocks GitHub Actions IPs in Task 0/11 → switch to the PC Task Scheduler fallback in Task 11 and tell me.

Done for day one means:
- Public repo `WilliamEbong/spontaneous-travel-radar` live, Spec Kit initialised, all tests passing (`pytest -q`).
- One real scan committed by the workflow (or the PC fallback), `data/latest.json` present, `mode: dry-run`.
- GitHub Pages dashboard live and verified with Playwright, URL in `README.md`.
- Weekly digest routine created (Monday 07:00 Calgary time); hit routine created but inert; `routine/CAPABILITIES.md` filled from the probe run.
- `docs/notes/day-one-smoke.md`, `docs/notes/decisions.md` and `docs/LEARNING-RUN.md` written.

When done, give me: the repo and dashboard URLs, the routine URLs, the smoke-test findings in three lines, the decisions you made that I should check, and the eight defaulted questions from the design §11 as a checklist.
