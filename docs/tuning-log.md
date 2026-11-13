# Tuning log

Every trial of the nightly self-tuning loop (`scripts/tune_loop.py`, `docs/TUNING-PLAN.md`, D-82), newest last.
Score: the hindsight price score on the train days, 0 to 100, higher is better; a trial is kept only when it wins by
1 point or more without crossing a guardrail. Holdout: the same score on the last 7 scan days, never used to pick a
trial (it can only veto a whole night). Parts: deal and ladder F0.5 (candidates, good-or-better calls), the share of
judged trips called good or better and sent for a closer look. Undo a kept change: revert its `tune:` commit.

| date | # | change | score | holdout | parts after | result |
|---|---|---|---|---|---|---|
