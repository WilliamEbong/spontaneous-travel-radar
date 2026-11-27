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
| 2026-11-25 | 1 | price_curve.share_1 0.75 → 0.85 | 29.24 → 31.03 | 42.38 → 60.50 | deal 0.04, ladder 0.58, good 13%, closer look 0.3%, n 669 | kept: better by 1.79 in 90.6% of 1000 redraws |
| 2026-11-25 | 2 | rolling_ladder.typical 50 → 55 | 31.03 → 34.33 | 60.50 → 65.62 | deal 0.10, ladder 0.58, good 13%, closer look 0.9%, n 669 | reverted: better by 3.30 but in only 65.1% of 1000 redraws of the days (needs 90%) |
| 2026-11-25 | 3 | rolling_ladder.good 25 → 30 | 31.03 → 32.56 | 60.50 → 61.83 | deal 0.04, ladder 0.62, good 17%, closer look 0.3%, n 669 | kept: better by 1.53 in 92.2% of 1000 redraws |
| 2026-11-25 | 4 | price_curve.share_2 1.00 → 1.05 | 32.56 → 32.56 | 61.83 → 61.83 | deal 0.04, ladder 0.62, good 17%, closer look 0.3%, n 669 | reverted: changes no decision up to its bound |
| 2026-11-25 | 5 | rolling_window_days 60 → 90 | 32.56 → 32.56 | 61.83 → 61.83 | deal 0.04, ladder 0.62, good 17%, closer look 0.3%, n 669 | reverted: changes no decision up to its bound |
| 2026-11-25 | 6 | price_curve.share_0 0.60 → 0.65 | 32.56 → 35.85 | 61.83 → 67.94 | deal 0.10, ladder 0.62, good 17%, closer look 0.9%, n 669 | reverted: better by 3.29 but in only 65.1% of 1000 redraws of the days (needs 90%) |
| 2026-11-25 | 7 | dayoff.candidate_threshold 70 → 72 | 32.56 → 30.77 | 61.83 → 56.01 | deal 0.00, ladder 0.62, good 17%, closer look 0.0%, n 669 | reverted: guardrail: trips sent for a closer look 0.0%, band 0.5% to 3.0% |
| 2026-11-25 | 8 | weekend.candidate_threshold 70 → 80 | 32.56 → 32.56 | 61.83 → 61.83 | deal 0.04, ladder 0.62, good 17%, closer look 0.3%, n 669 | reverted: changes no decision up to its bound |
| 2026-11-25 | 9 | rolling_ladder.typical 50 → 45 | 32.56 → 31.68 | 61.83 → 58.37 | deal 0.02, ladder 0.62, good 17%, closer look 0.1%, n 669 | reverted: guardrail: trips sent for a closer look 0.1%, band 0.5% to 3.0% |
| 2026-11-25 | 10 | price_curve.share_1 0.85 → 0.80 | 32.56 → 30.77 | 61.83 → 51.53 | deal 0.00, ladder 0.62, good 17%, closer look 0.0%, n 669 | reverted: guardrail: trips sent for a closer look 0.0%, band 0.5% to 3.0% |
| 2026-11-25 | 11 | rolling_window_days 60 → 30 | 32.56 → 32.56 | 61.83 → 61.83 | deal 0.04, ladder 0.62, good 17%, closer look 0.3%, n 669 | reverted: changes no decision up to its bound |
| 2026-11-25 | 12 | rolling_ladder.good 30 → 35 | 32.56 → 34.58 | 61.83 → 62.40 | deal 0.04, ladder 0.66, good 21%, closer look 0.3%, n 669 | kept: better by 2.02 in 100.0% of 1000 redraws |
| 2026-11-25 | 13 | price_curve.share_0 0.60 → 0.65 | 34.58 → 37.88 | 62.40 → 68.51 | deal 0.10, ladder 0.66, good 21%, closer look 0.9%, n 669 | reverted: better by 3.30 but in only 65.1% of 1000 redraws of the days (needs 90%) |
| 2026-11-25 | 14 | price_curve.share_2 1.00 → 1.05 | 34.58 → 34.58 | 62.40 → 62.40 | deal 0.04, ladder 0.66, good 21%, closer look 0.3%, n 669 | reverted: changes no decision up to its bound |
| 2026-11-25 | 15 | dayoff.candidate_threshold 70 → 72 | 34.58 → 32.79 | 62.40 → 56.58 | deal 0.00, ladder 0.66, good 21%, closer look 0.0%, n 669 | reverted: guardrail: trips sent for a closer look 0.0%, band 0.5% to 3.0% |
| 2026-11-25 | 16 | weekend.candidate_threshold 70 → 80 | 34.58 → 34.58 | 62.40 → 62.40 | deal 0.04, ladder 0.66, good 21%, closer look 0.3%, n 669 | reverted: changes no decision up to its bound |
| 2026-11-25 | night | 16 trials, 3 kept: live on main | 29.24 → 34.58 | 42.38 → 62.40 | hindsight, 17 scan days 2026-11-09 to 2026-11-25 | |
| 2026-11-26 | 1 | rolling_window_days 60 → 90 | 35.08 → 35.08 | 60.37 → 60.37 | deal 0.04, ladder 0.66, good 22%, closer look 0.3%, n 592 | reverted: changes no decision up to its bound |
| 2026-11-26 | 2 | rolling_ladder.typical 50 → 55 | 35.08 → 38.57 | 60.37 → 65.36 | deal 0.11, ladder 0.66, good 22%, closer look 1.0%, n 592 | reverted: better by 3.49 but in only 67.9% of 1000 redraws of the days (needs 90%) |
| 2026-11-26 | 3 | dayoff.candidate_threshold 70 → 68 | 35.08 → 38.57 | 60.37 → 67.47 | deal 0.11, ladder 0.66, good 22%, closer look 1.0%, n 592 | reverted: better by 3.49 but in only 67.9% of 1000 redraws of the days (needs 90%) |
| 2026-11-26 | 4 | price_curve.share_0 0.60 → 0.65 | 35.08 → 38.57 | 60.37 → 66.22 | deal 0.11, ladder 0.66, good 22%, closer look 1.0%, n 592 | reverted: better by 3.49 but in only 67.9% of 1000 redraws of the days (needs 90%) |
| 2026-11-26 | 5 | price_curve.share_2 1.00 → 0.95 | 35.08 → 35.08 | 60.37 → 60.37 | deal 0.04, ladder 0.66, good 22%, closer look 0.3%, n 592 | reverted: changes no decision up to its bound |
| 2026-11-26 | 6 | weekend.candidate_threshold 70 → 62 | 35.08 → 36.88 | 60.37 → 60.92 | deal 0.07, ladder 0.66, good 22%, closer look 0.7%, n 592 | reverted: better by 1.80 but in only 65.1% of 1000 redraws of the days (needs 90%) |
| 2026-11-26 | 7 | rolling_ladder.good 35 → 30 | 35.08 → 33.12 | 60.37 → 60.17 | deal 0.04, ladder 0.62, good 18%, closer look 0.3%, n 592 | reverted: not better by 1 |
| 2026-11-26 | 8 | price_curve.share_1 0.85 → 0.80 | 35.08 → 33.16 | 60.37 → 50.08 | deal 0.00, ladder 0.66, good 22%, closer look 0.0%, n 592 | reverted: guardrail: trips sent for a closer look 0.0%, band 0.5% to 3.0% |
| 2026-11-26 | 9 | price_curve.share_0 0.60 → 0.55 | 35.08 → 34.13 | 60.37 → 56.08 | deal 0.02, ladder 0.66, good 22%, closer look 0.2%, n 592 | reverted: guardrail: trips sent for a closer look 0.2%, band 0.5% to 3.0% |
| 2026-11-26 | 10 | rolling_window_days 60 → 30 | 35.08 → 35.08 | 60.37 → 60.37 | deal 0.04, ladder 0.66, good 22%, closer look 0.3%, n 592 | reverted: changes no decision up to its bound |
| 2026-11-26 | 11 | dayoff.candidate_threshold 70 → 72 | 35.08 → 33.16 | 60.37 → 53.99 | deal 0.00, ladder 0.66, good 22%, closer look 0.0%, n 592 | reverted: guardrail: trips sent for a closer look 0.0%, band 0.5% to 3.0% |
| 2026-11-26 | 12 | weekend.candidate_threshold 70 → 80 | 35.08 → 35.08 | 60.37 → 60.37 | deal 0.04, ladder 0.66, good 22%, closer look 0.3%, n 592 | reverted: changes no decision up to its bound |
| 2026-11-26 | 13 | rolling_ladder.typical 50 → 45 | 35.08 → 34.13 | 60.37 → 56.08 | deal 0.02, ladder 0.66, good 22%, closer look 0.2%, n 592 | reverted: guardrail: trips sent for a closer look 0.2%, band 0.5% to 3.0% |
| 2026-11-26 | 14 | price_curve.share_2 1.00 → 1.05 | 35.08 → 35.08 | 60.37 → 60.37 | deal 0.04, ladder 0.66, good 22%, closer look 0.3%, n 592 | reverted: changes no decision up to its bound |
| 2026-11-26 | night | 14 trials, 0 kept: no change | 35.08 → 35.08 | 60.37 → 60.37 | hindsight, 18 scan days 2026-11-09 to 2026-11-26 | |
| 2026-11-27 | 1 | price_curve.share_0 0.60 → 0.55 | 34.45 → 33.61 | 62.05 → 57.57 | deal 0.02, ladder 0.65, good 23%, closer look 0.1%, n 668 | reverted: guardrail: trips sent for a closer look 0.1%, band 0.5% to 3.0% |
| 2026-11-27 | 2 | rolling_window_days 60 → 30 | 34.45 → 34.45 | 62.05 → 62.05 | deal 0.03, ladder 0.65, good 23%, closer look 0.3%, n 668 | reverted: changes no decision up to its bound |
| 2026-11-27 | 3 | dayoff.candidate_threshold 70 → 72 | 34.45 → 32.74 | 62.05 → 54.28 | deal 0.00, ladder 0.65, good 23%, closer look 0.0%, n 668 | reverted: guardrail: trips sent for a closer look 0.0%, band 0.5% to 3.0% |
| 2026-11-27 | 4 | price_curve.share_1 0.85 → 0.80 | 34.45 → 32.74 | 62.05 → 49.70 | deal 0.00, ladder 0.65, good 23%, closer look 0.0%, n 668 | reverted: guardrail: trips sent for a closer look 0.0%, band 0.5% to 3.0% |
| 2026-11-27 | 5 | weekend.candidate_threshold 70 → 62 | 34.45 → 36.06 | 62.05 → 62.56 | deal 0.07, ladder 0.65, good 23%, closer look 0.6%, n 668 | reverted: better by 1.61 but in only 63.5% of 1000 redraws of the days (needs 90%) |
| 2026-11-27 | 6 | rolling_ladder.typical 50 → 55 | 34.45 → 37.59 | 62.05 → 67.82 | deal 0.10, ladder 0.65, good 23%, closer look 0.9%, n 668 | reverted: better by 3.14 but in only 65.8% of 1000 redraws of the days (needs 90%) |
| 2026-11-27 | 7 | rolling_ladder.good 35 → 30 | 34.45 → 32.91 | 62.05 → 61.92 | deal 0.03, ladder 0.62, good 19%, closer look 0.3%, n 668 | reverted: not better by 1 |
| 2026-11-27 | 8 | price_curve.share_2 1.00 → 1.05 | 34.45 → 34.45 | 62.05 → 62.05 | deal 0.03, ladder 0.65, good 23%, closer look 0.3%, n 668 | reverted: changes no decision up to its bound |
| 2026-11-27 | 9 | price_curve.share_2 1.00 → 0.95 | 34.45 → 34.45 | 62.05 → 62.05 | deal 0.03, ladder 0.65, good 23%, closer look 0.3%, n 668 | reverted: changes no decision up to its bound |
| 2026-11-27 | 10 | price_curve.share_0 0.60 → 0.65 | 34.45 → 38.33 | 62.05 → 68.58 | deal 0.11, ladder 0.65, good 23%, closer look 1.1%, n 668 | kept: better by 3.88 in 91.6% of 1000 redraws |
| 2026-11-27 | 11 | dayoff.candidate_threshold 70 → 72 | 38.33 → 34.45 | 68.58 → 59.92 | deal 0.03, ladder 0.65, good 23%, closer look 0.3%, n 668 | reverted: guardrail: trips sent for a closer look 0.3%, band 0.5% to 3.0% |
| 2026-11-27 | 12 | rolling_window_days 60 → 30 | 38.33 → 38.33 | 68.58 → 68.58 | deal 0.11, ladder 0.65, good 23%, closer look 1.1%, n 668 | reverted: changes no decision up to its bound |
| 2026-11-27 | 13 | price_curve.share_1 0.85 → 0.80 | 38.33 → 33.61 | 68.58 → 54.28 | deal 0.02, ladder 0.65, good 23%, closer look 0.1%, n 668 | reverted: guardrail: trips sent for a closer look 0.1%, band 0.5% to 3.0% |
| 2026-11-27 | 14 | rolling_ladder.typical 50 → 55 | 38.33 → 39.75 | 68.58 → 71.41 | deal 0.14, ladder 0.65, good 23%, closer look 1.4%, n 668 | kept: better by 1.42 in 90.0% of 1000 redraws |
| 2026-11-27 | 15 | rolling_ladder.good 35 → 30 | 39.75 → 38.22 | 71.41 → 71.28 | deal 0.14, ladder 0.62, good 19%, closer look 1.4%, n 668 | reverted: not better by 1 |
| 2026-11-27 | 16 | weekend.candidate_threshold 70 → 80 | 39.75 → 39.75 | 71.41 → 71.41 | deal 0.14, ladder 0.65, good 23%, closer look 1.4%, n 668 | reverted: changes no decision up to its bound |
| 2026-11-27 | night | 16 trials, 2 kept: live on main | 34.45 → 39.75 | 62.05 → 71.41 | hindsight, 19 scan days 2026-11-09 to 2026-11-27 | |
