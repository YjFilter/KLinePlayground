# Current Project State

## Active Milestone
Phase 4 - API and frontend integration is complete; TASK-014 passed final no-patch browser acceptance.

## Completed Foundation
- Multi-agent collaboration control plane and quality profiles.
- BaoStock-backed five-year normalized 30-minute source, validation, cache, and synchronization.
- `ReplayPeriod` contracts for `30m`, `4h_session`, `daily`, and `weekly`.
- Revealed-only aggregation with partial-candle completion state and no future OHLCV leakage.
- Replay clock using actual base timestamps for lunch, weekends, holidays, suspensions, short weeks, and incomplete sessions.
- Pure advance plans containing each underlying 30-minute timestamp in `(current_time, target_time]`.

## Phase 2 Verification
- Aggregator tests: 8 passed.
- Replay-clock tests: 11 passed.
- Independent no-future-leakage tests: 6 passed.
- `python scripts/quality_gate.py phase2`: passed, 25 focused tests.
- Full quality profile passed after integration.

## Multi-Agent Outcome
- One Agent implemented and tested aggregation.
- One Agent implemented and tested the replay clock.
- One independent Agent wrote black-box future-leakage tests.
- Codex fixed public contracts, integrated outputs, extended quality gates, and performed final review.

## Scope Boundary
Phase 2 intentionally does not modify `KLineProcessorEnhanced`, Flask routes, trading execution, frontend, reports, or persistence. Those components will consume these stable boundaries in Phases 3 and 4.

## Known Limitation
BaoStock does not provide Beijing Exchange 30-minute data. A fallback source or import path remains required for prefixes `43`, `83`, `87`, and `92`.

## Phase 3 Completed
- Previous effective trading-day close lookup.
- Sequential hidden-base-bar execution with explicit replay-clock commit.
- Full trade timestamps and display-period metadata with additive SQLite migration.
- Critical trading adapter joining replay plans, prices, previous close, orders, and simulator.
- Independent daily-large-step versus repeated-30m equivalence verification.

## Phase 4 Completed
- `TASK-010`: intraday replay session controller accepted.
- `TASK-011`: four-period static HTML/CSS controls accepted.
- `TASK-012`: Flask API integration accepted; 65 focused API tests and the full 275-test suite passed.
- `TASK-013`: frontend JavaScript integration accepted; 33 focused static tests and the full 308-test suite passed.
- `TASK-014`: final no-patch browser/API acceptance passed with 9 Pass / 0 Fail / 0 Blocked.
- Fresh intraday session evidence: Console errors 0, HTTP 4xx 0, HTTP 5xx 0, `/next` max concurrency 1, stale replay plan 0, and no post-pause `/next` requests.
- The original TASK-014 FAIL evidence remains preserved; the latest report section records the passing retest after commit `33ab2a2`.

## Known Legacy Issue
- Legacy blind-box daily mode can log `加载技术指标失败: Value is undefined`; it is isolated from the intraday path and is non-blocking for Phase 4.

## Next Action
Select the next roadmap milestone or publish the completed Phase 4 commit series to the remote repository.

## Phase 5 Started
- Approved specification: historical context, trading-day limits, bidirectional completed-review loading, and intraday blind-box selection.
- TASK-015 completed the immutable distinct-trading-day replay cutoff contract.
- TASK-016 completed active/completed read-only chart windows for all four replay periods with a server-side no-future cap.
- TASK-017 completed bounded-retry intraday blind-box selection with BSE exclusion, two-year context checks, and injectable randomness.
- TASK-018 completed the static historical-window toolbar, one-year loading controls, and actual-trading-day setup wording.
- Codex reviewed the six worker-owned files, added stable package exports, and passed 307 intraday tests plus 13 subtests.
- Codex owns public exports, Flask hotspot integration, persistence contracts, quality gates, and final acceptance.

## Phase 5 Next Action
Flask and persistence integration is complete:
- Intraday specified starts request two years of prior context and apply distinct trading-day replay limits.
- Intraday blind-box starts select a real timestamp through the accepted bounded selector.
- Active chart windows cap at replay `current_time`; completed history charts rebuild without `active_trainings`.
- Completed reports persist full timestamp, period, data source, and trading-day metadata.
- Verification passed: 72 focused API tests, 80 API/trading-rule tests, phase3 quality gate, and 297 intraday tests.

Next, wire the accepted TASK-018 controls to the committed chart-window APIs in a JavaScript-only WorkBuddy task, then run Codex integration review and browser acceptance.

## Phase 5 Frontend Integration Complete
- TASK-019 wired `max_training_days`, four-period intraday blind-box startup, active chart windows, completed history windows, and one-year navigation.
- Codex integration review fixed legacy date-only report reconstruction, made the trading-day limit visible in both setup modes, stopped legacy polling in read-only history, preserved opposite pagination flags, isolated stale requests, and preserved same-timestamp trade markers.
- Automated verification passed: 54 frontend/static tests, 81 API/trading-rule tests, and 318 intraday tests.
- Browser evidence passed for an existing completed history record and a specified `600000` 30-minute session limited to 5 trading days; replay advanced from `2025-07-14 10:00:00` to `10:30:00` with no automatic advance.

## Phase 5 Next Action
Run final blind-box and restart browser acceptance, then close Phase 5 or fix any acceptance-only issue.

## Phase 5 Complete
- Final acceptance: 11 Pass / 0 Fail / 0 Blocked.
- Real blind-box `30m` startup with 150 trading days selected `600000` at `2024-05-27 10:00:00` and completed in 10.69 seconds after adding cache-first candidate selection.
- The replay frame contained exactly 150 trading dates and 1200 base bars with two full years of prior context.
- Four-period switching preserved replay time and a manual future-range attack was capped exactly at `current_time`.
- Completed history rebuilt after full Flask restarts without `active_trainings`, including a persisted buy marker and bidirectional one-year browser loading.
- Acceptance report: `docs/testing/historical-context-blind-box-browser-acceptance.md`.

## Next Action
Phase 5 is ready for normal use. The next milestone should expand the intraday cache pool beyond `600000` so blind-box stock selection has a larger local universe without depending on unstable public stock-list endpoints.

## Resizable Chart Workspace and Local Indicators Complete
- Main K-line, volume, and technical-indicator panels now share a resizable workspace with two mouse/touch/keyboard-accessible horizontal splitters.
- Panel proportions persist in browser local storage and Lightweight Charts resize continuously through drag and container changes.
- MACD, KDJ, RSI, and BOLL now calculate locally from the currently rendered/revealed K-line window, so intraday sessions no longer depend on or skip the legacy indicator endpoint.
- Browser acceptance passed at a 1900x1000 desktop viewport: main chart 441->401 px, volume 114->154->184 px, indicator 156->126 px; all four indicators produced non-empty canvases; 30m->daily switching preserved time and next advanced to the daily close; console errors 0.
- Automated verification passed: JavaScript syntax checks, 61 focused frontend/history tests, and the full 368-test suite.

## Next Action
Use the repaired chart workspace normally. `.runtime/` remains intentionally untracked and must not be committed.


## Compact Training Layout and Immediate Daily Trade Markers Complete
- Active training now applies a compact toolbar/header/status layout: desktop toolbar 42px, stock header 48px, history toolbar 30px, and replay status 27px.
- New panel defaults prioritize the K-line view; volume and indicator panes can shrink to 32px and 52px. Browser drag acceptance expanded the main chart from 584px to 714px.
- Intraday trade responses now return the complete marker list immediately. Frontend state preserves markers across snapshots, aligns timestamps to the current rendered period, and reuses one Lightweight Charts marker layer.
- Browser acceptance on daily view passed without any period switch: buy markers appeared at 2025-07-14 10:00 and 15:00, then a sell marker appeared at 2025-07-15 15:00. Marker layer contained B, B, S and console errors were 0.
- Automated verification passed: 132 focused tests and the full 373-test suite.

## Next Action
Review the repaired layout in normal use. Source changes remain uncommitted; .runtime/ remains intentionally untracked.
