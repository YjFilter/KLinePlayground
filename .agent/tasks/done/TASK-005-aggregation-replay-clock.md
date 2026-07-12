---
id: TASK-005
title: Build aggregation and replay clock core
status: done
priority: P0
owner: codex
depends_on:
  - TASK-002
write_scope:
  - backend/intraday/models.py
  - backend/intraday/aggregator.py
  - backend/intraday/replay_clock.py
  - backend/intraday/__init__.py
  - tests/test_intraday_aggregator.py
  - tests/test_intraday_replay_clock.py
  - tests/test_intraday_no_future_leakage.py
  - scripts/quality_gate.py
  - tests/test_quality_gate.py
  - .agent/QUALITY_GATES.md
  - .agent/STATE.md
  - .agent/handoffs
  - docs/superpowers/plans/2026-07-13-aggregation-replay-clock.md
quality_profiles:
  - phase2
  - full
---

## Goal
Provide tested four-period aggregation and a period-aware replay clock over the canonical 30-minute timeline without modifying trading, API, frontend, reports, or persistence.

## Acceptance Criteria
- [x] `30m`, `4h_session`, `daily`, and `weekly` aggregation is supported.
- [x] Partial higher-period bars only use revealed 30-minute OHLCV.
- [x] Completion uses actual session and trading-week boundaries.
- [x] Period switching does not change current replay time.
- [x] Advance plans contain every real base timestamp in `(current_time, target_time]`.
- [x] Lunch, weekends, short weeks, incomplete sessions, and timeline end are tested.
- [x] Independent no-future-leakage tests pass.
- [x] Phase 2 and full quality profiles pass.

## Result
- Aggregator implementation and tests were delegated to an implementation Agent.
- Replay clock implementation and tests were delegated to a separate implementation Agent.
- Independent no-future-leakage black-box tests were delegated to a third Agent.
- Codex owned public contracts, integration, quality gates, review, and final acceptance.
