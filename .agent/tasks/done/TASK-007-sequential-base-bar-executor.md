---
id: TASK-007
title: Build sequential base-bar advance executor
status: done
priority: P0
owner: workbuddy-7
depends_on:
  - TASK-005
write_scope:
  - backend/intraday/advance_executor.py
  - tests/test_intraday_advance_executor.py
read_scope:
  - backend/intraday/models.py
  - backend/intraday/replay_clock.py
  - backend/order_manager.py
  - docs/superpowers/specs/2026-07-12-multi-timeframe-intraday-replay-design.md
quality_profiles:
  - phase3-focused
---

## Goal
Provide a framework-independent executor that consumes a ReplayAdvance plan and invokes callbacks once for every hidden base timestamp, in strict chronological order.

## Acceptance Criteria
- [ ] Execute exactly the plan's `base_bar_times` in order.
- [ ] For each timestamp call price/state update before pending-order processing.
- [ ] Collect and preserve all per-bar events in order.
- [ ] Commit the replay clock only after all base bars succeed.
- [ ] On callback failure, do not commit the replay clock and report the failed timestamp plus completed timestamps.
- [ ] Finished plans perform no work and fail clearly or return an explicit finished result.
- [ ] A daily/weekly large step and repeated 30m plans expose equivalent ordered base-bar processing.
- [ ] Focused tests pass.

## Constraints
Use dependency-injected callbacks. Do not import Flask or mutate simulator/order-manager production code. Do not modify replay_clock, models, app, simulator, frontend, existing tests, or quality gates. Do not commit.

## Codex Acceptance
- Scope reviewed and accepted.
- Focused WorkBuddy tests and legacy trading regressions passed.
- Integrated through `backend/intraday/trading_engine.py` without modifying Flask or frontend behavior.
