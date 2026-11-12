# Plan: The permanent self-tuning loop

## Technical context
Python 3.11+, stdlib and pyyaml only (no new dependency). History is the append-only JSONL in `data/history/`
(rows carry `components` and `inputs` since D-76, `share` and `total_cad` since v2). Everything replays from it; no
network anywhere in the loop.

## Where the loop runs, and why
Inside the `radar-daily` routine, as one deterministic command (`python scripts/tune_loop.py --date <date>`), after
the analysis and before the routine's own change. Reasons:
- the scan stays isolated: a tuning bug can never cost a day's scan, and `.github/workflows/` stays untouched;
- the routine already pushes to `main`, opens pull requests and writes the note that reports the loop;
- the routine can propose up to three trials of its own (`--try key=value`), the autoresearch pattern, while the
  arithmetic, the keep-or-revert rule and the file edits stay in code (constitution II);
- the harness is plain Python, so moving it into Actions later is one workflow step.
It reads whatever history is on `main` and never assumes today's scan has landed (D-74, D-79).

## Files
- `radar/config.py`: `Scoring` gains `ladder_mode`, `rolling_ladder`, `rolling_window_days`, `rolling_min_days`,
  `ladder_exclude_ranges` with defaults that reproduce `static`; validation.
- `radar/store.py`: `rolling_flights()`; `radar/main.py` rolls the refs once per scan; `radar/score.py` stores the
  flights ladder it judged with in `inputs.flights_ladder`.
- `config/scoring.yaml`: the rolling keys (`ladder_mode: rolling`); `config/tuning.yaml`: `auto_apply`, the night's
  budget, `frozen` keys.
- `scripts/backtest.py`: load, judge (reusing `radar/score.py`), the hindsight score, the CLI.
- `scripts/tune_loop.py`: guard, surface, neighbours, the night, the config edit with read-back, the logs,
  `--summary` for the Monday note.
- Tests: `tests/test_rolling_ladders.py`, `tests/test_backtest.py`, `tests/test_tune_loop.py`.
- Docs: `docs/TUNING-PLAN.md` (rewritten), `docs/LEARNING-RUN.md`, `routine/PROMPT-daily.md`,
  `routine/PROMPT-tune.md` (superseded stub), `HANDOFF.md`, `SESSION-LOG.md`, `docs/notes/decisions.md` (D-82).
