---
id: TASK-012
title: Integrate intraday replay Flask API
status: ready
priority: P0
owner: unassigned
depends_on:
  - TASK-010
write_scope:
  - backend/app_enhanced.py
  - tests/test_intraday_api.py
read_scope:
  - backend/intraday/session.py
  - backend/intraday/service.py
  - backend/intraday/cache.py
  - backend/intraday/baostock_source.py
  - backend/trade_simulator_enhanced.py
  - backend/order_manager.py
  - docs/superpowers/specs/2026-07-12-multi-timeframe-intraday-replay-design.md
quality_profiles:
  - phase4-focused
---

## Goal
Add an `intraday_30m` branch to the existing Flask training API while preserving the default `legacy_daily` branch and all existing response behavior.

## Acceptance Criteria
- [ ] Start accepts explicit `data_mode` and all four period values.
- [ ] Requests without `data_mode` preserve legacy daily behavior.
- [ ] Intraday start loads normalized data through `IntradayDataService`, chooses the first actual timestamp on/after start date, and stores one `IntradayReplaySession`.
- [ ] Intraday start response includes the complete session snapshot and data mode.
- [ ] New period route switches without advancing and returns a snapshot.
- [ ] Intraday next route advances by active-period boundary and returns ordered events.
- [ ] Intraday data route returns the current snapshot without mutating replay state.
- [ ] Manual trade uses the current base close and saves full time/display period.
- [ ] Account, pending-order, reset, and end routes remain usable for intraday sessions or return explicit compatible payloads.
- [ ] Legacy API regression tests continue to pass.
- [ ] Tests mock network/data services and never call BaoStock live.

## Constraints
Modify only app and the new test file. Do not modify intraday modules, simulator, order manager, frontend, existing tests, quality gates, agent files, or Git state. Do not commit.
