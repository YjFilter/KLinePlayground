---
id: TASK-012
title: Integrate intraday replay Flask API
status: done
priority: P0
owner: workbuddy-012
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
- [x] Start accepts explicit `data_mode` and all four period values.
- [x] Requests without `data_mode` preserve legacy daily behavior.
- [x] Intraday start loads normalized data through `IntradayDataService`, chooses the first actual timestamp on/after start date, and stores one `IntradayReplaySession`.
- [x] Intraday start response includes the complete session snapshot and data mode.
- [x] New period route switches without advancing and returns a snapshot.
- [x] Intraday next route advances by active-period boundary and returns ordered events.
- [x] Intraday data route returns the current snapshot without mutating replay state.
- [x] Manual trade uses the current base close and saves full time/display period.
- [x] Account, pending-order, reset, and end routes remain usable for intraday sessions or return explicit compatible payloads.
- [x] Legacy API regression tests continue to pass.
- [x] Tests mock network/data services and never call BaoStock live.

## Constraints
Modify only app and the new test file. Do not modify intraday modules, simulator, order manager, frontend, existing tests, quality gates, agent files, or Git state. Do not commit.

## Codex Acceptance
- API hotspot reviewed and corrected for explicit data-mode compatibility.
- Start-date lookup rejects requests with no real timestamp on or after the requested date.
- Manual trades always use current base close and prior-trading-day price limits.
- Replay price state preserves the actual base-bar id across start, advance, and reset.
- 65 focused API tests and the full 275-test suite passed.
