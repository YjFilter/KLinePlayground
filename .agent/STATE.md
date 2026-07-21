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

## Drawing Tools and Crypto Futures Complete
- Added TradingView-style Fibonacci retracement, ruler, long-position, and short-position drawing tools with selection, dragging, lock, visibility, delete, undo/redo, clear, and editable Fibonacci levels.
- Added Binance-first / Bybit-fallback USDT perpetual data with normalized instruments, dynamic search/top universe, monthly candle/funding caches, mark-price data, and offline restart support.
- Added 24x7 crypto replay from canonical 5-minute bars across 5m, 15m, 30m, 1h, 4h, daily, and weekly periods without future leakage.
- Added isolated-margin futures practice with long/short/close, market and limit orders, 1-20x leverage, funding, mark-price liquidation, reduce-only handling, reversal fills, pending-order cancellation, persistence, reports, and completed-history charts.
- Fixed real integration defects found during browser acceptance and review: the service bundle funding contract, unnecessary specified-symbol universe refresh, row-wise cache validation/aggregation/snapshot serialization, active-session runtime restoration, Bybit long-range funding pagination, and crypto price currency labels.
- Real data acceptance passed with Bybit BTCUSDT and ETHUSDT. Binance returned an IP restriction in this environment and the fallback remained functional.
- Performance acceptance: cached 30-day BTC bundle 3.64s, full training start 5.42s, next 5-minute bar 1.25s, period switches 0.09-0.49s, restarted 15-minute history chart 1.87s.
- Browser acceptance passed for all seven periods, market open/close, limit submit/cancel, next-bar advance, red/green long-short risk boxes, Fibonacci/ruler rendering, completed report, and history reconstruction after Flask restart; console errors 0.
- Runtime restart acceptance preserved the exact 5-minute replay time, long position, and pending limit order; restored account access completed in 3.88s.
- Bybit long-range funding acceptance returned 274 BTCUSDT funding events from January 1 through April 1, 2024 using time-based pagination.
- Verification passed: JavaScript syntax, Python compile checks, 116 focused crypto/drawing tests plus 24 subtests, and the full 511-test suite plus 37 subtests.

## Next Action
Use the drawing and crypto futures workflow normally. Keep .runtime/ untracked and excluded from commits.

## BTC and ETH Offline Cache Complete
- BTC and ETH shorthand inputs now normalize to BTCUSDT and ETHUSDT in both frontend and backend startup paths.
- Imported Binance official monthly 5-minute trade, mark-price, and funding archives for BTCUSDT and ETHUSDT from January 2024 through June 2026.
- Verified complete aligned offline coverage from January 2024 through May 2026: 29 months and 254,016 trade plus 254,016 mark bars per symbol.
- Monthly cache reads now open only the requested month files instead of repeatedly decompressing the entire archive; the reproduced 60-day offline bundle dropped from about 55 seconds per symbol to 7-10 seconds.
- Real /api/training/start acceptance normalized BTC/ETH correctly, selected the local Binance cache without REST access, and started both sessions in about 12-13 seconds.

## Next Action
Refresh the browser once to load the new JavaScript, then use BTC or ETH shorthand normally. Keep .runtime/ untracked and excluded from commits.
## AICoin-Style Crypto Replay and Drawing Refactor Complete (2026-07-16)
- Crypto training now uses an isolated dark two-column workspace: maximized chart area plus a fixed 320-340px replay/trading console. The original A-share three-column layout, left-side account information, and trade history remain intact.
- The crypto console includes playback, visible reset/end controls, account/position/order/history sections, large long/short/close direction selectors, collapsible volume/indicator panes, and chart fullscreen.
- Trend, rectangle, Fibonacci, ruler, long-position, and short-position tools now use pointer drag with live draft preview, requestAnimationFrame coalescing, 8px time/OHLC snapping, Alt bypass, and chart pan/zoom suspension during drawing.
- Long/short tools create Chinese risk/reward overlays in one drag with fixed 1.5:1 reward/risk, account equity, estimated position size, risk, entry, stop, and target labels. Anchors reproject to the nearest available bar when switching periods.
- Drawings remain in browser runtime during one training session, survive period switches, and are hard-reset with undo/redo history cleared on end, reset, new training, or exit.
- Crypto period switching now sends only one /period request, versions and aborts rapid requests, serializes backend mutations with a per-session lock, and rejects stale request IDs so SQLite restart state cannot be overwritten by an older response.
- Period snapshots reuse normalized/aggregated caches and return at most 300 bars centered on the current visible time range. Invalid old ranges fall back to fitContent; earlier/later history remains available through the explicit chart-window actions.
- Real BTC browser acceptance confirmed BTCUSDT title, 680px + 340px layout at the available desktop viewport, visible reset/end controls, long/short selection, seven periods, real panel collapse to display:none/0px, and a Chinese 1.5:1 long-position overlay.
- Performance acceptance on a fresh offline BTC session: cold period switches 154-273ms and cached switches 102-152ms; all requests remained local.
- Verification passed: JavaScript syntax, Python compileall, reviewer re-check with no remaining Critical/Important issues, 66 focused tests, and the full 540-test suite plus 37 subtests.

## Next Action
Use the crypto replay workspace normally at http://127.0.0.1:5000/. Keep .runtime/ and offline market data untracked and excluded from commits.

## Risk Box, Ruler, and Market Strip Refinement Complete (2026-07-16)
- Long/short risk overlays now use exactly three compact single-line labels for stop, summary, and target. Stop boundaries are red, target boundaries are green, and the entry summary boundary is dark teal.
- Risk labels use adaptive price precision, four-significant-digit position size, compact K/M account values, canvas clamping, and overlap avoidance.
- The ruler now uses a fixed TradingView-style teal region with dashed horizontal/vertical guides, an arrow, blue-gray anchors, and a four-line dark-teal information card.
- Ruler metrics include signed price change, percentage, bar and bullish/bearish counts, natural Chinese duration, and locally accumulated volume with K/M/B abbreviations.
- The ruler information card scales down when the canvas is extremely narrow so the full card remains visible instead of being clipped.
- Crypto OHLC, volume, and change percentage now occupy the chart-window toolbar; the duplicate right-side daily details and legacy A-share order section are hidden only in crypto mode.
- A-share daily details, IDs, and layout remain unchanged outside crypto training.
- Browser acceptance covered BTCUSDT and ETHUSDT ruler plus long/short risk overlays at the available 1280x720 viewport; this is narrower than the 1366px desktop acceptance floor and remained readable without toolbar overlap.
- Verification passed: JavaScript syntax, Python compileall, 38 focused tests, and the full 543-test suite plus 37 subtests.

## Current Next Action
Review and commit the six implementation/test files plus this state and handoff update when ready. Keep `.runtime/` and offline market data untracked. The active local server is `http://127.0.0.1:8000/` because port 5000 is unavailable on this host.

## Crypto Workspace Integration and Offline Search Complete (2026-07-16)
- Crypto desktop workspace acceptance now covers readable dark-theme text, a resizable/collapsible 340px trade console, a 32px collapsed trade-console tab, K-line-only focus mode, button pressed feedback, and successful long/close/short order submission.
- Rapid seven-period switching uses only the period endpoint, ignores stale responses, avoids account/chart-window refreshes, and does not show a full-screen loading overlay for fast switches.
- Local crypto instrument search now filters metadata paths by symbol before reading JSON, ranks by turnover, deduplicates symbols after sorting, and keeps the highest-turnover record.
- Cached instrument metadata paths are indexed in memory and invalidated whenever instrument metadata is saved. Crypto catalog dependencies are prewarmed during Flask startup without contacting Binance or Bybit.
- Real offline search performance on a fresh server process: BTC first search 564ms, ETH cached search 16ms, repeated BTC search 18ms. BTC/ETH results were unique and all requests stayed local.
- Accessibility regression tests now scope separator assertions to the two chart-panel splitters, preserving the separate keyboard-accessible trade-console splitter.
- Verification passed: 36 universe/API/cache tests, 94 crypto workspace/drawing/futures tests, JavaScript syntax checks, Python compileall, git diff check, and the full 592-test suite plus 37 subtests.
- Active local server: http://127.0.0.1:8000/ (PID 19636, bound to 0.0.0.0 for LAN access).

## Current Next Action
Review the full existing working-tree scope before creating any commit. Keep `.runtime/` and offline `data/` excluded; no commit has been created.

## Crypto Funding Cutoff and Editable Fees Complete (2026-07-17)
- Diagnosed the reported BTCUSDT session `yj_20260717_131521`: gross realized profit was 99.4823 USDT and trading fees were 49.8388 USDT, but the report also charged 208.0038 USDT and credited 4.9596 USDT of historical funding, producing the displayed -1.5340% return.
- Root cause: a newly created replay executor passed every funding event at or before the first advanced bar to the current position, including events before the replay start time.
- `FuturesReplayExecutor` now discards funding events at or before the replay starting timestamp. Funding is settled only for events occurring after the session begins.
- Added an editable Maker/Taker fee-rate card in the crypto trade console. Inputs use percentage units, default to Maker 0.02% and Taker 0.05%, and accept values from 0% through 1%.
- Fee rates can be changed only while flat with no pending orders, affect subsequent fills only, survive reset/runtime persistence, and are included in completed crypto reports.
- Live acceptance reproduced 2025-07-17 05:10–05:50 with custom Maker 0.01% / Taker 0.03%: realized PnL 9.9246 USDT, total fees 2.9832 USDT, funding paid/received 0, total return +0.0694%. Temporary acceptance history was deleted afterward.
- Verification passed: 81 focused tests plus 4 subtests, JavaScript syntax, Python compileall, git diff check, and the full 597-test suite plus 37 subtests.
- Active server: http://127.0.0.1:8000/ (PID 4380).
- The already-saved affected history record was not rewritten automatically; future sessions use the corrected logic.

## Future Whitespace Drawing Fix (2026-07-17)
- Drawing anchors can now be created, previewed, selected, anchor-dragged, and body-dragged in the blank logical area to the right of the last revealed candle.
- The controller derives a median bar interval from revealed bars and converts between future logical coordinates and timestamps without exposing future OHLCV data.
- Drawing primitives use the same projection path, so future anchors render correctly and continue to reproject after bar or period updates.
- Existing snap behavior remains unchanged near revealed candles; charts without logical-coordinate APIs retain the previous safe invalid-coordinate behavior.
- Verification passed: drawing runtime 30 tests, frontend integration 64 tests, JavaScript syntax, diff check, and full suite 599 passed plus 37 subtests.
- Active server: http://127.0.0.1:8000/ (PID 25164).

## Ruler and Risk Overlay UX (2026-07-18)
- The ruler now matches the compact reference layout: a three-line card above the measured region, a centered vertical guide, a horizontal guide, directional arrows, and two anchor handles.
- Ruler text is limited to price/percent change, candle counts, and elapsed time; volume was removed from the chart overlay. Positive ruler values no longer add redundant plus signs.
- Long/short risk overlays keep their red/green zones visible but hide all text by default. Hovering the risk area reveals three concise labels for stop, entry with price and RR, and target. Pointer leave hides them immediately.
- Account, position size, and unopened-PnL text were removed from the chart overlay to preserve candle visibility; those details remain available in the trading console.
- Verification passed: 31 drawing runtime tests, 101 frontend-focused tests, JavaScript/Python syntax, diff check, and full suite 600 passed plus 37 subtests.
- Active server: http://127.0.0.1:8000/ (PID 22376).


## Crypto Trigger Orders and Incremental Replay Complete (2026-07-19)
- Crypto order entry now uses one A-share-style segmented control: market, limit, and breakout, with a shared trigger-price field for limit/breakout orders.
- Both opening and closing orders support market, limit, and breakout execution. Limit fills use maker fees; breakout fills use taker fees; trigger orders cannot fill on their submission candle.
- Limit and breakout gap execution uses the next bar open when it is more favorable/required by the trigger rule, while preserving deterministic long/short and reduce-only behavior.
- Crypto next-bar replay now returns an incremental delta instead of rebuilding the full snapshot. The frontend updates candle/volume/account/orders/fills directly, ignores duplicate clicks, and no longer makes follow-up account/history requests.
- Replay-only persistence is coalesced into a short delayed checkpoint; trade, fee, reset, and completion actions still save immediately. Checkpoint writes are serialized.
- Backward compatibility is preserved for callers whose bar payload omits open; close is used as the fallback open.
- Verification passed: JavaScript syntax, Python compileall, focused crypto tests (110 passed and 10 subtests), and the full suite (621 passed and 47 subtests). Git diff check passed with only line-ending warnings.
- Flask route-level restart acceptance now proves that a missing in-memory session is restored from persisted runtime state before the first `/next` request, then continues with an incremental response.
- Real offline BTCUSDT and ETHUSDT acceptance covered market, limit, and breakout opening/closing. Twenty sequential `/next` requests measured roughly 3–7ms each after data load.
- Browser DOM acceptance at 1366x768 confirmed the segmented labels, unique ids, active/pressed feedback, and shared trigger-price visibility rules.
- Active server: http://127.0.0.1:8000/ and http://192.168.1.24:8000/ (PID 15680, bound to 0.0.0.0).
- No commit was created. Existing uncommitted changes were preserved; .runtime/ and offline data remain excluded.

## Next Action
Use BTCUSDT or ETHUSDT in the running app to visually confirm the integrated order panel and perceived next-bar speed. Before any commit, review the entire existing uncommitted diff and continue excluding .runtime/ and offline data.


## LAN Access Investigation (2026-07-19)
- Host-side Flask binding and health are correct on 0.0.0.0:8000 and 192.168.1.24.
- Two narrow inbound firewall rules now allow TCP 8000 from the local 192.168.1.0/24 subnet, including a Python program rule.
- The remote client still needs to provide Test-NetConnection, no-proxy curl, and IPv4 output to distinguish proxy from router/client isolation.
- Latest handoff: .agent/handoffs/2026-07-19-lan-access-investigation.md.

## Keyboard Fix and TP/SL Orders Complete (2026-07-19)
- Fixed global keyboard shortcuts intercepting number input in all crypto order panel fields (trigger price, margin, fee rate). The handler now skips all shortcuts when focus is on any input/select/textarea element.
- Added take-profit / stop-loss support to crypto futures opening orders, following Binance/Bybit conventions.
- Backend: `FuturesOrder` gained `tp_price`, `sl_price`, and `parent_order_id` fields. On opening fill, TP creates a reduce_only limit close order and SL creates a reduce_only breakout close order. OCO cancellation fires when either child fills. Same-bar conflict resolves SL-first (conservative). Manual close or position-flat cancels orphaned TP/SL orders.
- Backend: `/trade` endpoint accepts `tp_price` and `sl_price` with directional validation (long: tp > entry > sl; short: tp < entry < sl) and localized Chinese error messages.
- Frontend: TP/SL toggle checkbox with two price inputs and real-time estimated PnL display. Section hides for close orders. Fields reset after successful submit. Pending orders display labels TP/SL children distinctly with trigger prices.
- Verification passed: JavaScript syntax, Python compileall, 18 focused TP/SL tests, and the full 639-test suite plus 47 subtests.
- Active server: http://192.168.1.24:8000/ (PID 22340). Note: agent-orchestrator uvicorn (PID 12048) occupies 127.0.0.1:8000 and intercepts localhost requests.
- No commit was created. Existing uncommitted changes preserved; .runtime/ and offline data remain excluded.

## Next Action
Restart the Flask server to load the new code, then visually verify the TP/SL panel in a BTCUSDT session: toggle TP/SL, enter prices, confirm estimated PnL, submit with TP/SL, advance bars to trigger, and verify OCO cancellation and pending order display.

## Crypto Cancel and Limit Trigger Fix (2026-07-19)
- Fixed crypto cancellation races by serializing DELETE cancellation with the same per-training lock used by next-bar advancement.
- Successful cancellation now checkpoints immediately. Missing and inactive orders return structured `order_not_found` / `order_inactive` responses plus the authoritative pending-order list.
- The frontend refreshes account and pending orders before showing a cancellation failure, so stale cancel buttons disappear after an order fills or is already cancelled.
- Regression coverage proves daily snapshots never expose candles after `current_time` and a BTCUSDT short limit fills on the exact underlying five-minute candle whose high reaches the limit.
- Root cause of the reported no-fill screenshot was an old Flask process serving pre-fix backend code while the browser loaded newer static files. All stale project Flask processes were stopped.
- Verification passed: focused set 54 passed plus 10 subtests; order set 40 passed plus 10 subtests; full suite 642 passed plus 47 subtests; JavaScript syntax, Python compileall, and diff check passed.
- Active server: `http://127.0.0.1:8000/` and LAN binding `0.0.0.0:8000`, PID 24292.
- No commit was created. Existing uncommitted work is preserved; `.runtime/` and offline market data remain excluded.

## Next Action
Force-refresh the browser, then visually verify one far-away pending order can be cancelled and a BTCUSDT/ETHUSDT daily short limit fills only after a newly revealed underlying candle reaches its price.

## Binance-Style Crypto Orders Complete (2026-07-20)
- Rebuilt crypto futures order handling around explicit market, limit, and breakout semantics while preserving the existing one-way isolated-margin engine and A-share paths.
- Limit and breakout directions are validated against the current traded price, the submission candle cannot fill the order, and fills use the configured order price for deterministic replay.
- Opening orders can attach mark-price-triggered TP/SL protection. Stop-loss wins same-bar conflicts and OCO cancels the sibling order after one protection order fills.
- Pending orders support parameter copy and authoritative cancellation; each opening direction allows at most one active limit/breakout order.
- Frontend now shows quantity, fee, minimum quantity/notional, computed price, direction-aware price shortcuts, clear error codes/messages, pending-order state, and trade history.
- Final review found and fixed three browser blockers: an undefined pending-order renderer variable, crypto progress calling `toFixed()` on a missing field, and incremental next-bar responses not refreshing replay time/status.
- Browser acceptance passed on BTCUSDT and ETHUSDT: market open/close, TP/SL creation and OCO cleanup, valid/invalid limit direction, next-candle limit fill, parameter copy, breakout submit/cancel, and pending/trade refresh.
- Observed next-bar UI latency after the fixes: ETH daily partial-to-close 348ms and cached incremental day advance 414ms, with no new console errors.
- Verification: `657 passed, 61 subtests passed`; JavaScript syntax, Python compileall, and `git diff --check` passed.
- Active server: `http://127.0.0.1:8000/` and `http://192.168.1.24:8000/`, PID 17568, bound to `0.0.0.0`.
- No commit was created. Existing uncommitted work remains intact; `.runtime/` and offline market data were not edited, deleted, staged, or included.

## Next Action
Use the running BTC/ETH replay normally and review the full working-tree scope before any commit. Keep `.runtime/` and offline data excluded.

## Vercel Deployment Complete (2026-07-21)
- Production project: `yjfilters-projects/kline-playground`; alias: `https://kline-playground-seven.vercel.app`.
- Flask runs as a Vercel Python Service. `.runtime/` and local `users/` are excluded from deployment uploads.
- Neon resource `neon-claret-mirror` stores compressed user archives. Only the real `yj` archive remains.
- Production and Preview require HTTP Basic Auth. Credentials are outside the repository at `D:\Personal\Temp\kline-vercel-credentials.txt`.
- Health acceptance: cloud enabled, cloud ready, one restored user, and no cloud error.
- Real smoke acceptance created a temporary user, started BTCUSDT, advanced one candle, persisted state, deleted the user, and confirmed cloud deletion.
- Verification: 675 tests and 66 subtests passed; JavaScript syntax, Python compileall, and diff check passed.
- Mainland DNS currently resolves `*.vercel.app` incorrectly. Stable direct access needs a custom domain or VPN.
- No commit was created and existing uncommitted work remains intact.

## Next Action
Open the deployment with the saved credentials. If direct access fails, attach a user-owned custom domain in Vercel.

## GitHub Private Upload (2026-07-21)
- Private repository: `YjFilter/KLinePlayground`.
- GitHub remote: `github`; existing Gitee remote remains `origin`.
- Upload excludes runtime state, credentials, local users, Vercel binding metadata, and offline market data.
- See `.agent/handoffs/2026-07-21-github-private-upload.md` for the concise publication record.

## Next Action
Use GitHub as the private backup and collaboration source; keep local runtime and credential files untracked.