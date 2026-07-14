---
id: TASK-015
title: Add trading-day replay window contract
status: ready
priority: P0
owner: unassigned
depends_on:
  - TASK-014
write_scope:
  - backend/intraday/training_window.py
  - tests/test_intraday_training_window.py
read_scope:
  - backend/intraday/session.py
  - backend/intraday/replay_clock.py
  - docs/superpowers/specs/2026-07-14-historical-context-trading-day-blind-box-design.md
  - docs/superpowers/plans/2026-07-14-historical-context-blind-box.md
quality_profiles:
  - phase2
---

## Goal
Implement the pure immutable trading-day window contract so a limit such as 150 means 150 distinct data-bearing trading dates rather than 150 base or displayed candles.

## Acceptance Criteria
- [ ] max_training_days counts distinct dates from start_time.
- [ ] Zero uses all remaining trading dates.
- [ ] The cutoff is the final base timestamp of the selected final trading date.
- [ ] The returned replay frame starts exactly at start_time and never crosses the cutoff.
- [ ] Holidays, gaps, and suspensions are handled from actual data order.
- [ ] Negative limits, duplicate/unsorted timestamps, and missing start_time raise ValueError.
- [ ] Input frames are not mutated.
- [ ] Focused tests pass.

## Constraints
Modify only the two write-scope files. Do not modify __init__.py, Flask, frontend, existing tests, task files, dependencies, or Git state. Do not commit.
