---
id: TASK-009
title: Verify intraday trading step equivalence
status: done
priority: P0
owner: workbuddy-9
depends_on:
  - TASK-006
  - TASK-007
  - TASK-008
write_scope:
  - tests/test_intraday_trading_equivalence.py
read_scope:
  - backend/intraday/advance_executor.py
  - backend/intraday/trading_context.py
  - backend/intraday/trading_engine.py
  - backend/intraday/replay_clock.py
  - backend/order_manager.py
  - backend/trade_simulator_enhanced.py
quality_profiles:
  - phase3-focused
---

## Goal
Independently verify with real trading components that large-period advancement is behaviorally equivalent to repeated 30-minute advancement and preserves previous-close, T+1, metadata, event ordering, and account results.

## Acceptance Criteria
- [ ] Daily large-step and repeated 30m processing produce equal ordered events and trade history.
- [ ] Final capital, shares, position lots, and current price are equal.
- [ ] Same-day exit after a buy remains blocked by T+1.
- [ ] The next actual trading day's first eligible bar can sell.
- [ ] All bars in one day use the prior trading day's final close for limit checks.
- [ ] Trade records contain full timestamps and the selected display period.
- [ ] Tests use temporary databases and deterministic offline bars.

## Constraints
Black-box tests only. Do not modify production code, existing tests, quality gates, task files, or Git state. Report any defect with a minimal reproduction and stop rather than patching production.

## Codex Acceptance
- Independent black-box suite added 9 scenarios and passed.
- Large daily advancement matched repeated 30-minute advancement.
- Previous-close, price-limit, T+1, timestamp, display-period, event ordering, and account state semantics passed.
- No production defect was found.
