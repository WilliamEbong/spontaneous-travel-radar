# Spontaneous Travel Radar

A tracker that watches round-trip fares for two from Calgary (YYC) to about 20 North American cities, scores complete weekend trips (flights + two nights + context), and alerts only on deals that would be crazy to pass up.

Start here:

1. `docs/superpowers/specs/2026-11-09-spontaneous-travel-radar-design.md` — the design: the trip window rule, the city list, the two-tier architecture (free collector + rare Claude routine), the scoring model and calibration bands.
2. `BUILD-PLAN.md` — the detailed, step-by-step build plan (written after the design, reviewed by Codex).
3. `KICKOFF-PROMPT.md` — paste into a fresh Claude Code session (Opus 5.5) to start the build.

Constraints that shape everything: $0 new spend, minimal Claude usage, two adults, home in Calgary by 4pm on the last day off.
