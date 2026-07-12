---
id: TASK-006
title: Build previous trading day close index
status: ready
priority: P0
owner: unassigned
depends_on:
  - TASK-005
write_scope:
  - backend/intraday/trading_context.py
  - tests/test_intraday_trading_context.py
read_scope:
  - backend/intraday/models.py
  - backend/market_rules.py
  - docs/superpowers/specs/2026-07-12-multi-timeframe-intraday-replay-design.md
quality_profiles:
  - phase3-focused
---

## Goal
Provide a pure previous-trading-day close lookup for normalized 30-minute bars so every bar in one trading day uses the same prior effective session close.

## Acceptance Criteria
- [ ] Build an immutable lookup from normalized 30-minute data.
- [ ] Every intraday bar on a date returns the previous data-bearing trading date's final close.
- [ ] The first trading date returns `None`.
- [ ] Weekends, holidays, suspensions, and non-consecutive dates use actual data order.
- [ ] Input is not mutated.
- [ ] Duplicate or unsorted timestamps fail clearly rather than silently selecting a close.
- [ ] Focused tests pass.

## Constraints
Do not modify market rules, replay clock, aggregator, simulator, order manager, Flask, frontend, existing tests, or quality gates. Do not commit.
