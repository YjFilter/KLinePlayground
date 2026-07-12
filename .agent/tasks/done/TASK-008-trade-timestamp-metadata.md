---
id: TASK-008
title: Add trade timestamp and display-period metadata
status: done
priority: P0
owner: workbuddy-8
depends_on:
  - TASK-005
write_scope:
  - backend/trade_simulator_enhanced.py
  - tests/test_trade_timestamp_metadata.py
read_scope:
  - backend/history_manager.py
  - backend/app_enhanced.py
  - docs/superpowers/specs/2026-07-12-multi-timeframe-intraday-replay-design.md
quality_profiles:
  - phase3-focused
---

## Goal
Extend simulator trade records with full `trade_time` and `display_period` while preserving existing `trade_date`, T+1 date semantics, legacy callers, and independent same-day trade ordering.

## Acceptance Criteria
- [ ] `buy` and `sell` accept optional `trade_time` and `display_period` without breaking existing callers.
- [ ] Trade dictionaries and generated report details expose the two new fields.
- [ ] SQLite `trades` table gains columns through repeatable additive migration; no table rebuild or data deletion.
- [ ] Insert and update paths persist both fields.
- [ ] Two same-day trades at different times remain separate records and preserve order.
- [ ] T+1 continues to use `trade_date`, not `trade_time`.
- [ ] Legacy calls that pass only `trade_date` still work and receive safe defaults.
- [ ] Focused tests use a temporary database and pass.

## Constraints
Do not modify app, history manager, order manager, market rules, replay modules, frontend, existing tests, or quality gates. Do not change fees, accounting, T+1 behavior, or same-day merge behavior except where required to preserve distinct timestamped trades. Do not commit.

## Codex Acceptance
- Scope reviewed and accepted.
- Focused WorkBuddy tests and legacy trading regressions passed.
- Integrated through `backend/intraday/trading_engine.py` without modifying Flask or frontend behavior.
