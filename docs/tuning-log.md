# Tuning log

Every trial of the nightly self-tuning loop (`scripts/tune_loop.py`, `docs/TUNING-PLAN.md`, D-82), newest last.
Score: the hindsight price score on the train days, 0 to 100, higher is better; a trial is kept only when it wins by
1 point or more without crossing a guardrail. Holdout: the same score on the last 7 scan days, never used to pick a
trial (it can only veto a whole night). Parts: deal and ladder F0.5 (candidates, good-or-better calls), the share of
judged trips called good or better and sent for a closer look. Undo a kept change: revert its `tune:` commit.

| date | # | change | score | holdout | parts after | result |
|---|---|---|---|---|---|---|
| 2026-11-22 | 1 | price_curve.share_0 0.60 → 0.55 | 0.00 → 0.00 | 0.00 → 0.00 | deal 0.00, ladder 0.00, good 0%, closer look 0.0%, n 369 | reverted: not better by 1 |
| 2026-11-22 | 2 | rolling_ladder.good 25 → 20 | 0.00 → 0.00 | 0.00 → 0.00 | deal 0.00, ladder 0.00, good 0%, closer look 0.0%, n 369 | reverted: not better by 1 |
| 2026-11-22 | 3 | weekend.candidate_threshold 70 → 68 | 0.00 → 0.00 | 0.00 → 0.00 | deal 0.00, ladder 0.00, good 0%, closer look 0.0%, n 369 | reverted: not better by 1 |
| 2026-11-22 | 4 | rolling_window_days 60 → 45 | 0.00 → 0.00 | 0.00 → 0.00 | deal 0.00, ladder 0.00, good 0%, closer look 0.0%, n 369 | reverted: not better by 1 |
| 2026-11-22 | 5 | dayoff.candidate_threshold 70 → 68 | 0.00 → 0.00 | 0.00 → 0.00 | deal 0.00, ladder 0.00, good 0%, closer look 0.0%, n 369 | reverted: not better by 1 |
| 2026-11-22 | 6 | price_curve.share_2 1.00 → 0.95 | 0.00 → 0.00 | 0.00 → 0.00 | deal 0.00, ladder 0.00, good 0%, closer look 0.0%, n 369 | reverted: not better by 1 |
| 2026-11-22 | 7 | price_curve.share_1 0.75 → 0.70 | 0.00 → 0.00 | 0.00 → 0.00 | deal 0.00, ladder 0.00, good 0%, closer look 0.0%, n 369 | reverted: not better by 1 |
| 2026-11-22 | 8 | rolling_ladder.typical 50 → 45 | 0.00 → 0.00 | 0.00 → 0.00 | deal 0.00, ladder 0.00, good 0%, closer look 0.0%, n 369 | reverted: not better by 1 |
| 2026-11-22 | 9 | dayoff.candidate_threshold 70 → 72 | 0.00 → 0.00 | 0.00 → 0.00 | deal 0.00, ladder 0.00, good 0%, closer look 0.0%, n 369 | reverted: not better by 1 |
| 2026-11-22 | 10 | rolling_ladder.good 25 → 30 | 0.00 → 0.00 | 0.00 → 0.00 | deal 0.00, ladder 0.00, good 0%, closer look 0.0%, n 369 | reverted: not better by 1 |
| 2026-11-22 | 11 | price_curve.share_2 1.00 → 1.05 | 0.00 → 0.00 | 0.00 → 0.00 | deal 0.00, ladder 0.00, good 0%, closer look 0.0%, n 369 | reverted: not better by 1 |
| 2026-11-22 | 12 | price_curve.share_0 0.60 → 0.65 | 0.00 → 0.00 | 0.00 → 0.00 | deal 0.00, ladder 0.00, good 0%, closer look 0.0%, n 369 | reverted: not better by 1 |
| 2026-11-22 | 13 | price_curve.share_1 0.75 → 0.80 | 0.00 → 0.00 | 0.00 → 0.00 | deal 0.00, ladder 0.00, good 0%, closer look 0.0%, n 369 | reverted: not better by 1 |
| 2026-11-22 | 14 | rolling_window_days 60 → 75 | 0.00 → 0.00 | 0.00 → 0.00 | deal 0.00, ladder 0.00, good 0%, closer look 0.0%, n 369 | reverted: not better by 1 |
| 2026-11-22 | 15 | rolling_ladder.typical 50 → 55 | 0.00 → 0.00 | 0.00 → 0.00 | deal 0.00, ladder 0.00, good 0%, closer look 0.0%, n 369 | reverted: not better by 1 |
| 2026-11-22 | 16 | weekend.candidate_threshold 70 → 72 | 0.00 → 0.00 | 0.00 → 0.00 | deal 0.00, ladder 0.00, good 0%, closer look 0.0%, n 369 | reverted: not better by 1 |
| 2026-11-22 | night | 16 trials, 0 kept: no change | 0.00 → 0.00 | 0.00 → 0.00 | hindsight, 14 scan days 2026-11-09 to 2026-11-22 | |
| 2026-11-23 | 1 | price_curve.share_0 0.60 → 0.65 | 0.00 → 0.00 | 9.16 → 9.16 | deal 0.00, ladder 0.00, good 0%, closer look 0.0%, n 591 | reverted: not better by 1 |
| 2026-11-23 | 2 | rolling_ladder.good 25 → 30 | 0.00 → 0.00 | 9.16 → 10.42 | deal 0.00, ladder 0.00, good 0%, closer look 0.0%, n 591 | reverted: not better by 1 |
| 2026-11-23 | 3 | weekend.candidate_threshold 70 → 72 | 0.00 → 0.00 | 9.16 → 9.16 | deal 0.00, ladder 0.00, good 0%, closer look 0.0%, n 591 | reverted: not better by 1 |
| 2026-11-23 | 4 | rolling_window_days 60 → 75 | 0.00 → 0.00 | 9.16 → 9.16 | deal 0.00, ladder 0.00, good 0%, closer look 0.0%, n 591 | reverted: not better by 1 |
| 2026-11-23 | 5 | dayoff.candidate_threshold 70 → 72 | 0.00 → 0.00 | 9.16 → 9.16 | deal 0.00, ladder 0.00, good 0%, closer look 0.0%, n 591 | reverted: not better by 1 |
| 2026-11-23 | 6 | price_curve.share_2 1.00 → 1.05 | 0.00 → 0.00 | 9.16 → 9.16 | deal 0.00, ladder 0.00, good 0%, closer look 0.0%, n 591 | reverted: not better by 1 |
| 2026-11-23 | 7 | price_curve.share_1 0.75 → 0.80 | 0.00 → 0.00 | 9.16 → 9.16 | deal 0.00, ladder 0.00, good 0%, closer look 0.0%, n 591 | reverted: not better by 1 |
| 2026-11-23 | 8 | rolling_ladder.typical 50 → 55 | 0.00 → 0.00 | 9.16 → 9.16 | deal 0.00, ladder 0.00, good 0%, closer look 0.0%, n 591 | reverted: not better by 1 |
| 2026-11-23 | 9 | weekend.candidate_threshold 70 → 68 | 0.00 → 0.00 | 9.16 → 9.16 | deal 0.00, ladder 0.00, good 0%, closer look 0.0%, n 591 | reverted: not better by 1 |
| 2026-11-23 | 10 | rolling_ladder.typical 50 → 45 | 0.00 → 0.00 | 9.16 → 9.16 | deal 0.00, ladder 0.00, good 0%, closer look 0.0%, n 591 | reverted: not better by 1 |
| 2026-11-23 | 11 | dayoff.candidate_threshold 70 → 68 | 0.00 → 0.00 | 9.16 → 9.16 | deal 0.00, ladder 0.00, good 0%, closer look 0.0%, n 591 | reverted: not better by 1 |
| 2026-11-23 | 12 | price_curve.share_1 0.75 → 0.70 | 0.00 → 0.00 | 9.16 → 9.16 | deal 0.00, ladder 0.00, good 0%, closer look 0.0%, n 591 | reverted: not better by 1 |
| 2026-11-23 | 13 | price_curve.share_2 1.00 → 0.95 | 0.00 → 0.00 | 9.16 → 9.16 | deal 0.00, ladder 0.00, good 0%, closer look 0.0%, n 591 | reverted: not better by 1 |
| 2026-11-23 | 14 | price_curve.share_0 0.60 → 0.55 | 0.00 → 0.00 | 9.16 → 9.16 | deal 0.00, ladder 0.00, good 0%, closer look 0.0%, n 591 | reverted: not better by 1 |
| 2026-11-23 | 15 | rolling_window_days 60 → 45 | 0.00 → 0.00 | 9.16 → 9.16 | deal 0.00, ladder 0.00, good 0%, closer look 0.0%, n 591 | reverted: not better by 1 |
| 2026-11-23 | 16 | rolling_ladder.good 25 → 20 | 0.00 → 0.00 | 9.16 → 7.36 | deal 0.00, ladder 0.00, good 0%, closer look 0.0%, n 591 | reverted: not better by 1 |
| 2026-11-23 | night | 16 trials, 0 kept: no change | 0.00 → 0.00 | 9.16 → 9.16 | hindsight, 15 scan days 2026-11-09 to 2026-11-23 | |
| 2026-11-24 | 1 | price_curve.share_1 0.75 → 0.65 | 27.90 → 27.90 | 33.97 → 33.97 | deal 0.00, ladder 0.56, good 11%, closer look 0.0%, n 542 | reverted: changes no decision up to its bound |
| 2026-11-24 | 2 | rolling_ladder.typical 50 → 40 | 27.90 → 27.90 | 33.97 → 33.97 | deal 0.00, ladder 0.56, good 11%, closer look 0.0%, n 542 | reverted: changes no decision up to its bound |
| 2026-11-24 | 3 | rolling_ladder.good 25 → 20 | 27.90 → 25.20 | 33.97 → 35.85 | deal 0.00, ladder 0.50, good 8%, closer look 0.0%, n 542 | reverted: not better by 1 |
| 2026-11-24 | 4 | price_curve.share_2 1.00 → 0.95 | 27.90 → 27.90 | 33.97 → 33.97 | deal 0.00, ladder 0.56, good 11%, closer look 0.0%, n 542 | reverted: changes no decision up to its bound |
| 2026-11-24 | 5 | rolling_window_days 60 → 30 | 27.90 → 27.90 | 33.97 → 33.97 | deal 0.00, ladder 0.56, good 11%, closer look 0.0%, n 542 | reverted: changes no decision up to its bound |
| 2026-11-24 | 6 | price_curve.share_0 0.60 → 0.50 | 27.90 → 27.90 | 33.97 → 33.97 | deal 0.00, ladder 0.56, good 11%, closer look 0.0%, n 542 | reverted: changes no decision up to its bound |
| 2026-11-24 | 7 | dayoff.candidate_threshold 70 → 60 | 27.90 → 29.05 | 33.97 → 45.78 | deal 0.02, ladder 0.56, good 11%, closer look 0.2%, n 542 | reverted: better by 1.15 but in only 68.0% of 1000 redraws of the days (needs 90%) |
| 2026-11-24 | 8 | weekend.candidate_threshold 70 → 60 | 27.90 → 27.90 | 33.97 → 33.97 | deal 0.00, ladder 0.56, good 11%, closer look 0.0%, n 542 | reverted: changes no decision up to its bound |
| 2026-11-24 | 9 | rolling_ladder.good 25 → 30 | 27.90 → 29.33 | 33.97 → 35.60 | deal 0.00, ladder 0.59, good 15%, closer look 0.0%, n 542 | reverted: better by 1.43 but in only 89.5% of 1000 redraws of the days (needs 90%) |
| 2026-11-24 | 10 | price_curve.share_0 0.60 → 0.70 | 27.90 → 27.90 | 33.97 → 33.97 | deal 0.00, ladder 0.56, good 11%, closer look 0.0%, n 542 | reverted: changes no decision up to its bound |
| 2026-11-24 | 11 | rolling_ladder.typical 50 → 60 | 27.90 → 27.90 | 33.97 → 33.97 | deal 0.00, ladder 0.56, good 11%, closer look 0.0%, n 542 | reverted: changes no decision up to its bound |
| 2026-11-24 | 12 | weekend.candidate_threshold 70 → 80 | 27.90 → 27.90 | 33.97 → 33.97 | deal 0.00, ladder 0.56, good 11%, closer look 0.0%, n 542 | reverted: changes no decision up to its bound |
| 2026-11-24 | 13 | rolling_window_days 60 → 90 | 27.90 → 27.90 | 33.97 → 33.97 | deal 0.00, ladder 0.56, good 11%, closer look 0.0%, n 542 | reverted: changes no decision up to its bound |
| 2026-11-24 | 14 | price_curve.share_1 0.75 → 0.85 | 27.90 → 29.05 | 33.97 → 36.30 | deal 0.02, ladder 0.56, good 11%, closer look 0.2%, n 542 | reverted: better by 1.15 but in only 68.0% of 1000 redraws of the days (needs 90%) |
| 2026-11-24 | 15 | price_curve.share_2 1.00 → 1.05 | 27.90 → 27.90 | 33.97 → 33.97 | deal 0.00, ladder 0.56, good 11%, closer look 0.0%, n 542 | reverted: changes no decision up to its bound |
| 2026-11-24 | 16 | dayoff.candidate_threshold 70 → 80 | 27.90 → 27.90 | 33.97 → 33.97 | deal 0.00, ladder 0.56, good 11%, closer look 0.0%, n 542 | reverted: changes no decision up to its bound |
| 2026-11-24 | night | 16 trials, 0 kept: no change | 27.90 → 27.90 | 33.97 → 33.97 | hindsight, 15 scan days 2026-11-09 to 2026-11-23 | |
