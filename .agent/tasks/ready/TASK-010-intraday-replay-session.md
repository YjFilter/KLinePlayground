---
id: TASK-010
title: Build intraday replay session controller
status: ready
priority: P0
owner: unassigned
depends_on:
  - TASK-005
  - TASK-009
write_scope:
  - backend/intraday/session.py
  - tests/test_intraday_session.py
read_scope:
  - backend/intraday/models.py
  - backend/intraday/aggregator.py
  - backend/intraday/replay_clock.py
  - backend/intraday/trading_context.py
  - backend/intraday/trading_engine.py
  - docs/superpowers/specs/2026-07-12-multi-timeframe-intraday-replay-design.md
quality_profiles:
  - phase4-focused
---

## Goal
Provide a Flask-independent `IntradayReplaySession` that owns one canonical replay clock, active display period, revealed aggregation, next-boundary state, and period-aware trading advancement.

## Required Public Contract
- Construct from normalized complete 30-minute bars, initial timestamp, stock code, simulator, and order manager.
- `snapshot()` returns current state and aggregated visible bars without advancing.
- `set_period(period)` switches period and returns a snapshot without changing current time.
- `advance()` plans and executes the next active-period boundary through `execute_trading_advance`, then returns state plus ordered events.
- `reset()` restores initial time and period without replacing account or order collaborators.

## Snapshot Fields
`current_time`, `active_period`, `base_interval`, `available_periods`, `current_bar_complete`, `next_boundary`, `kline_data`, `current_base_bar`, and `finished`.

## Acceptance Criteria
- [ ] Construction validates the initial timestamp and normalized timeline.
- [ ] Snapshot contains every required state field and revealed-only bars.
- [ ] Period switching preserves current time and account/order collaborators.
- [ ] Advance processes every hidden base bar and returns ordered events.
- [ ] Reset restores initial time and period.
- [ ] Focused offline tests pass.

## Constraints
No Flask imports. No network/cache access. Do not modify any existing production or test file. Do not implement legacy daily mode. Do not commit.
