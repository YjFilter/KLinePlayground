---
id: TASK-017
title: Add intraday blind-box selector
status: ready
priority: P0
owner: unassigned
depends_on:
  - TASK-014
write_scope:
  - backend/intraday/random_selector.py
  - tests/test_intraday_random_selector.py
read_scope:
  - backend/data_manager.py
  - backend/intraday/service.py
  - backend/intraday/training_window.py
  - docs/superpowers/specs/2026-07-14-historical-context-trading-day-blind-box-design.md
  - docs/superpowers/plans/2026-07-14-historical-context-blind-box.md
quality_profiles:
  - phase1
---

## Goal
Implement deterministic, bounded-retry blind-box selection of a BaoStock-supported stock and a real intraday start date inside the requested range.

## Acceptance Criteria
- [ ] The selected date is a real data-bearing trading date inside date_start/date_end.
- [ ] The selected start timestamp is that date's first real 30-minute timestamp.
- [ ] BSE prefixes 43/83/87/92 are rejected.
- [ ] Candidates must provide at least 730 days of prior market context.
- [ ] Non-zero max_training_days requires enough remaining distinct trading dates.
- [ ] Empty, invalid, insufficient, and source-error candidates are retried.
- [ ] Attempts are bounded and final errors are actionable.
- [ ] Randomness is injectable for deterministic tests.
- [ ] Focused tests pass without live network access.

## Constraints
Modify only the two write-scope files. Do not modify __init__.py, Flask, frontend, existing tests, task files, dependencies, or Git state. Do not commit.
