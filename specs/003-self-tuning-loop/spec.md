# Spec: The permanent self-tuning loop

Approved by William on 2026-11-12 (design agreed in the session that started this build). Replaces the one-time
2026-12-09 retune (`radar-tune`) and the 2026-12-08 stop of `radar-daily`. Full rules: `docs/TUNING-PLAN.md`.

## Overview
The radar must never stop. It keeps scanning, writing the daily note and checking health with no end date, and it
improves its own price judgment every night the way Karpathy's autoresearch does: a fixed harness, one editable
surface, one number, a fixed budget per experiment, keep the change if the number improves and revert it if not,
forever. William edits only the instructions. He will not look at travel until February, so it runs unattended.

## User scenarios
- **US1 (P1)** The daily routine runs every day with no end date; 2026-12-08 gets a one-time month-one summary that
  ends nothing.
- **US2 (P1)** Every night, once 14 scan days exist, 10 to 20 trial changes to the price judgment are replayed
  offline against the logged history; a change is kept only when the hindsight price score beats the current one by
  more than the noise margin without breaking the calibration guardrails, and it goes live on its own as one commit.
- **US3 (P1)** Before 14 scan days exist the loop does nothing and says "collecting, N of 14 days".
- **US4 (P2)** Each route's flight ladder follows its own last 60 days of fares once it has 14 days of them.
- **US5 (P2)** The Monday note tells William, in plain words on a phone, what was kept that week and how the score
  moved.
- **US6 (P3)** Once William's book/skip taps reach 30 rows, they blend into the number and the taste weights unlock.

## Functional requirements
- **FR-301** `routine/PROMPT-daily.md` has no date window; the 2026-12-08 summary is one-time and changes nothing else.
- **FR-302** `scripts/backtest.py` re-scores the logged history under a given config, offline, deterministic, no
  network, and prints the score with its components (train, holdout, counts, rates). Under two minutes.
- **FR-303** `ladder_mode: rolling`: per route, percentiles 10/25/50 of `price_pp` over the 60 days before the scan
  day, at least 14 scan days, windows starting 2026-12-18 to 2027-01-04 excluded, exceptional < good < typical by at
  least 1 CAD; the static ladder until then. `static` reproduces the old behaviour. The scan and the backtest share
  one function.
- **FR-304** The hindsight price score is defined in `docs/TUNING-PLAN.md` (b): near the eventual low, unfinished
  weekends, F0.5, the 7-day holdout, the guardrails, the noise margin. Every score is stored with its inputs and
  components (`data/tuning/runs.jsonl`) so it can be explained and re-scored without re-fetching.
- **FR-305** `scripts/tune_loop.py`: 10 to 20 trials a night over the surface in `docs/TUNING-PLAN.md` (c) only;
  taste weights frozen until `data/labels.jsonl` has 30+ rows; every trial appended to `docs/tuning-log.md`; one
  switch `auto_apply` in `config/tuning.yaml` (on: one `tune:` commit on `main`; off: a pull request).
- **FR-306** Start guard: under 14 scan days in `data/history/`, print "collecting, N of 14 days" and write nothing.
- **FR-307** Selection never sees the holdout: trial decisions use the train days only; the holdout can only veto
  a whole night.
- **FR-308** Section C of the daily prompt gives the loop a narrow exemption for its surface; everything else on
  the never-touch list stays; `mode` stays `dry-run`.

## Success criteria
- **SC-301** `pytest -q` green, with tests for replay determinism, the metric on a hand-built fixture, keep and
  revert, the 14-day guard and the holdout never reaching selection, plus the rolling ladders.
- **SC-302** `python scripts/backtest.py` runs offline on the current data and prints the score with components.
- **SC-303** A dry run of the trial loop on a fixture shows kept and reverted entries in the log.
