---
id: TASK-016
title: Add read-only intraday chart windows
status: ready
priority: P0
owner: unassigned
depends_on:
  - TASK-014
write_scope:
  - backend/intraday/chart_window.py
  - tests/test_intraday_chart_window.py
read_scope:
  - backend/intraday/aggregator.py
  - backend/intraday/service.py
  - backend/intraday/session.py
  - docs/superpowers/specs/2026-07-14-historical-context-trading-day-blind-box-design.md
  - docs/superpowers/plans/2026-07-14-historical-context-blind-box.md
quality_profiles:
  - phase2
---

## Goal
Implement a read-only chart-window service that aggregates explicit date windows and enforces current_time as the hard future boundary during active training.

## Acceptance Criteria
- [ ] Supports 30m, 4h_session, daily, and weekly.
- [ ] Active windows cap range_end at current_time.
- [ ] Completed read-only windows may extend after training_end.
- [ ] Response contains serialized K lines, volume, window_start/end, has_earlier/later, and read_only.
- [ ] has_later is false during active training.
- [ ] Future OHLCV extremes never leak into active results.
- [ ] Window boundaries are deterministic and JSON serializable.
- [ ] Input data is not mutated.
- [ ] Focused tests pass without network access.

## Constraints
Modify only the two write-scope files. Do not modify __init__.py, Flask, frontend, existing tests, task files, dependencies, or Git state. Do not commit.
