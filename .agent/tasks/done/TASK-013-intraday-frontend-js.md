---
id: TASK-013
title: Wire intraday replay frontend behavior
status: done
priority: P0
owner: workbuddy-013
depends_on:
  - TASK-011
  - TASK-012
write_scope:
  - frontend/js/main_enhanced.js
  - tests/test_intraday_frontend_static.py
read_scope:
  - frontend/index_enhanced.html
  - frontend/css/style_enhanced.css
  - backend/app_enhanced.py
  - backend/intraday/session.py
  - docs/superpowers/specs/2026-07-12-multi-timeframe-intraday-replay-design.md
quality_profiles:
  - frontend
---

## Goal
Connect the existing four-period controls to the accepted intraday Flask API while preserving the legacy JavaScript branch for sessions whose data_mode is not intraday_30m.

## Required Behavior
- Read the selected value from #kline-period instead of hard-coding daily.
- New training requests from the four-period selector explicitly send data_mode: intraday_30m and the selected period.
- Preserve a legacy branch whenever currentTraining.data_mode is not intraday_30m.
- Do not auto-advance immediately after starting an intraday session; render its returned snapshot at the initial real timestamp.
- For intraday sessions, period buttons POST /api/training/{id}/period with {period}; switching must not call /next.
- Support exact periods 30m, 4h_session, daily, weekly and readable badge labels.
- Render intraday start/data/period snapshots and next responses whose snapshot is nested under response.snapshot.
- Update #current-replay-time, #next-boundary-time, and #current-bar-status after every intraday snapshot.
- Toggle incomplete-candle and bar-status-incomplete/bar-status-complete classes from current_bar_complete.
- Continue/playback calls /next once per active-period unit and stops cleanly when finished.
- Intraday chart data comes from snapshot.kline_data; derive volume points from each candle's volume when needed.
- Avoid legacy-only indicator, chip-distribution, adjustment, full-data, or kline_processor-backed requests while in intraday mode unless the endpoint is explicitly compatible.
- Existing buy/sell/account/pending-order/reset/end flows must continue to work with intraday response shapes.
- Reset must render response.snapshot and restore its active period.

## Static Tests
Create focused Python static-contract tests that inspect main_enhanced.js without running a browser. At minimum verify:
- Start reads #kline-period and sends data_mode: intraday_30m.
- Intraday period switching uses the /period endpoint and does not use /next in that switching branch.
- All four exact period values are handled.
- Intraday snapshot status IDs and completion classes are referenced.
- Intraday next handles response.snapshot and finished.
- Intraday start does not auto-call nextBar.
- Legacy data-loading behavior remains present behind a non-intraday branch.

## Acceptance Criteria
- [x] Selected setup period starts an intraday_30m session.
- [x] Start renders initial snapshot without advancing.
- [x] Each period button switches without advancing.
- [x] Continue advances by the active period and renders the resulting snapshot.
- [x] Replay status and incomplete/complete visuals stay synchronized.
- [x] Playback, reset, trade, account, pending orders, and end remain usable.
- [x] Legacy JavaScript path remains available for legacy sessions.
- [x] JavaScript syntax check passes.
- [x] Focused static tests pass.

## Constraints
Modify only the two write-scope files. Do not modify HTML, CSS, backend, existing tests, dependencies, agent files, or Git state. Do not commit. Do not access live BaoStock or external networks.

## Codex Acceptance
- Frontend response-shape branches reviewed against the accepted Flask API.
- Random/box mode retains the legacy daily start path instead of sending an invalid intraday request.
- Intraday timestamps preserve market wall-clock labels without an eight-hour chart shift.
- JavaScript syntax check passed.
- 33 focused static frontend tests and the full 308-test suite passed.
