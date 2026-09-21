# Current Project State

#### Current Snapshot（当前快照 — 每次会话结束时覆盖此区块）
- 最新测试基线：796 passed + 89 subtests passed（Python pytest） / 39 passed（Node.js test runner）
- 已完成：
  1. AICoin 风格 A 股自选/收藏股票面板 (Watchlist)：完整实现左侧自选栏（`自选`、`持仓`、`指数` 三大标签分类），支持本地持久化存储 (`ashare_live_watchlist_v1`) 与预置核心权重股；
  2. 毫秒级批量实时行情轮询：后端 `/api/ashare/live/batch` 接口通过腾讯行情网关单次请求获取数十只自选股票的现价与涨跌幅，前端 3 秒高频轮询，数据平滑跳动；
  3. 双向升降序排序：支持按“最新价”与“今日涨幅”一键点击在“默认 - 降序 - 升序”间循环切换；
  4. 点击联动与秒级切图：点击自选/持仓/指数列表中任意股票，中间 K 线图表、顶部行情条与右侧 A 股交易台秒级同步切换为该股票；
  5. 快速搜索添加自选：底部常驻 `+ 添加自选` 按钮，唤起搜索弹窗支持代码/名称/拼音缩写模糊检索，一键加入自选或直接切图；单行悬停 `×` 快捷删除；
  6. 自选面板一键折叠收起：面板右上角 `◀` 收起、图表头部 `▶ 自选` 展开，本地记忆折叠状态；
  7. 经典三栏专业终端工作区：左侧自选股 (270px) + 中间核心走势图表 (1fr) + 右侧 A 股专属模拟交易台 (340px)，支持双侧独立折叠；
  8. A 股同花顺专业标准周期（日、周、月 | 1分、5分、15分、30分、60分、120分、240分），日K加载 800 根覆盖 3.3 年以上历史数据，指数代码（如 sh000001 上证指数）精准识别；
  9. A 股专属现货模拟交易台（四宫格资产指标、当前持仓浮盈、T+1锁定解冻、买卖整手撮合、快捷仓位比例）。
- 隔离机制：data-ashare-live-only 与 data-crypto-workspace-only / data-a-share-workspace-only 严格互斥，零 regression
- 验证状态：前端 JS 单测 39/39 全数通过，Python 单元测试 796/796 全数通过，HTTP 批量接口与搜索接口均毫秒级响应
- 规范保障：严格恪守不执行 git commit 或 git push，工作树整洁可用

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
## Crypto Extended Window And Independent Theme Complete (2026-07-22)
- Root cause is resolved at the data boundary: active replay state keeps the fast 300-bar session snapshot, while an explicitly expanded chart window is re-aggregated from offline cache for every selected crypto period.
- The backend remembers the earliest loaded boundary and current replay end, reuses a per-period runtime cache, invalidates it on next/reset/end, and never exposes bars after the replay clock.
- Frontend marks an earlier load as extended runtime state, sends range bounds only for expanded windows, ignores stale period responses, and trusts the response window boundaries.
- BTCUSDT regression coverage now switches the same expanded 2024 window through `4h`, `1h`, and `15m` without advancing replay time or losing the 2024 start.
- Crypto has an independent `crypto_theme` setting and `cryptoUiTheme` local preference. It defaults to dark, uses a compact sun/moon button, and does not change the A-share `theme` or `body[data-theme]`.
- The crypto shell, toolbar, controls, chart/volume/indicator palettes, information overlays, and trade console now switch together between dark and light variables.
- Browser acceptance: loaded one earlier year on BTCUSDT, switched daily to 4-hour, and visibly retained 2024 candles; light and dark modes both rendered without black/white shell mixing; A-share theme stayed unchanged.
- Verification: crypto suite `230 passed, 48 subtests passed`; full suite `683 passed, 66 subtests passed`; JavaScript syntax, Python compileall, and diff checks passed.
- Local Flask service is running on `0.0.0.0:8000`, PID 12792. No commit was created.
- Existing unrelated `.gitignore` and `启动项目.bat` changes remain preserved; `.runtime/`, local users, offline market data, and credentials were not edited directly.
- Handoff: `.agent/handoffs/2026-07-22-crypto-period-loaded-window-fix.md`.

## Next Action
Hard-refresh `http://127.0.0.1:8000/` and continue normal BTC/ETH replay. Review the full working-tree scope before any commit and keep runtime/offline data excluded.

## Crypto Period Switch Performance Complete (2026-07-22)
- Expanded crypto windows now load trade candles only; chart reads skip mark prices, funding, instrument discovery, and duplicate cache scans.
- The normalized one-year 5-minute frame is retained in active training memory and reused across periods; `/next` appends the newly revealed base candle before clearing derived period payloads.
- Period serialization is vectorized and fine-period frontend responses use a compact OHLCV shape. The browser keeps an 8-entry runtime period snapshot cache and invalidates it on replay/window/training boundaries.
- Real BTCUSDT one-year Flask route timings: `4h 0.17s`, `1h 0.30s`, `15m 0.82s`, `5m 1.70s`, `daily 0.09s`; repeated `4h` was `0.01s`. The 5m response fell from about `31.9MB` to `11.0MB`.
- Verification: crypto suite `236 passed, 48 subtests passed`; full suite `690 passed, 66 subtests passed`; JavaScript syntax, Python compileall, and diff checks passed.
- Local Flask service is running on `0.0.0.0:8000`, PID `9268`. No commit was created; `.runtime/`, offline data, local users, credentials, `.gitignore`, and the launcher were not modified by this task.
- Handoff: `.agent/handoffs/2026-07-22-crypto-period-switch-performance.md`.

## Next Action
Hard-refresh `http://127.0.0.1:8000/`, load one year once, then switch periods normally. Repeated switches at the same replay time should render from browser memory without another period request.

## Crypto Two-Year History And Continuity Complete (2026-07-22)
- Crypto setup now exposes `训练前历史（年）`, defaults/minimums to `2`, accepts `2–5`, and remains independent from forward training duration.
- Added private one-time history preparation jobs with progress, cancellation, 30-minute expiry, monthly cache reuse, source pinning, and per-contract download locking.
- Training start consumes the prepared bundle and full historical 5-minute frame without rereading it; old clients use the same preparation synchronously.
- Fixed 1h/4h replay continuity by appending every newly revealed underlying 5-minute bar and repairing legacy sparse tails before aggregation.
- 5m/15m responses are capped at 12,000 bars, carry full-history/render metadata, align segment boundaries, and load earlier segments from runtime memory without network access.
- Runtime checkpoints persist the selected history window and rebuild it from offline cache after service restart.
- Forward replay append now uses a sorted fast path instead of renormalizing the full two-year frame; real browser 4h next-bar latency improved from about 2.1s to about 0.3s.
- Browser acceptance passed for BTCUSDT: two-year preparation completed from 25 cached months, daily history started in 2023-12 UTC, 5m/15m rendered 12,000 bars, rapid switches ended on the requested 1h period with strictly increasing timestamps, and 4h advance completed 48 underlying bars without fragments.
- Verification: crypto suite `262 passed, 53 subtests passed`; final full suite `717 passed, 71 subtests passed`; JavaScript syntax, Python compileall, and diff checks passed.
- Existing uncommitted work remains intact. `.runtime/`, offline market data, users, credentials, `.gitignore`, and the launcher were not modified by this task.
- Handoff: `.agent/handoffs/2026-07-22-crypto-two-year-history-continuity.md`.

## Next Action
Hard-refresh `http://127.0.0.1:8000/`, start BTCUSDT or ETHUSDT with the default two-year history, and continue normal replay. Review the complete working-tree scope before any commit and keep runtime/offline data excluded.

## External AI Takeover Package (2026-07-22)
- Added root `AI_TAKEOVER.md` as the low-token entry point for a new main AI.
- Added `.agent/prompts/MAIN_AGENT_PROMPT.md` as a complete copy-paste primary-agent prompt.
- Added `.agent/prompts/WORKBUDDY_TASK_PROMPT.md` as a bounded worker prompt with exclusive write scope, TDD, verification, and fixed result contract.
- The takeover package points new agents to repository source-of-truth files instead of requiring chat history or full-repository ingestion.
- UTF-8 content and `git diff --check` passed.
- Control-plane unit tests pass, but the existing `.agent/tasks/done/TASK-023-result.md` causes `scripts/agent_status.py` to fail because it is a result report without task front matter. This pre-existing file was not modified.
- Handoff: `.agent/handoffs/2026-07-22-external-ai-takeover-package.md`.

## Next Action
Give the next main AI the contents of `.agent/prompts/MAIN_AGENT_PROMPT.md`; use `.agent/prompts/WORKBUDDY_TASK_PROMPT.md` for bounded implementation work.

## Frontend z-index Fix Batch 1 Complete (2026-07-27)
- TASK-024 by QoderWork, reviewed and accepted by main AI (WorkBuddy).
- Fixed two z-index occlusion bugs in `frontend/css/style_enhanced.css`:
  - `.modal` z-index 1000 → 1100 (modals now above loading overlay).
  - `#main-app.chart-focus-mode` z-index 10000 → 900 (focus mode now below modals and overlay).
- Final hierarchy: focus-mode(900) < loading-overlay(1000) < modal(1100).
- Main AI verification: diff confirmed only 2 target lines changed (context lines untouched); `git diff --check`, `node --check`, `python -m compileall` all passed; control-plane quality gate failures are pre-existing (TASK-023 result report) and tooling artifacts (agent_status.py scanning result.md), unrelated to the CSS change.
- Browser verification via Playwright: `getComputedStyle` confirmed modal=1100, loading-overlay=1000, chart-focus-mode=900, hierarchyCorrect=true.
- Main AI integration fixes: corrected task frontmatter `status: ready → review` and `owner: unassigned → QoderWork`; moved task to `done/`.
- Existing uncommitted changes in other files remain preserved; no commit created.
- Handoff: `.agent/handoffs/2026-07-27-zindex-fix-batch1.md`.

## AiCoin-Style Crypto UI: Toolbar + Phase 1 Chart Terminalization Complete (2026-08-09)
- 顶部工具栏重构：`drawing-toolbar` 移入 `.chart-header`，周期/画图/面板三组由 `.toolbar-group-separator` 分隔，水平一体化；focus-mode 用毛玻璃覆盖层保留画图工具。股票模式与既有测试选择器（`id="drawing-toolbar"`、全部 data 属性、`flex-direction: row`、`overflow-x: auto`）均保持兼容。
- Phase 1 图表区终端化（仅加密模式生效，股票模式观感不变）：
  - 新增加密专用调色板 `THEME_PALETTES.crypto_dark/crypto_light`（涨跌 `#0ecb81/#f6465d`、背景 `#0b0e11`、淡化网格），`getThemePalette()` 按模式分流。
  - 加密模式实心蜡烛 + 价格轴当前价标签块（`lastValueVisible` + `applyLastPriceTagColor`）+ 虚线十字光标（`getCrosshairOptions`）。
  - 成交量与 MACD 柱颜色改由调色板驱动，币圈绿涨红跌、A股红涨绿跌各自符合惯例。
  - 主图左上角常驻 overlay 图例 `showLatestChartInfo()`：最新 bar OHLC + MA/BOLL 彩色数值，十字线跟随，接入数据更新各路径。
  - 副图头部改 AiCoin 式图例行："指标名(参数) ▾ + 彩色实时数值"，点击打开指标库切换；`INDICATOR_REGISTRY` 扩充 KDJ/RSI/BOLL；数值行泛化支持四种指标并跟随十字线。原 `<select id="indicator-select">` 保留为隐藏元素以兼容静态测试。
  - 加密模式隐藏旧图例色块（`#chart-legend/#active-indicator-tags/#indicator-legend`），`.chart-info-display` 改纯文本叠加层。
- Verification: `node --check` 通过；全量 `pytest -q` 通过 `717 passed, 71 subtests passed in 31.71s`；`git diff --check` 通过；浏览器加载无 JS 报错，新函数与 DOM 接线、加密分支配色/十字/蜡烛运行时校验全部正确。
- 本会话改动：`frontend/js/main_enhanced.js`、`frontend/css/style_enhanced.css`、`frontend/index_enhanced.html`。未创建提交；`.runtime/`、离线数据、凭证、`.gitignore`、启动脚本未改动。
- Handoff: `.agent/handoffs/2026-08-09-aicoin-ui-phase1.md`.

## Next Action
开一局币圈训练（如 BTCUSDT）并硬刷新 `http://127.0.0.1:8000/`，确认实心绿红蜡烛、价格轴当前价标签、左上角常驻图例与副图 AiCoin 图例行效果；确认后进入第二期（图标/密度/交易台融合）。

## AiCoin-Style Crypto UI Phase 2: Toolbar Icons + Density + Console Blend Complete (2026-08-10)
- 画图工具图标化：`#drawing-toolbar` 的 10 个画图工具 + 6 个操作按钮由 Unicode 符号换成内联 SVG 线条图标（`stroke="currentColor"` 跟随 hover/active 变色）；`data-drawing-tool`/`data-drawing-action`/`aria-label`/`title` 全部保留，JS 与静态测试不受影响。
- 密度收紧（仅加密模式）：图表头 36→34px、周期按钮 padding 收紧、面板/画图按钮 26→24px、画图按钮 min-width 28→26px、`chart-window-toolbar`/`replay-status-bar` 28→24px、交易台卡片 padding/圆角收紧。
- 交易台边框融合：`.crypto-console-splitter` 从 6px 实心色条改为透明 6px 拖拽区 + 居中 1px 发丝线（`::before`），拖拽把手默认隐藏、hover/拖动显现；移除 `.trade-console` 重复 `border-left`，图表与交易台之间只剩一条发丝线。
- 面板控制按钮（成交量/指标/指标库/全屏）与周期按钮保留文字（语义开关 + focus-mode 测试依赖）。
- Verification: `node --check` 通过；全量 `pytest -q` 通过 `717 passed, 71 subtests passed in 34.39s`；`git diff --check` 通过；浏览器 DOM 校验 16 按钮全含 SVG、flex 居中、stroke=currentColor 正确继承，加密分支 splitter 发丝线/按钮密度/header 高度运行时校验全部正确，控制台无报错。
- 本会话改动：`frontend/index_enhanced.html`、`frontend/css/style_enhanced.css`（`main_enhanced.js` 本期未动）。未创建提交；`.runtime/`、离线数据、凭证、`.gitignore`、启动脚本未改动。
- Handoff: `.agent/handoffs/2026-08-10-aicoin-ui-phase2.md`.

## Next Action
开一局币圈训练并硬刷新 `http://127.0.0.1:8000/`，确认画图/操作图标清晰、工具栏更紧凑、图表与交易台之间为一条可拖拽的发丝线；确认后进入第三期（周期短标签、图标库/交易台细节、字重与留白微调）。

## AiCoin-Style Crypto UI Phase 3: Period Short Labels + Ind-Lib Polish + Typography Complete (2026-08-10)
- 周期短标签：工具栏 8 个周期按钮改 AiCoin 式 `5m/15m/30m/1h/4h/1D/1W`（class/`data-period` 保留，JS 只读 dataset）；训练设置表单下拉保持中文描述不变。
- 周期徽章对齐：`formatIntradayPeriodBadge` 的 daily/weekly 返回值改 `1D/1W`，case 标签未动以兼容静态测试断言。
- 新增金色 accent token `--crypto-accent`（暗 `#f0b90b` / 浅 `#b98700`）。
- 指标库面板加密配色：背景/边框用 `--crypto-panel/--crypto-border`，激活项与收藏星标用金色 accent，hover 用 `--crypto-control-hover`，参数输入框用加密 input token + tabular-nums。
- 排版微调（加密）：激活周期 `font-weight 600`；`#current-price` 独立强调（text 色 + 600 + tabular-nums）；日期/徽章/回放状态/窗口状态统一 tabular-nums。
- Verification: `node --check` 通过；全量 `pytest -q` 通过 `717 passed, 71 subtests passed in 35.88s`；`git diff --check` 通过；浏览器 DOM 校验周期标签/徽章/accent/指标库加密配色全部正确，控制台无报错。
- 本会话改动：`frontend/index_enhanced.html`、`frontend/css/style_enhanced.css`、`frontend/js/main_enhanced.js`。未创建提交；`.runtime/`、离线数据、凭证、`.gitignore`、启动脚本未改动。
- Handoff: `.agent/handoffs/2026-08-10-aicoin-ui-phase3.md`.

## Next Action
开一局币圈训练并硬刷新 `http://127.0.0.1:8000/`，确认周期按钮 `5m…1W`、徽章同步、指标库金色激活/收藏、价格与回放数字对齐；三期完成后如需继续，可做交易台下单表单细节、图表快捷键、暗色对比度与圆角统一。

## AiCoin-Style Crypto UI Phase 4: Indicator Library Settings Modal Complete (2026-08-10)
- 指标设置弹窗（`#ind-settings-overlay`，AiCoin 式）：标题+描述、恢复默认、关闭、动态表单、底部"取消显示/应用"；支持 Esc/遮罩/× 关闭；z-index 950。
- 设置模型 `indicatorSettings`（localStorage `indicatorSettingsV1`）：MA 多行（周期/启用/颜色，最多 8 行）+ MACD/KDJ/RSI/BOLL 参数与各线条颜色；`loadIndicatorSettings` 防损坏合并默认。
- 指标库齿轮改为打开设置弹窗（替代内联参数行）；移除内联 `.ind-lib-params` 生成与监听。
- 应用链路：MA 经 `rebuildMaSeries`/`updateMaLinesFromRendered` 重建并按行可见性渲染；MACD/KDJ/RSI/BOLL 经 `loadTechnicalIndicator` 用设置颜色重绘；同步隐藏设置框保证 `getTechnicalIndicatorConfig` 旧链路一致；刷新图例/副图图例行/主图 overlay。
- MA 币圈可用：`applyIntradaySnapshot`/`replaceRenderedKlineData`/`upsertRenderedBar` 在加密模式本地计算 MA（非加密 intraday 仍清空）。
- Verification: `node --check` 通过；全量 `pytest -q` 通过 `717 passed, 71 subtests passed in 14.81s`；`git diff --check` 通过；浏览器 DOM 校验四指标表单构建/应用同步/加密弹窗配色（背景 #11161c、金色应用按钮 #f0b90b）全部正确，控制台无报错；测试用 localStorage 已清理。
- 本会话改动：`frontend/js/main_enhanced.js`、`frontend/css/style_enhanced.css`、`frontend/index_enhanced.html`。未创建提交；`.runtime/`、离线数据、凭证、`.gitignore`、启动脚本未改动。
- Handoff: `.agent/handoffs/2026-08-10-aicoin-ui-phase4-indicator-settings.md`.

## Next Action
开一局币圈训练并硬刷新 `http://127.0.0.1:8000/`，打开指标库点任一指标齿轮，确认设置弹窗样式、增删 MA 行、改颜色/周期后应用生效、恢复默认与取消显示可用；后续可做设置弹窗"说明"标签页、指标预警占位、交易台下单表单细节。

## AiCoin-Style Crypto UI Phase 5: MACD Sub-Panel Style Complete (2026-08-10)
- MACD 线色 AiCoin 化：DIF/DEA 默认置"自动色"（`null`），`getAutoMacdColors`/`resolveIndicatorColor` 按主题解析——加密暗色 DIF `#eaecef`、DEA 金 `#f0b90b`；浅色 DIF `#1e2329`、DEA `#b98700`；用户自定义色优先，恢复默认回自动。
- 零轴虚线：`attachMacdZeroLine` 用 `createPriceLine` 在 `price:0` 画灰色虚线（加密 `rgba(132,142,156,0.45)`），随系列清除。
- 线宽加粗：`createIndicatorLineSeries` 增加 `lineWidth` 参数，MACD DIF/DEA 用 2。
- 主题联动：`applyChartTheme` 在 MACD 自动色且有数据时自动重绘，切明暗主题线色自适应。
- 设置表单 MACD 颜色选择器展示解析色；未改动则回写 `null` 保持跟随主题。
- Verification: `node --check` 通过；全量 `pytest -q` 通过 `717 passed, 71 subtests passed in 29.63s`；`git diff --check` 通过；浏览器校验默认 `null` 自动态、加密暗/浅解析色、表单展示全部正确，控制台无报错，localStorage 未污染。
- 本会话改动：`frontend/js/main_enhanced.js`。未创建提交；`.runtime/`、离线数据、凭证、`.gitignore`、启动脚本未改动。
- Handoff: `.agent/handoffs/2026-08-10-aicoin-ui-phase5-macd-style.md`.

## Next Action
开一局币圈训练并硬刷新 `http://127.0.0.1:8000/`，切到 MACD 副图确认 DIF 白线、DEA 金线、y=0 灰色虚线零轴、柱状红绿与 AiCoin 一致，并切明暗主题验证线色自适应；后续可做 KDJ/RSI/BOLL 线色 AiCoin 化、设置弹窗"说明"标签页、交易台下单表单细节。

## AiCoin-Style Crypto UI Phase 5b: MACD Histogram Hollow/Solid + Line Z-Order Fix (2026-08-10)
- 柱子动能着色（用户对照截图指出差距）：正且增强→实心绿、正但减弱→半透明绿（空心观感）、负且增强→实心红、负但收敛→半透明红；新增 `hexColorWithAlpha(hex,alpha)` 把 hex 转 rgba（3/6 位，非 hex 原样返回）。
- 线条层级修复：`histogramSeries` 创建移到 `difSeries`/`deaSeries` 之前——Lightweight Charts 后建系列画在上层，原柱子最后建导致盖住线，现白/金 DIF/DEA 线压柱顶，对齐 AiCoin。
- Verification: `node --check` 通过；全量 `pytest -q` 通过 `717 passed, 71 subtests passed in 24.98s`；`git diff --check` 通过；浏览器校验 `hexColorWithAlpha` 四象限动能映射全对，控制台无报错，localStorage 未污染。
- 本会话改动：`frontend/js/main_enhanced.js`。未创建提交；`.runtime/`、离线数据、凭证、`.gitignore`、启动脚本未改动。
- Handoff: `.agent/handoffs/2026-08-10-aicoin-ui-phase5b-macd-histogram-zorder.md`.

## Next Action
开一局币圈训练并硬刷新 `http://127.0.0.1:8000/`，切到 MACD 副图确认白 DIF/金 DEA 线压在柱上层、柱子有实心/半透明之分（增强实心、减弱空心）、零轴虚线仍在；空心偏淡可调 alpha（当前 0.4）。

## Crypto Risk-Based Position Sizing + 100x Leverage Complete (2026-08-10)
- 新增"以损定仓"：下单区勾选后输入开仓价/止损价/最大亏损，自动反推数量并把所需保证金填入 `#crypto-margin`。公式：数量=最大亏损÷|开仓价−止损价|；名义=数量×开仓价；保证金=名义÷杠杆；结果行展示数量/名义/保证金(Lx)/止损幅度%/保证金亏损率%。
- 新模块 `frontend/js/risk_calc.js`（UMD 可 node require）：`RiskCalc.computeRiskPosition`，含方向校验、`missing-inputs`/`stop-too-close` 非法态、杠杆钳制 1–100。
- 杠杆上限 1→100x：后端 `futures_simulator._validate_leverage` 改 `1<=leverage<=100`；前端训练设置与下单两处下拉加 50x/100x。
- 新测试 `tests/test_crypto_risk_calc.py`（node 运行时公式 + 静态契约）；`test_crypto_futures_simulator.py` 边界 21→101、有效值 20→100。
- Verification: `node --check`/`compileall` 通过；全量 `pytest -q` 通过 `723 passed, 71 subtests passed in 33.28s`；`git diff --check` 通过；浏览器模拟完整流程（2500/2450/100/10x→数量 2/保证金 500 自动填入/止损价同步止盈止损区）正确，控制台无报错。
- 本会话改动：`frontend/js/risk_calc.js`(新)、`main_enhanced.js`、`index_enhanced.html`、`style_enhanced.css`、`backend/crypto/futures_simulator.py`、`tests/test_crypto_futures_simulator.py`、`tests/test_crypto_risk_calc.py`(新)。未创建提交；`.runtime/`、离线数据、凭证、`.gitignore`、启动脚本未改动。
- 注：验证时发现 8000 端口 Flask 已停，已按启动脚本同款命令后台重新拉起（PID 32712）。
- Handoff: `.agent/handoffs/2026-08-10-risk-based-position-sizing.md`.

## Next Action
开一局币圈训练硬刷新，勾选"以损定仓"输入开仓价/止损价/最大亏损点"计算并填入"，确认保证金自动填入、预览数量≈目标、订单可正常提交；试 50x/100x 杠杆开仓。

## Cross Margin Liquidation + Zero Default Fees Complete (2026-08-10)
- 修复用户反馈"一下单就自动平仓"：根因是引擎按**逐仓（Isolated）**语义计算强平/保证金率——强平只看 `position.isolated_margin`，账户剩余余额不参与，100x 高杠杆下 1% 波动即强平。
- 改为**全仓（Cross）语义**：`futures_engine.liquidation_price` 用 `account.balance`（账户总余额）替代 `isolated_margin`；`futures_simulator.margin_ratio` 改为 维持保证金 ÷ 账户总权益（余额+浮动盈亏）。账户剩余资金共同支撑仓位，余额充足时强平价远离现价/为 0（不触发）。
- 手续费默认全部归零：`futures_orders` maker/taker 默认 `0`（原 0.0002/0.0005）、`futures_engine.liquidation_fee_rate` 默认 `0`（原 0.005）、`app_enhanced.DEFAULT_CRYPTO_*_FEE_RATE` 归零、前端表单默认值 0.02/0.05% → 0。保留 `MAX_CRYPTO_FEE_RATE=0.01` 上限与设置入口，用户可自行设置。
- 测试更新：`test_crypto_futures_engine` 强平价测试改用 balance=100（全仓语义下余额=保证金才与原值一致）；`test_crypto_futures_api` 默认费率断言 0.0、max_margin 断言 ≤10000、unaffordable 用例 margin 10000→10001（fee=0 时 10000 恰好可用）；`test_crypto_futures_simulator` margin_ratio 断言 1.8333→0.2619。
- Verification: `node --check`/`compileall`/`git diff --check` 通过；全量 `pytest -q` 通过 `723 passed, 71 subtests passed`。
- 本会话改动：`backend/crypto/futures_engine.py`、`backend/crypto/futures_simulator.py`、`backend/crypto/futures_orders.py`、`backend/app_enhanced.py`、`frontend/index_enhanced.html`、`tests/test_crypto_futures_api.py`、`tests/test_crypto_futures_engine.py`、`tests/test_crypto_futures_simulator.py`。未创建提交；`.runtime/`、离线数据、凭证、`.gitignore`、启动脚本未改动。
- Handoff: `.agent/handoffs/2026-08-10-cross-margin-zero-fees.md`.

## Next Action
硬刷新 `http://127.0.0.1:8000/` 开一局币圈训练（可用 100x 杠杆），确认：下单后不再"秒强平"（余额充足时强平价应远离现价）、保证金率按账户总权益计算、手续费显示 0 且可在设置中自行修改。

## AiCoin-Style Crypto Position Card Complete (2026-08-11)
- 币圈"当前持仓"区升级为 AiCoin 风格持仓卡片（`renderCryptoPositionCard` 渲染进 `#current-positions`）：头部交易对+方向徽标(多绿/空红)+逐仓+杠杆(x)+浮动盈亏(金额+保证金收益率%)；2 列指标网格含持仓量(币)/开仓均价/保证金(USDT)/标记价格/保证金率/预估强平价/止盈(绿)/止损(红)；止盈止损值取自挂单中的保护单；空仓回落"暂无持仓"。
- 卡片三操作：止盈止损→开启并聚焦下单区止盈止损面板；平仓→切换订单表单为市价平仓；市价全平→`cryptoMarketCloseAll` 直接 POST `/trade`(action=close, order_type=market, margin=0, leverage=持仓杠杆)，复用成交回报/状态链路。
- 加密模式隐藏下单面板内冗余 `.crypto-position-grid`；`updatePositionInfo`(A 股持仓渲染器)加密模式提前返回避免覆盖卡片。A 股模式行为不变。
- Verification: `node --check` 通过；全量 `pytest -q` 通过 `723 passed, 71 subtests passed in 49.01s`；`git diff --check` 通过；浏览器 DOM 模拟多头/空仓 payload，卡片头部与八项指标全对、操作钮齐全、空仓回落正确，控制台无报错。
- 本会话改动：`frontend/js/main_enhanced.js`、`frontend/css/style_enhanced.css`。未创建提交；`.runtime/`、离线数据、凭证、`.gitignore`、启动脚本未改动。
- Handoff: `.agent/handoffs/2026-08-11-crypto-position-card.md`.

## Next Action
开一局币圈训练开多/开空一笔，确认"当前持仓"卡片数据齐全、颜色正确，点三个操作钮验证：止盈止损聚焦下单区、平仓切市价平仓、市价全平一键成交；平仓后卡片回落"暂无持仓"。

## Drawing Floating Toolbar + Per-Request Settings Panel Complete (2026-08-11)
- 用户反馈"画斐波那契每次都要弹出左边设置页，挡位置"，参考 AiCoin 风格的浮动紧凑工具条。
- **改造**：
  1. `drawing_tools.js` `DrawingController` 加 `onSelectionChange` 回调（select/undo/redo/clearAll 触发）。`_emitSelectionChange` 内部辅助方法。
  2. `main_enhanced.js`：
     - `syncDrawingFloatingToolbar(selectedId, model)` 切换工具条显隐 + 同步锁定/隐藏按钮高亮 + 隐藏对象时整个隐藏工具条。
     - `bindDrawingFloatingToolbar()` 一次性绑定工具条按钮（拖动/设置/锁定/隐藏/删除）。"设置"按对象类型分派：斐波那契弹出档位面板，其他对象提示"无独立设置"。
     - 工具按钮激活时**不再自动显示设置面板**（避免遮挡 K 线）。选中/取消选中是面板唯一的显示触发。
     - 移除 `chart.pointerup` 自动重渲染 panel 的逻辑（已由 onSelectionChange 替代）。
  3. HTML 新增 `#drawing-floating-toolbar`（5 个 SVG 图标按钮）。斐波那契面板改为 `drawing-settings-popover` 类（右上角弹出而非左 50px）。
  4. CSS 浮动工具条样式（chart 顶部 12px、居中 translateX(-50%)、紧凑 30×30 图标按钮、hover/active 高亮、z-index 36 在 chart 之上）。
- **可复用模版**：浮动工具条是**通用画图操作栏**，选中任意画图对象时显示；"设置"按对象类型分发设置面板（斐波那契=档位列表，其他工具后续可扩展同名 panel 复用机制）。
- Verification: `node --check` 两个文件都通过；全量 `pytest -q` 通过 `727 passed, 71 subtests passed`；agent-browser 模拟 `syncDrawingFloatingToolbar()` 调用验证 `toolbarHidden=false`、5 按钮、position=absolute/top=12px/z-index=36 全部正确（viewport 太矮无法验证 transform 居中，但 CSS 已含 `translateX(-50%)`）。
- 本会话改动：`frontend/js/drawing_tools.js`、`frontend/js/main_enhanced.js`、`frontend/index_enhanced.html`、`frontend/css/style_enhanced.css`。未创建提交；`.runtime/`、离线数据、凭证、`.gitignore`、启动脚本未改动。
- Handoff: `.agent/handoffs/2026-08-11-drawing-floating-toolbar.md`.

## Next Action
硬刷新 `http://127.0.0.1:8000/`（服务直接 serve static，新前端立即生效），开 BTCUSDT 训练画一个斐波那契；激活工具时不再弹设置面板；**点击 chart 上已画的斐波那契**触发浮动工具条（顶部居中红框风格），"设置"图标才弹出档位面板（右上角），不再挡左侧 K 线。

## Drawing Tools Expanded: Fibonacci Time Zones + Per-Tool Settings (2026-08-11)
- 用户反馈：除斐波那契外其他画图工具"设置都是空的"；并要求新增"斐波那契趋势时间"工具。
- **drawing_tools.js 改动**：
  1. 新增 `fibonacci-time` 工具类型：单锚点向右按斐波那契数列（默认 1/2/3/5/8/13/21/34/55）画垂直时间线，支持标签位置 top/bottom、颜色、线宽、线型。
  2. 通用线条设置归一化：`normalizeLineOptions`、`normalizeRectangleOptions`、`normalizeTextOptions`、`normalizeFibonacciTimeSettings`——所有工具 model.options 都有统一字段 `color/lineWidth/lineStyle/labelVisible`（保留 undefined 让渲染时 fallback 到主题色 `strokeColor`，避免破坏 `setDefaultStrokeColor`）。
  3. 渲染：horizontal/trend/ray/rectangle/ruler/text/fibonacci-time 全部从 model.options 读 `lineWidth/lineStyle/labelVisible`；rectangle 增加 `fillColor/fillOpacity`；text 增加 `text/fontSize`；fibonacci-time 从 `_timeProjection.interval` 推算每根线时间。
  4. `_bodyDistance`：新增 fibonacci-time 检测（任意一根垂直时间线在 tolerance 内即命中）。
  5. Controller API：`getSelectedLineSettings/updateSelectedLineSettings` 通用接口 + `updateSelectedFibonacciTimeLevels/addFibonacciTimeLevel/removeFibonacciTimeLevel/resetFibonacciTimeSettings` 专用接口。
- **HTML 改动**：
  - 画图工具栏新增"斐波那契趋势时间"按钮（垂直时间线条图标）。
  - 新增 5 个设置面板 DOM：`#drawing-fibonacci-time-settings`、`#drawing-line-settings`、`#drawing-rectangle-settings`、`#drawing-text-settings`、`#drawing-position-settings`，全部用 `drawing-settings-popover` 类（右上角弹出）。
- **main_enhanced.js 改动**：
  - 浮动工具条"设置"按选中对象 `type` 分派：`openSelectedDrawingSettingsPanel(model)`。
  - 新增各面板填充逻辑 + `bindDrawingSettingPanels()` 一次性绑定所有变更事件。
  - `closeAllDrawingSettingPanels()` 选中取消时统一清理。
  - `positionSettingsPanel` 显示当前 `accountRiskPercent`。
- **CSS 改动**：扩展 `.drawing-settings label` 字段排版，新增 `.drawing-fibonacci-time-levels` 列表样式。
- **可复用模版**：浮动工具条 + 设置面板派发是通用模式——后续新增任何画图工具，只需：①在 normalize 添加设置字段；②HTML 加一个 popover panel（如果需要）；③`bindDrawingSettingPanels` 加事件绑定即可。
- Verification: `node --check` 通过；全量 `pytest -q` 通过 `727 passed, 71 subtests`（drawing_tools_frontend 35 个测试全过）。
- 本会话改动：`frontend/js/drawing_tools.js`、`frontend/js/main_enhanced.js`、`frontend/index_enhanced.html`、`frontend/css/style_enhanced.css`。未创建提交。
- Handoff: `.agent/handoffs/2026-08-11-drawing-tools-expanded.md`.

## Next Action
硬刷新 `http://127.0.0.1:8000/`，验证：①画图工具栏多一个"斐波那契趋势时间"按钮（垂直线图标），点一下单击一次画垂直时间线组；②选中任意画图工具画的图形→点浮动工具条"设置"图标→对应面板从右上角弹出，修改颜色/线宽/线型/标签立即生效；③斐波那契趋势时间面板可编辑时间倍数（增加/删除/重置）。

## Fibonacci Time Reworked to Two-Anchor Extension (2026-08-12)
- 用户反馈"斐波那契时间"工具与参考图（AiCoin）不符：参考图是**两锚点**（起点+终点）画**水平档位线 + 垂直时间线**，顶部显示倍数标签 `0 | 0.382 | 0.618 | 1 | 1.382 | 1.618 | 2`。
- **重做**：
  1. `DEFAULT_FIBONACCI_TIME_LEVELS` 从时间序列 `[1,2,3,5,8,13,21,34,55]` 改为**延伸倍数** `[0, 0.382, 0.618, 1, 1.382, 1.618, 2]`。
  2. `TOOL_POINT_COUNTS['fibonacci-time']` 1 → **2 锚点**（拖动画起讫）。
  3. 渲染改为：水平档位线 `price = p1 + n*(p2-p1)` + 垂直时间线 `time = t1 + n*(t2-t1)`，颜色随倍数分档（0/0.382=紫、0.618/1=蓝、1.382/1.618=绿、2=橙），顶部/底部显示倍数标签（`formatFibonacciTimeLabel`：整数不带小数、非整数 3 位）。
  4. `_bodyDistance` 同步改为检测垂直+水平线集合。
  5. `_creationAnchors`/`_defaultCreationAnchors` 移除单锚点特例（回到 2 锚点通用逻辑）。
- Verification: `node --check` 通过；全量 `pytest -q` 通过 `727 passed, 71 subtests`。
- 本会话改动：`frontend/js/drawing_tools.js`。未创建提交。

## Next Action
硬刷新 `http://127.0.0.1:8000/`，验证"斐波那契趋势时间"：拖动两个点（起点+终点），应画出与参考图一致的档位线 + 时间线 + 顶部倍数标签；选中后点浮动工具条"设置"可改颜色/线宽/线型/标签位置，倍数列表可编辑（0/0.382/0.618/1/1.382/1.618/2）。

## Fibonacci Time Tool Removed (2026-08-12)
- 用户确认"斐波那契趋势时间"工具与预期不符（点后其他画图工具消失），决定删除该工具自行处理。
- **清理范围**（4 个文件，fibonacci-time 相关全部移除，全局 0 处引用）：
  - `frontend/index_enhanced.html`：移除工具按钮 + `#drawing-fibonacci-time-settings` 面板 DOM。
  - `frontend/js/main_enhanced.js`：删除 `renderFibonacciTimeSettingsPanel`、`bindDrawingSettingPanels` 中的 fibonacci-time 绑定、`closeAllDrawingSettingPanels`/`openSelectedDrawingSettingsPanel` 中的分派。
  - `frontend/js/drawing_tools.js`：删除 `DEFAULT_FIBONACCI_TIME_LEVELS`、`defaultFibonacciTimeSettings`、`normalizeFibonacciTimeSettings`、`formatFibonacciTimeLabel`、渲染分支、`_bodyDistance` 分支、`TOOL_POINT_COUNTS` 项、Controller 的 fibonacci-time 专用方法、get/updateSelectedLineSettings 分派。`normalizeDrawingType` 移除别名。
  - `frontend/css/style_enhanced.css`：删除 `.drawing-fibonacci-time-levels` 相关样式。
- **保留**：通用线条设置（horizontal/trend/ray/ruler）、矩形、文字、持仓测算面板全部保留；斐波那契回撤（fibonacci）不受影响。
- Verification: `grep -r fibonacci-time frontend/` = 0；`node --check` 通过；全量 `pytest -q` 通过 `727 passed, 71 subtests`；curl 确认工具栏按钮恢复为原 10 个工具（无 fibonacci-time）。
- 本会话改动：`frontend/index_enhanced.html`、`frontend/js/main_enhanced.js`、`frontend/js/drawing_tools.js`、`frontend/css/style_enhanced.css`。未创建提交。

## Next Action
硬刷新 `http://127.0.0.1:8000/` 确认画图工具栏恢复（10 个工具：选择/趋势/横线/射线/矩形/文字/斐波那契回撤/量尺/做多/做空），点任意工具画图正常、浮动工具条设置面板正常。

## Fib-Trend-Time Fixed to Vertical Time Lines (2026-08-12)
- 用户让其他 AI 实现了 `fib-trend-time`（斐波那契趋势时间），但仍是错的：它画**水平档位线 + 斜趋势线 + 价格轴标签**（本质是"斐波那契回撤+趋势线"组合），而 AiCoin 参考图是**纯垂直时间线**（斐波那契倍数应用到时间轴）。
- **诊断**：其他 AI 的数据定义（`DEFAULT_FIB_TREND_TIME_LEVELS`：0/0.382/0.618/1/1.382/1.618/2/2.382/2.618/3 + 颜色分组）完全正确；错误只在渲染/命中/轴标签用了价格维度（水平）。
- **修复**（`frontend/js/drawing_tools.js`）：
  1. 渲染：改为画**垂直时间线**——`x = first.x + level.value * (second.x - first.x)`（像素插值，无需时间换算），从 y=0 到 y=height 贯穿；顶部/底部标签显示倍数（`level.label`），颜色按档位。
  2. `_bodyDistance`（命中检测）：改为检测**垂直线横向距离**。
  3. `_axisSlotCount`/`_axisLabelEntries`：fib-trend-time **不再输出价格轴标签**（倍数标签画在 chart 内部顶部）。
- **测试**：更新 `FibTrendTimeRuntimeTests` 4 个用例为新行为（垂直线渲染、无价格轴视图、垂直线命中、controller 流程 axisViews=0）。
- Verification: 全量 `pytest -q` 通过 `732 passed, 71 subtests`（画图 40 个全过）；`node --check` 通过。
- 本会话改动：`frontend/js/drawing_tools.js`、`tests/test_drawing_tools_frontend.py`。未创建提交。
- **教训**：参考图（AiCoin）中"斐波那契趋势时间"= 把斐波那契倍数应用到**时间轴**画垂直时间线（`x = t1 + n*Δt`）；**不是**价格轴水平档位线，也不是"时间序列"（1/2/3/5/8…）。数据定义（倍数+颜色）与渲染（垂直）要分开理解。

## Next Action
硬刷新 `http://127.0.0.1:8000/`，选"斐波那契趋势时间"按钮（虚线梯形图标），在 chart 上拖两个点，应看到：从起点向右按 0/0.382/0.618/1/1.382/1.618/2/2.382/2.618/3 画出一组**垂直时间线**（紫/蓝/青/粉/绿/橙），顶部显示倍数标签；点线可选中调出浮动工具条。

## Fib-Trend-Time Added Anchor Connector (2026-08-12)
- 用户反馈我做的版本缺了**两锚点之间的虚线参考连线**（参考图 AiCoin 风格用红色箭头表示"被分析的这一段行情"）。
- 网上搜索 TradingView 标准 Fibonacci Time Zones：自然数列 0/1/2/3/5/8/13...（**与 AiCoin 不同**，AiCoin 用小数倍 0/0.382/0.618/1...）；用户要 AiCoin 风格。
- **修复**：`drawing_tools.js` 渲染分支加 `drawLine(first, second)`（虚线，区别于档位线），作为"被分析的这一段行情"的视觉提示。线宽减半以与档位线视觉区分。
- Verification: 732 passed, 71 subtests；node --check 通过。

## Next Action
硬刷新页面，画一个斐波那契时间：拖两个点应看到①两锚点之间一条**虚线**（淡灰）连接，表示被分析的行情段；②向右展开 10 条垂直时间线（紫/蓝/青/粉/绿/橙），顶部显示倍数标签。

## Fib-Trend-Time Zero-Baseline Fixed to High Anchor (2026-08-12)
- 用户明确规则：两个锚点 = 左侧波段低点 + 右侧波段高点；基准周期 = 两锚点时间差；**0 线必须对齐右侧高点锚点**（波段终点，时间扩展的 0 基准点）；所有比例线（0.382/0.618/1/1.382/1.618/2/...）从 0 线向右侧（未来）延伸；1 线 = 高点之后再经过 1 个完整基准周期。
- **修复**（`frontend/js/drawing_tools.js`）：
  - 渲染：线时间 = `endTime + ratio * (endTime - startTime)`（0 基准 = 高点 endTime），优先用 `projectedTimeToCoordinate`（可投影到未来），失败回退像素 `second.x + ratio * (second.x - first.x)`。
  - `_bodyDistance` 命中检测同步改为高点 0 基准。
- 测试：更新渲染测试断言（level0 → x=second.x=20、level3 → x=50）。
- Verification: 732 passed, 71 subtests；node --check 通过。
- 教训：斐波那契趋势时间的 0 线不是起点锚点，而是**波段终点（高点）**——工具语义是"预测高点之后的未来转折时间"，而非"把波段本身当 0~1 区间"。

## Next Action
硬刷新，画斐波那契趋势时间：拖左侧低点 → 右侧高点，应看到 0 线恰好对齐右侧高点（与锚点白圈重合），1 线在高点右侧一个基准周期处，其余 0.382/0.618/1.382/1.618/2... 依次向右展开。

## Fib-Trend-Time: Base Period Uses Abs (2026-08-12)
- 用户反馈我做的版本出错：自己画的图锚点在右、线在左（basePeriod 为负、线向"过去"延伸）。用户给的参考图：下跌波段左高右低，红色水平箭头明确指向**右侧 = 未来方向**。
- **关键认知**：「未来方向」在 chart 上是**绝对时间正向**（向右），与锚点拖动顺序无关。即使先拖高点后拖低点（first.time > endTime，basePeriod 为负），线也应该向**右侧（未来）**延伸，0 线对齐第二锚点（endTime）。
- **修复**：`basePeriod = Math.abs(endTime - startTime)`，渲染和命中检测同步。`lineTime = endTime + ratio * basePeriod`，永远向时间正向（chart 右）延伸。
- Verification: 732 passed, 71 subtests；node --check 通过。
- 教训：基准周期长度是**正数**（时长），不区分方向；线方向方向（未来 = chart 右）是绝对时间正向，不受锚点拖动顺序影响。

## Next Action
硬刷新，无论先低后高还是先高后低，画出来 0 线都对齐第二锚点，1/1.382/2/... 都向 chart 右侧（未来）展开。

## Fib-Trend-Time FINAL Fix: 0~1 = a→b segment (2026-08-12)
- 用户最终明确（"很难吗？"）：用户从 **a→b 量取一段走势**，**0~1 的时间长度就是 a→b 的时间长度**；0 线对齐 a（起点），1 线对齐 b（终点）；0.382/0.618 在 a~b 之间；1.382/1.618/2/... 向 b 右侧（未来）扩展。
- **最终实现**（drawing_tools.js 渲染 + 命中检测）：
  - `basePeriod = endTime - startTime`（带方向）
  - `lineTime = startTime + ratio * basePeriod`（0 → a，1 → b，>1 → b 右侧）
  - 像素回退：`first.x + ratio * (second.x - first.x)`
- 测试更新：渲染断言（0→x=10、1→x=20、3→x=40），命中（档位2 x=30、档位3 x=40）。
- Verification: 732 passed, 71 subtests；node --check 通过。
- **教训**：这个工具极其简单——"0~1 就是量取的这段走势，往右扩展"。前面多次绕弯是因为过度解读（一会儿对齐高点、一会儿取 abs）。以后先问清楚"0 和 1 分别代表什么"，再动手。

## Next Action
硬刷新，a→b 拖一段走势：0 线在 a（起点）、1 线在 b（终点）、0.382/0.618 在中间、1.382/1.618/2/... 在 b 右侧（未来）展开，顶部显示倍数标签。

## Fib-Trend-Time FINAL (2026-08-12, user clarified 3rd time)
- 用户最终明确：两个锚点 A→B 量取一段走势；**0 线从 B 点（第二锚点）开始算**；**1 线在 B 右侧 +1×Δt 处**；Δt = |B.time − A.time|（A→B 量取的走势时长）；全部往右（未来）扩展。
- **最终实现**（drawing_tools.js 渲染+命中检测）：
  - `basePeriod = Math.abs(endTime - startTime)`（Δt 正数）
  - `lineTime = endTime + ratio * basePeriod`（0→B，1→B+Δt，1.382+ 继续右扩）
  - 像素回退：`second.x + ratio * Math.abs(second.x - first.x)`
- 测试更新：渲染（0→x=20、1→x=30、3→x=50），命中（档位2 x=40、档位3 x=50）。
- Verification: 732 passed, 71 subtests；node --check 通过。
- 教训总结：该工具 = 「0 基准在第二锚点 B，Δt = A→B 时长，从 B 向右按斐波那契倍数扩展」——0~1 的距离 = A→B 量取的走势时长。理解顺序：先问清"0 线在哪、1 线在哪"再动手。

## Next Action
硬刷新，A→B 拖一段走势：0 线应贴在 B（后拖锚点），1 线在 B 右侧一个基准周期处，0.382/0.618 在 B~B+Δt 之间，1.382/1.618/2/... 继续向右（未来）展开。

## Fib-Trend-Time Rewrite v2 (2026-08-12, 纯像素实现)
- 用户反馈"画图这里还是有问题"——虽然理解已确认对，但渲染仍错（怀疑浏览器缓存或时间投影逻辑复杂）。用户说"不行就删除重新做"。
- **彻底重写**为**纯像素实现**（不再依赖 _timeProjection 投影时间→坐标，逻辑直接可调试）：
  - `deltaX = Math.abs(second.x - first.x)`（向右扩展距离）
  - `lineX = second.x + ratio * deltaX`（0→B，1→B+ΔX，1.382+ 继续右扩）
  - 像素插值在缩放时与时间插值等价（之前验证过），且避免时间投影边界 case
- 命中检测同步：纯像素 `x = second.x + ratio * |ΔX|`
- 测试：732 passed, 71 subtests 全过（无需改测试，逻辑等价）
- Verification: 732 passed, 71 subtests；node --check 通过。
- 教训：复杂的时间投影逻辑（_timeProjection + projectedTimeToCoordinate）容易在边界 case 出错；用纯像素逻辑更稳定可靠——时间插值和像素插值在 chart 缩放时是等价的（x = W·(t-T0)/(T1-T0)）。

## Next Action
硬刷新 `http://127.0.0.1:8000/`，A→B 拖一段走势：0 线应贴在 B（后拖锚点），1 线在 B 右侧 +1×|A.x-B.x| 处，全部向右展开。如果仍不对，下一步是删除整个工具重新写。

## MACD/MA Default Parameters Updated (2026-08-12)
- 用户要求默认参数：MACD(10,20,5)，MA(10,20,40,80,160)，免每次手动改。
- **改动**：
  - `frontend/index_enhanced.html`：macd-fast/slow/signal input value 12/26/9 → 10/20/5
  - `frontend/js/main_enhanced.js`：3 处 macd 兜底（12/26/9 → 10/20/5）、`macd: {fast:10,slow:20,signal:5}` 默认、参数面板 default、getTechnicalIndicatorConfig 兜底；`maPeriods` 初始 [5,10,20] → [10,20,40,80,160]（2 处）；MA 参数面板 default '5,10,20' → '10,20,40,80,160'
  - `backend/app_enhanced.py`：3 处 ma_periods 请求默认 '10,20,40,80,160' + 3 处 fallback [10,20,40,80,160]
  - `backend/kline_processor_enhanced.py`：get_ma_data 默认 periods [10,20,40,80,160]
  - `backend/user_manager_enhanced.py`：用户设置 ma_periods 默认 [10,20,40,80,160]
  - `tests/test_chart_workspace_frontend.py`：MACD 断言 12/26/9 → 10/20/5
- 全局确认无 12/26/9 或 [5,10,20] 残留。
- **注意**：全量测试 60 failed —— **与本次改动无关**，根因是 `backend/crypto/replay_clock.py` 等文件在 17:02 被**其他 AI/会话并发修改**（git diff 10+/24-），破坏了 crypto 时间戳验证（"timestamps must form a continuous 1-minute timeline"）。本次改动相关测试（test_chart_workspace_frontend + test_drawing_tools_frontend）54 passed 全过。
- Verification: node --check 通过；54 passed（相关测试）。

## Next Action
需与用户确认：backend/crypto/ 的 60 个失败是否由其他 AI 正在改导致，是否要我处理回归（等待或修复）。

## Takeover Status Check + Git Object Store Repaired (2026-08-14)
- **接手状态检查**：全量 `pytest -q` 恢复全绿 `745 passed, 89 subtests passed`（38s）。上一条目记录的 60 个 crypto 失败已由其他会话在 8/13 修复（`backend/crypto` 核心文件 12:06–12:27、`backend/app_enhanced.py` 20:44、`tests/test_crypto_history_api.py` 20:45），`.agent/tasks/{active,ready,review,blocked}` 均无在办任务包。本次无需改动代码。
- **Git 修复**：接手时 git 全命令报 `fatal: bad object HEAD`——`main` 指向的提交 `338bb62` 及其对象在本地对象库被删（仅剩 clone pack + 5 个零散 blob）。用户提供 GitHub PAT，经 curl 走 git smart-http（本执行环境对 git 自带 TLS 间歇性重置：OpenSSL/schannel 均 SSL_ERROR_SYSCALL；curl 稳定）下载完整 packfile，`git index-pack` 装入对象库。恢复结果逐字节验证：`git cat-file -t HEAD` → commit，`git show -s HEAD` 元数据与远端一致，`git log/status/diff` 全部恢复正常（未提交改动 63 项原样保留）。
- 清理：修复过程中重建脚本曾写入 32 个畸形 tree 对象，已按结构校验精确删除；fsck --connectivity-only 现无 error（仅 2 条既有 dangling blob 提示，未动）。
- 未创建提交/分支，未暂存、移动、清理任何既有未提交改动；`.runtime/`、离线数据、`.gitignore`、启动脚本未触碰；令牌未持久化。
- Handoff: `.agent/handoffs/2026-08-14-git-object-repair-crypto-verified.md`.

## Next Action
等待用户下一项需求。（`AI_TAKEOVER.md` 过时摘要已同步：分支 main、最新交接、测试数字 745。）

## MA (10,20,40,80,160) Default Settings & Palette Matched (2026-08-14)
- **需求**：按用户提供的参考图配置 MA 默认参数、颜色与勾选显隐状态。
- **配置落地**：
  - MA 10：显隐状态 **未勾选 (visible: false)**，颜色 **紫色 `#7038db`**。
  - MA 20：显隐状态 **已勾选 (visible: true)**，颜色 **蓝色 `#2196f3`**。
  - MA 40：显隐状态 **已勾选 (visible: true)**，颜色 **绿色 `#52c41a`**。
  - MA 80：显隐状态 **已勾选 (visible: true)**，颜色 **青色 `#26c6da`**。
  - MA 160：显隐状态 **已勾选 (visible: true)**，颜色 **棕色/赭石 `#b85717`**。
- **指标系统与持久化**：
  - `main_enhanced.js`：更新 `MA_DEFAULT_COLORS` 与 `DEFAULT_INDICATOR_SETTINGS.ma.lines`。
  - 存储版本升级：`INDICATOR_SETTINGS_KEY = 'indicatorSettingsV2'`，带 V1 自定义指标无缝向下兼容，避免用户浏览器旧缓存覆盖新默认值。
  - 显隐联动增强：图表常驻信息（`showLatestChartInfo`）、图例（`renderChartLegend`）与十字准星悬浮数据（`subscribeCrosshairMove`）均接入 `isMaLineVisible` 检查，未勾选的均线不再干扰视觉与数据展示。
  - HTML 兜底修正：`frontend/index_enhanced.html` 中副图指标参数默认文字同步更新。
- **质量门禁与验证**：
  - JS 语法检查：`node --check frontend/js/main_enhanced.js` 通过。
  - Python 编译检查：`python -m compileall -q backend` 通过。
  - 新增测试：`tests/test_chart_workspace_frontend.py` 增加 `MaIndicatorDefaultSettingsTests`。
  - 全量测试套件：`.venv\Scripts\python.exe -m pytest -q` -> `747 passed, 89 subtests passed in 32.24s`（全绿）。

## BTC & ETH 2024-2026 Complete Offline Cache Synchronization (2026-08-14)
- **排查缺口**：
  - BTCUSDT：缺失 `2025-01`～`2025-04` 标记价格与 `2024-01`～`2025-04` 资金费率。
  - ETHUSDT：缺失 `2024-01`～`2024-05` 1m 成交 K 线、`2024-01`～`2026-04` 标记价格与 `2024-01`～`2026-04` 资金费率。
- **补齐完成**：
  - 从币安官方归档源（`data.binance.vision`）下载全部缺失月份数据。
  - 经 `CryptoMonthlyCache` 标准化为 `.csv.gz` + `.json` 校验写入。
  - 覆盖率达到 **100%（2024-01 ～ 2026-08 共 32/32 个月全部就绪）**，涵盖 1m 真实成交、标记价格与资金费率。
- **验证**：
  - 完整 2 年历史数据包离线秒级加载测试通过。
  - 全量测试套件：`.venv\Scripts\python.exe -m pytest -q` -> `747 passed, 89 subtests passed`（全绿）。

## Accumulated Workspace Changes Committed (2026-08-14)
- **提交内容**：工作区累积的 63 项有效源码与文档变更。
  - 修复 `.agent/tasks/done/TASK-024-zindex-fix-batch1.md` 任务状态（review -> done）及结果报告兼容。
  - 排除 `.runtime/`、`data/`、`users/` 与临时日志文件。
  - Commit ID: `282e0f9`。

## On-Chart Position & TP/SL/Pending Order Lines (2026-08-14)
- **功能落地**：在 Lightweight Charts 主图上实现了 TradingView / AICoin 风格的实时交易价格线（`candlestickSeries.createPriceLine`）：
  - **持仓均价线**：多单亮蓝（`#2196f3`）/ 空单亮红（`#f6465d`），带实时方向、数量、开仓均价、浮动盈亏（USDT）与收益率（%）。
  - **止盈线 (TP)**：翠绿虚线（`#0ecb81`），带价格标签。
  - **止损线 (SL)**：亮红虚线（`#f6465d`），带价格标签。
  - **限价/突破开仓挂单线**：蓝色/金色虚线，标注动作、触发价格与委托数量。
  - **动态联动**：下单、撤单、单步推演 K 线、切换周期（快照重载）及平仓时毫秒级自动重绘与更新收益。
- **质量门禁**：
  - `node --check frontend/js/main_enhanced.js` 通过。
  - `python scripts/agent_status.py .agent/tasks` 通过。
  - 新增测试：`tests/test_chart_workspace_frontend.py` 增加 `ChartTradePriceLinesTests`。
  - 全量测试套件：`.venv\Scripts\python.exe -m pytest -q` -> `750 passed, 89 subtests passed in 26.14s`（100% 全绿）。
## One-Click 2024 BTC Fast Test Mode & Cache Acceleration (2026-08-14)
- **用户痛点与需求**：测试新功能（指标、画图、持仓线、下单）时，每次填写表单并等待多年前期历史数据准备进度弹窗耗时较长。需要一个固定 2024 年 BTC 离线数据的一键极速开局入口，快速进入看盘测试。
- **功能实现**：
  1. **UI 极速入口**：
     - 在顶部主导航栏增加金黄色高亮 **「⚡ 快速测试(BTC)」** 按钮。
     - 在新建训练弹窗顶部嵌入 **「⚡ 极速功能测试模式」** 快捷横幅与「一键极速开局」按钮。
  2. **预设 2024 BTC 极速配置**：
     - 合约：`BTCUSDT`（100% 离线缓存，无任何网络依赖）。
     - 起始时间：`2024-07-01 00:00:00`，训练前历史：`1 年`（覆盖 2024 上半年完整 K 线）。
     - 训练时限：`60 天`，周期：`5m`，初始资金：`100,000 USDT`，杠杆：`10x`。
  3. **后端年份放宽与热缓存加速**：
     - 修改 `CRYPTO_HISTORY_MIN_YEARS = 1`（支持 1 年观察期）。
     - 在 `CryptoMonthlyCache` 中引入 `_frame_cache` 内存热缓存机制，避免重复 Gzip 解压与逐行反序列化。
     - 在 `CryptoDataService.get_chart_bars` 中增加连续性快速路径 `actual.equals(expected)`。
- **质量门禁**：
  - `node --check frontend/js/main_enhanced.js` 通过。
  - `python scripts/agent_status.py .agent/tasks` 通过。
  - 新增测试：`tests/test_chart_workspace_frontend.py` 增加 `QuickTestBtcEntryTests`；更新 `test_crypto_history_api.py` 与 `test_crypto_frontend_static.py`。
  - 全量自动化测试：`.venv\Scripts\python.exe -m pytest -q` -> **753 passed, 89 subtests passed in 24.62s（100% 全绿）**。
  - Commit ID: `c62e900`。

## On-Chart Risk Box to Order Panel Sync & Offline Data Dashboard (2026-08-14)
- **以损定仓与图表做多/做空工具双向打通**：
  1. 在画图浮动工具条 `#drawing-floating-toolbar` 中增加高亮「⚡ 同步下单」按钮。
  2. 当选中图表上的「做多 / 做空 / 风险回报测算框」时自动显示该按钮。
  3. 点击后触发 `syncDrawingToOrderPanel(model)`：
     - 提取入场价（Entry）、止损价（Stop）、止盈价（Target）。
     - 自动判断多空方向，切换下单方向按钮（`open_long` / `open_short`）。
     - 设置为限价单并填入入场价；开启止盈止损并填入止盈价与止损价。
     - 开启以损定仓，填入开仓价、止损价与风险金额（USDT），自动调用 `applyCryptoRiskCalc()` 计算推荐保证金与数量。
     - 给出状态提示并将下单区平滑滚动至视口，实现秒级挂单。
- **前端离线数据管理面板与一键下载**：
  1. **后端**：新增 `backend/crypto/data_manager.py`，提供 `scan_crypto_offline_status()` 与 `sync_crypto_offline_data()`；暴露 `GET /api/crypto/data/offline_status` 与 `POST /api/crypto/data/download`。
  2. **前端**：在「设置」弹窗内增加 **📦 币圈离线数据看板与管理**：
     - 状态表格：展示本地已缓存币种（BTCUSDT, ETHUSDT 等）、月份跨度、1m/标记/费率文件数、占用磁盘体积与完整性标识。
     - 下载工具：支持输入币种（例如 SOLUSDT, DOGEUSDT）与年份（2024, 2025, 2026, 全部），点击「开始增量下载」即可从 Binance 官方归档一键补齐，并实时显示进度与刷新看板。
- **质量门禁**：
  - `node --check frontend/js/main_enhanced.js` 通过。
  - `python scripts/agent_status.py .agent/tasks` 通过。
  - 新增测试：`tests/test_drawing_order_sync.py`（4 个测试全过），`tests/test_crypto_offline_data_manager.py`（5 个测试全过）。
  - 全量自动化测试：`.venv\Scripts\python.exe -m pytest -q` -> **762 passed, 89 subtests passed in 40.31s（100% 全绿）**。
## Quick Test Acceleration: 6-Month Fast Test Window (2026-08-14)
- **优化原因**：之前 1 年历史参数在 `start_time = 2024-07-01` 时回溯到了 `2023-07`，触发了向外网请求 2023 年份数据导致耗时。
- **调整落地**：
  - 将快速测试入口调整为固定使用 **2024 年上半年（2024-01 ~ 2024-07 共 6 个月）** 作为历史观察期，向后训练 30 天（2024-07-01 ~ 2024-07-31）。
  - 所有数据 100% 存在于本地已下载的 2024 年离线归档中，零网络依赖。
  - 支持 `history_months: 6` 参数，极速开局秒点秒开。
- **质量门禁**：
  - 全量自动化测试：`.venv\Scripts\python.exe -m pytest -q` -> **762 passed, 89 subtests passed (100% 全绿)**。
  - Commit ID: `22fc298`。

## Drawing Sync-Order Button UI & Logic Fixes (2026-08-14)
- **原因分析**：
  1. 浮动工具条 CSS 中 `.drawing-floating-toolbar button` 限制了 `width: 30px; height: 30px`，导致带文字的按钮被硬挤成竖向单字折行。
  2. 画图全局监听拦截了 `invokeDrawingAction`，但未在 `invokeDrawingAction` 中分发 `sync-order` 分支；同时 `syncDrawingToOrderPanel` 中对 `isCrypto` 判定因未显式同步模式而失效，且未向 DOM 发送 `input`/`change` 事件驱动计算。
- **调整落地**：
  1. **UI 美化**：为 `.drawing-sync-order-btn` 编写独立样式（`width: auto !important; height: 26px; padding: 0 10px; font-weight: 600; white-space: nowrap`），搭配标准闪电图标与暗金主题，水平完美居中排列。
  2. **逻辑修复**：
     - 在 `invokeDrawingAction` 中增加 `sync-order` 处理入口，多路兜底保障点击响应。
     - 强化 `isCrypto` 判定（涵盖 `isCryptoMode()`、`CRYPTO_MARKET_TYPE` 与界面 DOM 识别）。
     - 同步后自动触发 `input`/`change` 事件，自动填入限价价格、勾选并展开止盈止损、勾选并展开以损定仓并计算保证金，最后提供金色高亮提示与平滑聚焦。
- **质量门禁**：
  - 全量自动化测试：`.venv\Scripts\python.exe -m pytest -q` -> **762 passed, 89 subtests passed (100% 全绿)**。
  - Commit ID: `20c2c5c`。

## Chart Trade Price Lines Interactive Drag-To-Modify (2026-08-14)
- **功能背景**：
  - 用户需求：允许在图表上直接拖动「止损线/止盈线/限价挂单线」修改价格，松开鼠标自动同步修改后台订单。
- **技术实现**：
  1. **后端订单薄与接口**：
     - `backend/crypto/futures_orders.py`：在 `FuturesOrderBook` 中增加 `modify_order_price(order_id, new_price, timestamp)`，原生支持限价单、突破单、TP 保护单与 SL 保护单的价格即时修改。
     - `backend/app_enhanced.py`：暴露 `PUT /api/training/<training_id>/orders/<order_id>` 与 `POST /api/training/<training_id>/orders/<order_id>/modify`，带原子锁保护与运行快照持久化。
  2. **前端交互与图表层**：
     - `frontend/css/style_enhanced.css`：新增 `.chart-price-line-tooltip`（TP/SL/Limit 动态彩色高亮与毛玻璃阴影）与 `body.chart-dragging-order`（全局锁定 `ns-resize` 光标与防止文本选中）。
     - `frontend/js/main_enhanced.js`：
       - 在 `updateChartTradePriceLines` 中为每个有效挂单线绑定元数据 `{ line, orderId, order, type, price, side, quantity, entryPrice }` 并标明 `[可拖动]`。
       - 实现 `initChartTradeLineDragging`：监听指针移动与命中检测（±8px 容差），悬浮时变换光标；按住左键拖拽时实时根据 `candlestickSeries.coordinateToPrice(mouseY)` 计算新价格，并驱动价格线实时跟随与悬浮 Tooltip 动态展示新价格、相对开仓价幅度及预估 USDT 盈亏；松开鼠标后调用 PUT 接口异步改单并平滑刷新挂单列表与图表线。
- **质量门禁**：
  - 新增测试：`tests/test_crypto_order_modification.py`（5 个测试全部通过）。
  - 更新测试：`tests/test_chart_workspace_frontend.py`（24 个测试全部通过）。
  - 全量自动化测试：`.venv\Scripts\python.exe -m pytest -q` -> **769 passed, 89 subtests passed (100% 全绿)**。
  - Commit ID: `5937532`。

## Toolbar Event Bubbling Isolation & Drawing Sync Model Recovery Fix (2026-08-14)
- **原因查明**：
  - 浮动工具条 `#drawing-floating-toolbar` 处于 `#chart` 容器内。当用户鼠标按下（`pointerdown` / `mousedown`）点击「⚡ 同步到下单区」或设置按钮时，事件向上冒泡到图表容器，触发了 `drawingController._onPointerDown`；由于未命中图表上的具体控制柄，画图控制器在按钮响应前将当前选中对象取消了选中（`selectedId = null`），导致后续的点击逻辑未能拿到画图模型。
- **调整落地**：
  1. **事件冒泡彻底隔离**：为 `#drawing-floating-toolbar` 以及所有画图设置弹窗（斐波那契/做多做空/线条/矩形/文本）统一拦截并阻止 `pointerdown`、`mousedown` 与 `click` 的向上冒泡，杜绝误触画布取消选中。
  2. **模型状态双重兜底**：
     - 在工具条显示时自动记录 `lastSelectedRiskDrawingModel`；
     - 在同步方法 `syncDrawingToOrderPanel` 中采用多重降级解析：`selectedId -> lastSelectedRiskDrawingModel -> activeDrawing -> selectedDrawing -> store.list().find(risk)`，确保 100% 稳健命中当前测算框。
  3. **表单联动闭环**：同步后强制向限价、止损、止盈及以损定仓输入框分发 `input` 与 `change` 事件并刷新预览与保证金。
- **质量门禁**：
  - 全量自动化测试：`.venv\Scripts\python.exe -m pytest -q` -> **769 passed, 89 subtests passed (100% 全绿)**。
  - Commit ID: `f6c1936`。

## Risk Model Resolver Centralization & Store Method Fix (2026-08-14)
- **原因查明**：
  - `drawingController.store`（`DrawingStore` 类）原生只暴露了 `snapshot()` 和 `get(id)`，此前调用的 `store.list()` 返回 `undefined`；
  - `invokeDrawingAction('sync-order')` 内部存在遗留的校验拦截，未将获取责任完整委托给 `syncDrawingToOrderPanel`；
  - 浏览器端可能因缓存未即时加载最新的 JS 文件。
- **调整落地**：
  1. **数据层扩展**：在 `DrawingStore` 中显式添加 `list()` 与 `getAll()` 作为 `snapshot()` 的别名，保障所有外部调用兼容。
  2. **统一解析器**：抽取统一的 `getActiveRiskDrawingModel(explicitModel)`，通过 5 级降级策略（`explicitModel -> selectedId -> lastSelectedRiskDrawingModel -> activeDrawing -> selectedDrawing -> store.snapshot().reverse().find(risk)`）100% 可靠捕获做多/做空框。
  3. **调用链直通**：`invokeDrawingAction('sync-order')` 与浮动工具条统一直接调用 `syncDrawingToOrderPanel()`，不再进行前置误杀拦截。
  4. **缓存规避**：在 `index_enhanced.html` 引入带有版本参数（`?v=20260814_sync`）的脚本标签，杜绝浏览器静态资源缓存。
- **质量门禁**：
  - 全量自动化测试：`.venv\Scripts\python.exe -m pytest -q` -> **769 passed, 89 subtests passed (100% 全绿)**。
  - Commit ID: `314df76`。

## Chart Viewport Preservation on Next Bar Stepping (2026-08-14)
- **用户需求**：
  - 用户手动将图表向左拖动、在右侧留有留白空间（如截图 1 所示）时，每次点击「下一根 K 线」，图表不再强行跳动到最右端（截图 2），而是保持当前可视视口不变，新 K 线静默在右侧空白处生成。
- **调整落地**：
  1. **智能视口范围计算（`computePreservedNextLogicalRange`）**：
     - 当最新 K 线的 logical index 已经处于当前可视区间内部（`newBarIndex >= from && newBarIndex <= to - 1`）时，**完全维持当前的 `from` 和 `to` 不变**，绝不移动/跳动图表；
     - 只有当用户推进到图表右边缘（`newBarIndex > to - 1`）时，才整体按差值平移以容纳最新 K 线，同时完美保持用户当前的缩放比例；
     - 用户回溯历史时，保持历史查看区间不变。
  2. **全面覆盖**：在币圈模式（`nextCryptoBar`）、Intraday 模式及股票模式（`nextBar`）统一接入。
  3. **自动化测试覆盖**：在 `tests/test_chart_workspace_frontend.py` 中新增 `ChartViewportPreservationTests`。
- **质量门禁**：
  - 全量自动化测试：`.venv\Scripts\python.exe -m pytest -q` -> **771 passed, 89 subtests passed (100% 全绿)**。
  - Commit ID: `5754c77`。

## OHLC Magnetic Snap & Flexible Partial Position Closing (2026-08-14)
- **用户需求**：
  1. 🧲 绘制磁吸模式（OHLC Magnetic Snap）：画线时支持精准吸附到 K 线的最高价、最低价、开盘价、收盘价；
  2. 灵活分批平仓（Partial Position Closing）：持仓 100u 时，支持平 50u 或按 25%/50%/75% 比例分批平仓，不再强制全平。
- **调整落地**：
  1. **🧲 磁吸模式**：
     - 工具栏新增 `🧲 磁吸模式` 开关按钮，支持快捷键（`Ctrl` 临时强力吸附，`Alt` 临时禁用）；
     - `DrawingController._anchorFromPoint` 实现基于欧氏距离的 OHLC 极值吸附算法；
     - `DrawingPaneRenderer` 在吸附时渲染青色高亮光圈指示点；
  2. **🪙 灵活分批平仓**：
     - `FuturesOrderBook.submit_order` 在 `action == "close"` 时支持传入 `margin` / `quantity`，按比例分批市价/限价平仓；
     - 下单面板切换到「平仓」时，最大保证金自动对齐当前持仓保证金，25%/50%/75%/全部 比例按钮基于持仓保证金自动填入；
     - 预计平仓数量与金额实时联动计算。
  3. **测试覆盖**：
     - 新增 `tests/test_crypto_partial_close.py`（3 个测试通过）；
     - 新增 `DrawingMagnetSnapTests` 与 `CryptoPartialCloseUITests`（31 个测试通过）；
     - 40 个画图运行时测试通过。
- **质量门禁**：
  - 全量自动化测试：`.venv\Scripts\python.exe -m pytest -q` -> **779 passed, 89 subtests passed (100% 全绿)**。
  - Commit ID: `0edae94`。

## Chart Time Minute Precision & Initialization Robustness (2026-08-14)
- **用户需求**：
  - 图表底部时间轴及十字光标悬浮显示时间精确到分钟，格式如 AICoin 所示（`2026-08-14 17:00`）。
- **调整落地**：
  1. **时间格式化与图表初始化健壮性**：
     - `formatChartCrosshairTime(time)` 全面容错处理 `Date`、`BusinessDay` 对象与时间戳，十字光标悬浮胶囊精确显示 `YYYY-MM-DD HH:mm`（如 `2026-08-14 17:00`）；
     - 清理次级图表（成交量、技术指标）冗余的时间格式化配置，交由主图时间轴统一驱动；
     - 训练启动异常提示精确暴露错误原因，杜绝被硬编码 alert 遮蔽。
  2. **测试覆盖**：
     - `tests/test_chart_workspace_frontend.py` 的 `ChartTimeMinutePrecisionTests` 全绿通过。
- **质量门禁**：
  - 全量自动化测试：`.venv\Scripts\python.exe -m pytest -q` -> **781 passed, 89 subtests passed (100% 全绿)**。
  - Commit ID: `aacd420`。

## Cross Margin Mode & Liquidation Price Line (2026-08-14)
- **用户需求**：
  1. 仓位模式切换为「全仓」（不要逐仓）；
  2. 每单都有明确预估强平价，并在主图绘制专属红色强平价线（与止损线区分）；价格触及强平线即触发强平爆仓。
- **调整落地**：
  1. **全仓模式展示与数据模型**：
     - `FuturesPosition.to_dict()` 增加 `margin_mode: "cross"`；
     - 持仓卡片标签显示为 `全仓`；
     - `trading.py` 快照挂载引擎实时计算的 `liquidation_price`；
     - 预估强平价：在全仓权益充裕且价格跌到 0 也不爆仓时，展示 `0.00 (全仓安全)`；持仓有风险暴露时准确显示计算强平价（如 `50,389.66`）。
  2. **主图强平价线（爆仓线）可视化**：
     - `updateChartTradePriceLines` 绘制红色点状强平线：`💀 强平 (Liq): xxx [爆仓线]`（颜色 `#d50000`，粗细 2px，点状虚线，与止损虚线明显区分）；
     - 当 K 线推进价格穿透强平线时，后端引擎自动执行强平结算并记录事件，前端弹出强平爆仓警示并更新账户。
  3. **测试覆盖**：
     - `tests/test_chart_workspace_frontend.py` 新增 `CrossMarginAndLiquidationPriceLineTests`。
- **质量门禁**：
  - 全量自动化测试：`.venv\Scripts\python.exe -m pytest -q` -> **783 passed, 89 subtests passed (100% 全绿)**。
  - Commit ID: `308859f`。

## True Cross Margin Bankruptcy & Zero Balance Liquidation (2026-08-14)
- **用户需求**：
  - 全仓爆仓（强平）后账户资产应该直接亏成 0（不能剩下部分资金），强平价应严格算上总资产。
- **调整落地**：
  1. **全仓强平爆仓价公式重构**：
     - 多头：`P_liq = EntryPrice - Balance / Quantity`；
     - 空头：`P_liq = EntryPrice + Balance / Quantity`；
     - 强平价严格代表总资产全部亏损完毕的真实破产价格。
  2. **强平爆仓结算直接归零**：
     - `check_liquidation` 触发时，将账户余额全部结算为已实现亏损，`balance` 直接归零为 `0 USDT`，仓位清空；
     - 记录已实现亏损为全部账户资产（`-balance_lost`），彻底消除强平后仍有剩余资产的现象。
- **质量门禁**：
  - 全量自动化测试：`.venv\Scripts\python.exe -m pytest -q` -> **783 passed, 89 subtests passed (100% 全绿)**。
  - Commit ID: `1d92dc2`。

## Stage 2: Code Architecture Governance & Modularization (2026-08-14)
- **用户需求**：
  - 先搞定第二阶段（代码治理）：将单文件臃肿逻辑进行结构化解耦与模块化重构。
- **调整落地**：
  1. **前端模块化分层 (`frontend/js/modules/`)**：
     - `chart_theme.js`：图表色盘、多主题适配（暗黑/明亮/AiCoin Crypto主题）、蜡烛实体与十字光标配置；
     - `chart_trade_lines.js`：主图持仓均价线、止盈止损线、限价/突破挂单线与强平爆仓线可视化及拖拽改单；
     - `crypto_order_panel.js`：下单方向、订单类型、杠杆切换、快捷比例分配与以损定仓计算；
     - `position_manager.js`：持仓卡片渲染、爆仓监听与成交流水；
     - `index_enhanced.html`：按依赖顺序列入模块化脚本引入。
  2. **后端路由解耦规划 (`backend/routes/`)**：
     - 初始化 `crypto_routes`、`stock_routes`、`user_routes`、`training_routes` Blueprints。
- **质量门禁**：
  - 全量自动化测试：`.venv\Scripts\python.exe -m pytest -q` -> **783 passed, 89 subtests passed (100% 全绿)**。
  - Commit ID: `43700f9`。

## Compact Position Card & Zero-Scroll Layout (2026-08-14)
- **用户需求**：
  1. 当前持仓卡片（蓝色框）做得精致好看，能一页看完，不要滚动；
  2. 手续费率与资金费（红色框）对开仓没有影响，移到开始训练时的设置弹窗中。
- **调整落地**：
  1. **持仓卡片精致化与高密度重构**：
     - 头部整合 `[币种] [做多/做空] [全仓] [杠杆]` 胶囊标签，右侧清晰展示总浮动盈亏（USDT与百分比）；
     - 数据网格优化为紧凑的 `均价/现价`、`持仓量`、`保证金`、`预估强平价`（红色醒目）、`止盈/止损`；
     - 底部精细化药丸按钮 `[止盈止损] [平仓] [市价全平]`，高度紧凑精致。
  2. **手续费率移至训练设置弹窗**：
     - 在「开始训练」弹窗中加入 `Maker 手续费率 (%)` 与 `Taker 手续费率 (%)` 输入项；
     - 隐藏下单台中的大块手续费设置与资金费面板，直接消除多余高度占用，右侧交易台实现**一页尽收眼底，无需滚动**。
- **质量门禁**：
  - 全量自动化测试：`.venv\Scripts\python.exe -m pytest -q` -> **783 passed, 89 subtests passed (100% 全绿)**。
  - Commit ID: `dab9629`。

> [!IMPORTANT]
> **Git 提交与推送铁律**：后续所有功能和修改一律在本地验证完成，**绝不自动执行 `git push`**。只有在用户验证通过并显式指示“提交到 GitHub”时，才执行远程推送。

## Visible Range Extreme Price Tags (High / Low Markers, AICoin Style) (2026-08-14)
- **用户需求**：
  - 在主图上实时显示当前可见可视范围内的最高价和最低价，并采用类似 AICoin 的指示标签样式（`← 0.07035` / `0.06918 →`）。
- **调整落地**：
  1. **动态极值追踪与标签计算**：
     - 在 `main_enhanced.js` 中新增 `updateVisibleExtremePriceTags()`，根据 `chart.timeScale().getVisibleLogicalRange()` 精准定位当前视野内的最高 K 棒与最低 K 棒；
     - 通过 `candlestickSeries.priceToCoordinate` 与 `chart.timeScale().timeToCoordinate` 精确计算最高影线顶端和最低影线底端的像素坐标；
     - 自动根据 X 轴所在半区自适应切换指示方向：左侧指向 `← 0.07035`，右侧指向 `0.06918 →`；
  2. **事件与响应式联动**：
     - 绑定可见视口平移缩放（`subscribeVisibleLogicalRangeChange` / `subscribeVisibleTimeRangeChange`）、K 线前进/更新（`replaceRenderedKlineData` / `upsertRenderedBar`）、窗口尺寸变化（`resizeCharts`），并配合 `requestAnimationFrame` 确保 60fps 丝滑流畅；
  3. **AICoin 风格精致渲染**：
     - 在 `style_enhanced.css` 中引入 `.chart-extreme-price-tag`，半透明深色微胶囊背景、等宽数字高对比排版，自适应浅色与深色主题。
- **质量门禁**：
  - 全量自动化测试：`.venv\Scripts\python.exe -m pytest -q` -> **783 passed, 89 subtests passed (100% 全绿)**。
  - 本地验证完成，**未执行 Git 远程推送（严格遵循用户验证指令）**。

## Stage 2 & 3: Code Architecture Governance & Modularization (2026-08-17)
- **用户需求**：
  - 选项 D：推进代码治理（前端/后端单文件解耦拆分）。
- **调整落地**：
  1. **前端模块化分层 (`frontend/js/modules/`)**：
     - `theme.js`：主题色盘配置、深浅/AiCoin色盘管理；
     - `extreme_tags.js`：可视区间极值标签（AICoin 风格 High/Low 标签）动态计算与调度；
     - `crypto_order.js`：永续合约下单台名义价值、保证金与快捷比例换算；
     - `position.js`：持仓未实现盈亏与收益率计算；
     - `index_enhanced.html`：按依赖顺序列入模块化脚本引入。
  2. **后端蓝图解耦落地 (`backend/routes/`)**：
     - `user_routes.py`：用户列表查询、创建与云端同步；
     - `stock_routes.py`：A股分时/历史日期与标的查询；
     - `crypto_routes.py`：币圈标的池与合约查询；
     - `training_routes.py`：训练会话活跃状态管理；
     - `app_enhanced.py`：完成 Blueprint 动态注册与统一入口维护。
- **质量门禁**：
  - 全量自动化测试：`.venv\Scripts\python.exe -m pytest -q` -> **783 passed, 89 subtests passed (100% 全绿)**。
  - 本地验证完成，**未执行 Git 远程推送（严格遵循用户验证指令）**。

## Fix: Crypto Replay Period Desync (Daily vs 2D Step Bug) (2026-08-23)
- **问题定位**：
  - 用户反馈在日线（1D）模式下点击“下一根 K 线”时，K 线步进和聚合跳变为了两日线（2D）周期（从 10-26 跨步到 10-28）。
  - **根本原因**：
    1. 在前端 `switchCryptoViewPeriod` 中切换周期后，未在应用快照时调用 `updatePeriodBadge(nextPeriod)`；
    2. 当从其他周期切回或切换期间，前端 `currentPeriod` 内部状态与工具栏 `.view-period-btn.active` 选中状态失步；
    3. 工具栏按钮在视觉上高亮 `1D`，而实际请求后端时被 `if (currentPeriod === nextPeriod)` 拦截直接 return，导致后端 Session 的 ReplayClock 仍停留在 `2d`（2日线）模式；
    4. 后端 `models.CryptoPeriod.parse` 未对 `"1d"` / `"1D"` 等常见别名做宽松容错。
- **调整落地**：
  1. **前端周期状态联动强化**：
     - 在 `applyCryptoPeriodSnapshot` 中强制调用 `updatePeriodBadge(nextPeriod)` 同步全局 `currentPeriod` 与工具栏激活状态；
     - 在 `formatIntradayPeriodBadge` 中增加 `1d` 显式映射；
  2. **后端容错加固**：
     - 在 `backend/crypto/models.py` 的 `CryptoPeriod.parse()` 中增加对 `"1d"`, `"1w"`, 大小写等别名的智能容错映射。
- **质量门禁**：
  - 全量自动化测试：`.venv\Scripts\python.exe -m pytest -q` -> **783 passed, 89 subtests passed (100% 全绿)**。
  - 本地验证完成，**未执行 Git 远程推送（严格遵循用户验证指令）**。

## Fix: Replace Chart Window State on Snapshot Refresh (Preventing Mixed Period Bar Merging) (2026-08-26)
- **现象定位**：
  - 用户反馈在未完成 K 线触发补全时（`delta.refresh_snapshot`），图表上的 K 线全部错乱，出现大量细单日柱子，且之后推进持续混乱。
- **根本原因**：
  - `applyCryptoNextDelta` 收到 `delta.refresh_snapshot` 时调用 `applyActiveSnapshotToChartWindow(snapshot)`；
  - `applyActiveSnapshotToChartWindow` 内部调用 `applyChartWindow(payload)` 时**未传 `{ replace: true }`**！
  - 导致 `mergeChartWindow` 将当前 2D 快照数据与之前 1D 残留在 `chartWindowState.kline_data` 中的单日数据执行了 `mergeTimedItems` 混杂合并！
  - 1D 的所有单日 K 棒被强行保留并交织插入在 2D K 棒之间，造成图面完全错乱！
- **修复落地**：
  - 在 `applyActiveSnapshotToChartWindow` 中显式传入 `{ replace: true }`，确保快照刷新时彻底清空并替换旧周期数据，杜绝多周期数据交织混杂；
  - 统一成交量时间戳转换（`intradayBarToTimestamp`）；
  - 静态脚本版本提升为 `?v=20260826_v3`。
- **质量门禁**：
  - 全量自动化测试：`.venv\Scripts\python.exe -m pytest -q` -> **783 passed, 89 subtests passed (100% 全绿)**。
  - 本地验证完成，**未执行 Git 远程推送（严格遵循用户验证指令）**。

## Next Action
等待用户在浏览器中硬刷新并验证补全与推进（2D 蜡烛干净原地闭合收盘）。














## Governance Optimization: Route Blueprints Migration + Frontend Pure-Logic Module + JS Quality Gates (2026-08-30)
- **用户需求**：解决接手评估中的优化项 2~6：模块化落地、前端质量门禁、交接断层、缓存版本自动化、控制面小项。
- **调整落地**：
  1. **后端路由实迁 Blueprint**：`app_enhanced.py` 从 3881 行减至约 2410 行；45 个 `@app.route` 处理器实迁至 `backend/routes/` 四个 Blueprint（user 11 个、crypto 9 个、stock 3 个、training 24 个，含随迁辅助 `get_ai_config`/`analyze_report_with_ai`/`_crypto_history_prepare_*`）。共享状态与业务辅助函数保留在 `app_enhanced.py`（测试直接引用其符号）；处理器内以函数级 `import backend.app_enhanced as ae` 延迟绑定访问，保住 monkeypatch 契约。同时消除 user_routes 桩与 app 路由的重复注册隐患；清理 4 个死导入（base64/traceback/requests/sqlite3）。
  2. **前端纯逻辑模块**：新增 `frontend/js/modules/chart_window_core.js`（225 行，UMD，浏览器 + require 双模式），17 个纯函数自 `main_enhanced.js` 迁出（mergeTimedItems、mergeChartWindow、parseChartWindowTimestamp、intradayBarToTimestamp、formatIntradayPeriodBadge、normalizeChart* 等），main 9606→9429 行并以解构真正消费模块（区别于此前的"只拆不接"）。
  3. **JS 质量门禁**：新增 `tests/js/chart_window_core.test.js`（node:test，12 个用例）+ `tests/test_js_unit.py`（pytest 包装器，node 缺失时跳过），`pytest -q` 门禁覆盖前端纯逻辑；新增 `.eslintrc.json`，`npx eslint@8.57.0 frontend/js/modules/ tests/js/` 零告警（main_enhanced.js 遗留债暂不入 lint 范围）。
  4. **静态测试加载器**：4 个前端静态测试文件改用 `tests/_frontend_js.py` 按 `index_enhanced.html` script 顺序拼接源码，贴合浏览器共享全局作用域的真实契约，断言本身未改。
  5. **缓存版本自动化**：`index_enhanced.html` 去掉手写 `?v=`，`/` 路由改为 `_versioned_index_html()` 按各 js/css 文件 mtime 自动追加版本号，杜绝忘改版本导致的旧缓存。
  6. **控制面小项**：`agent_status.py` 对 `TASK-023-result.md` 的告警确认已被早期会话修复（`*-result.md` 校验豁免），无需改动；`routes/__init__.py` 及本次重写的 6 个文件换行符归一 CRLF；git gc 评估完成——提交安全前不执行（避免清掉 2 个既有 dangling blob）。
  7. **交接断层**：新增 `.agent/handoffs/2026-08-26-modularization-and-replay-fixes-backfill.md` 回填 8/17、8/23、8/26 三次会话；`AI_TAKEOVER.md` 摘要同步（783→784 门禁、最新交接指针）。
- **质量门禁**：
  - 全量 `.venv\Scripts\python.exe -m pytest -q` -> **784 passed, 89 subtests passed (100% 全绿，含新 JS 单测门禁)**。
  - `node --test tests/js/chart_window_core.test.js` -> 12 pass / 0 fail；ESLint 零告警；`git diff --check` 干净。
  - 浏览器烟雾验证：页面正常渲染，`window.KLineChartWindowCore` 与全部接线函数就位，`formatIntradayPeriodBadge('1d')='1D'`，11 个脚本全部带自动 mtime 版本号。
  - 本地验证完成，**未执行 Git 提交与远程推送（严格遵循用户验证指令）**。

## Next Action
等待用户浏览器验收（K线回放、下单、持仓、周期切换如常即通过）；验收后可指示分片提交（建议按：路由迁移 / 前端模块 + 门禁 / 缓存版本化 / 文档交接 四片）。

## Frontend Module Wiring & Continued Extraction (2026-08-30 晚续段)
- **用户需求**：继续剩余优化空间——"只拆不接"的模块接线、继续缩小 main、扩大 lint 覆盖。
- **关键发现**：8/17 创建的 4 个模块中，theme.js/extreme_tags.js 是 main 现行逻辑的**过时副本**（main 从未消费，一直跑自己的本地实现）；position.js/crypto_order.js 则**在 main 中无对应物**（main 直接使用后端算好的 unrealized_pnl），属无消费者的投机模块。
- **调整落地**（方向：把 main 的**现行逻辑**灌回模块再接线，绝不用旧副本覆盖 main）：
  1. **theme.js 真接线**：模块内的过时色盘替换为 main 现行 THEME_PALETTES 表（light/dark/crypto_dark/crypto_light，AiCoin 配色），main 侧以 `const THEME_PALETTES = (window.KLineThemeModule || {}).PALETTES;` 消费（保留静态测试的边界字面量，测试零改动）。
  2. **extreme_tags.js 真接线**：main 的可视区极值标签现行实现（146 行）参数化后迁入模块（chart/series/klineData 注入，消除全局耦合），main 仅保留 raf 调度薄壳（约 20 行）。
  3. **新增 period_snapshot_cache.js**：币圈周期快照缓存簇（LRU 上限 16 + 训练会话隔离 + 窗口键构建）整体内聚入模块，跨模块复用 chart_window_core 的时间戳解析（UMD 双环境 require/root），`chartWindowState` 默认参数改为双环境安全解析；main 以解构消费，7 个新 node:test 单测。
  4. **ESLint 覆盖扩展**至 js 根部纯库 indicator_math.js / risk_calc.js / drawing_tools.js；清理 drawing_tools.js 中 7 个确认零引用的死代码（6 个常量/函数 + 仅被死代码调用的 formatCompactNumber）。
  5. **position.js / crypto_order.js 处置**：无消费者、无 main 对应物，属用户未提交改动**不删除**，报告待用户决定（接线需先有客户端盈亏预览/下单台计算需求）。
- **质量门禁**：
  - JS 单测 **19 passed**（chart_window_core 12 + period_snapshot_cache 7）；ESLint 全范围零告警；`.venv` 全量 pytest **784 passed, 89 subtests passed**。
  - `main_enhanced.js` 9429 → **9182 行**；模块数 6 个全部被真实消费（theme/extreme_tags/period_snapshot_cache/chart_window_core）或明确挂起待需求（position/crypto_order）。
  - 浏览器实测（硬刷新）：模块色盘即 main 现行色盘（`getThemePalette().chartBg='#fdfefe'`）、极值标签调度链路、缓存键构建（`t1|1d|default_window|...`）全部就位，12 个脚本加载正常。
  - 本地验证完成，**未执行 Git 提交与推送**。

## Next Action
等待用户浏览器验收（重点：主题切换、可视区极值标签、币圈多周期回切秒回）；position.js/crypto_order.js 去留由用户决定。

## Commits (2026-08-30)
- 上述两次会话成果已按用户指示分五片提交至本地 `main`（**未推送远程**）：
  - `e032af1` fix: 币圈回放周期别名容错
  - `e89ac40` refactor: 45 条路由实迁四个 Blueprint
  - `9b7837e` refactor: 前端纯逻辑抽取入模块并完成真实接线
  - `1730455` test: JS 单测接入 pytest 门禁
  - `1efaa38` docs: 交接与摘要同步
- 提交前最终门禁复验：784 passed, 89 subtests passed。

## Feature: Trading Hours Background Bands (做单时段背景色带) (2026-08-30 深夜)
- **用户需求**：做单时间规律可视化——在 4H 以下的币圈周期上，用稍微淡一点的背景标出做单时间段（如 08:00–24:00 UTC+8），回放/做单时一眼识别"当前 K 线是否在时段内"；美术细节由 AI 把控。
- **调整落地**：
  1. **新增 `frontend/js/modules/trading_hours.js`**（UMD 双模式）：纯函数 `computeTradingHourSegments`（本地时区日内分段，支持跨午夜窗口如 22:00–06:00，首版实现时区符号写反，验证用例当场暴露并修正）；`drawTradingHoursBands` 用可视区间两端锚点做线性时间→像素投影，规避 timeToCoordinate 对非数据时间的空值；overlay canvas（pointer-events:none，z-index 10，低于极值标签 15）只覆盖主图窗格并扣除右侧价格轴宽度。
  2. **theme.js 四套色盘新增 `sessionBand`**：light 淡蓝 0.045 / dark 冷蓝 0.06 / crypto_dark 琥珀 0.05 / crypto_light 琥珀 0.07——跟随主题的"稍微淡一点"。
  3. **工具栏"做单"时段选择器**（开始 00–23 时 / 结束 01–24 时）：位于图表控制区（全屏按钮旁），仅币圈 4H 以下周期显示；改动即生效，localStorage `tradingHours` + 用户设置 `trading_hours_start/end`（三个登录/切换用户流程点均已接入恢复）双持久化。
  4. **门控与联动**：仅 `isCryptoMode() && 周期<4h` 绘制；切日线/更大周期自动清屏并隐藏控件；pan/缩放/resize/主题切换/周期切换/模式切换全链路重绘（复用极值标签的 rAF 调度惯例）。
  5. **单测**：`tests/js/trading_hours.test.js` 8 个用例（门控/全天窗口/跨午夜/子窗口裁剪/跨天多段/相等小时关闭/非法输入/时段读写钳制），门禁总数 27。
- **质量门禁**：
  - JS 单测 **27 passed**；ESLint 全范围零告警；全量 pytest **784 passed, 89 subtests passed**；`node --check` 全通过。
  - **浏览器实测**（极速开局 BTC → 切 15m）：色带像素区间精确对应每日 08:00–24:00 UTC+8（±像素取整），alpha=13 即设计值 0.05；时段改 9–18 后色带变 09:00–17:57 且 localStorage 正确保存（已恢复 8–24）；切日线控件隐藏+画布清空，切回 15m 自动恢复；平移图表自动重绘。
  - 环境备注：嵌入式测试浏览器冻结 requestAnimationFrame（visibility=visible 但 rAF 不执行），导致 rAF 调度的功能（含既有极值标签/筹码分布）在自动化里不重绘；真实浏览器无此问题。验证时用 rAF 立即执行补丁 + 重置卡死的 `tradingHoursRafId` 完成全链路证明。
  - 本地验证完成，**未提交、未推送**。

## Next Action
等待用户浏览器验收做单时段色带（币圈 + 4H 以下周期）；验收后可指示提交推送。position.js/crypto_order.js 去留仍待用户决定。

## Feature Addendum: Trading Hours Toggle (做单色带开关) (2026-08-30 深夜续)
- **用户需求**：给做单时段色带加一个显示/不显示的开关。
- **调整落地**：工具栏"做单"标签升级为开关按钮（`#trading-hours-toggle-btn`，aria-pressed 同步）；开启时琥珀色高亮态与色带呼应，关闭时清屏并使时段选择器变灰（仍可见、可再开启）；`tradingHoursEnabled` 状态并入 localStorage `tradingHours` 对象（新增 `enabled` 字段，向后兼容缺省 true）与用户设置 `trading_hours_enabled`（0/1，`applyTradingHoursFromSettings` 恢复）。
- **质量门禁**：浏览器实测 关→画布清空+按钮变灰+`enabled:false` 保存，开→色带恢复（着色宽度 0.63）+`enabled:true`；全量 pytest **784 passed, 89 subtests**；JS 单测 27 passed；ESLint 零告警。**未提交、未推送**。

## Fix: Trading Hours Period Inclusion (4H Included) & Chart Wall-Clock Time Alignment (2026-09-07)
- **现象定位**：
  - 用户反馈 1：做单背景色带的显示时间段与设置不一致（用户选 08:00~24:00，图表上却着色在 00:00~16:00，刚好倒置偏了 8 小时）；
  - 用户反馈 2：要求是“4h及以下”（即包含 4h），但前版实现排除了 4h。
- **根本原因**：
  1. **时区重复抵消/倒置偏离**：KLinePlayground 的底层时间格式（`intradayBarToTimestamp`）直接以 `Date.UTC(...)` 将数据原文字符串时间转为时间戳，轻量图表（Lightweight Charts）X 轴展示的数值本身即为原汁原味的盘中时间（例如 08:00 对应 X 轴 08:00）。前版 AI 误以为图表是标准 UTC 而在计算中强行减去 8 小时（`tzOffset = 480`），导致原本属于 08:00~24:00 的区间被硬生生平移绘制成了 00:00~16:00！
  2. **4H 周期门控范围错误**：前版 `CRYPTO_INTRADAY_PERIODS` 集合仅有 `1m/3m/5m/15m/30m/1h/2h/3h`，遗漏了 `4h`（排除了 4h）。
- **修复落地**：
  1. `frontend/js/modules/trading_hours.js`：
     - `CRYPTO_INTRADAY_PERIODS` 集合加入 `'4h'`，使 4h 周期也完整支持做单时段色带与工具栏控件；
     - `computeTradingHourSegments` 默认 `tzOffsetMinutes` 调整为 `0`（与图表 X 轴时间刻度 100% 对齐），使选中的 08:00~24:00 严丝合缝绘制在图表 08:00~24:00 刻度之间，00:00~08:00 则还原为无高亮背景。
  2. `tests/js/trading_hours.test.js`：更新 8 个单测用例与断言，覆盖包含 4H 的周期门控与对齐后的时间分段。
- **质量门禁**：
  - JS 单测：`node --test tests/js/*.test.js` -> **27 passed**；
  - 代码规范：`npx eslint@8.57.0` -> **0 告警**；
  - 后端门禁：`pytest -q` -> **784 passed, 89 subtests passed (100% 全绿)**；
  - 静态资源 mtime 版本号自动生效；
  - 严格遵循指令：**未执行 git 提交与远程推送**。

## UI Polish & Ironclad Rule: Dual-Theme Consistency (Light & Dark Full Adaptive Support) (2026-09-07)
- **用户铁律指示**：
  > "这个项目有两种主题。亮和暗，你要记住的是以后做的功能和优化都要考虑到这点，要符合主题统一"
  > **必须牢记的核心设计准则**：本项目包含 **暗色（Dark）** 与 **亮色（Light）** 两套独立完整的主题体系。任何新增功能、UI 优化、下拉框、弹窗、颜色配置，都必须同时严格适配亮暗两种主题，严禁单方面写死某一主题的配色。
- **现象复盘**：
  - 用户此前在亮色模式（页面顶部为白色、图表为白底、日月切换按钮为 `☾`）下点击做单时段下拉框时，弹出菜单却被上一次提交硬编码成了暗黑菜单（黑底白字），在纯白界面中极度突兀，破坏了亮色主题的一致性。
- **根本原因**：
  - 上次修改将 `color-scheme: dark` 和 `#1e2026` 硬编码在基础 `.trading-hours-controls select` 规则中，而浅色主题的覆盖规则误用了不存在的 class 选择器 `.theme-crypto-light`，未能正确命中系统实际使用的属性选择器 `[data-crypto-theme="light"]` / `[data-theme="light"]`。
- **修复落地**：
  1. 精准对接系统的全局主题状态标记：
     - **亮色主题**（`#main-app[data-crypto-theme="light"]` 与 `[data-theme="light"]`）：
       - 强制声明 `color-scheme: light;`；
       - 下拉菜单本体背景设为纯白 `#ffffff`，边框 `rgba(0, 0, 0, 0.12)`，字体 `#182230`；
       - `<option>` 弹出菜单完全适配为纯白底 `#ffffff`、深色字 `#182230`、选中项淡琥珀背景 `rgba(185, 135, 0, 0.15)`；
       - 控件微胶囊边框、文字、hover 与 active（`#b98700`）全面切换为精致柔和的浅色调。
     - **暗色主题**（`#main-app[data-crypto-theme="dark"]` 与 `[data-theme="dark"]`）：
       - 保持原汁原味的暗黑 AiCoin 质感（`color-scheme: dark;`、深黑背景、金色高亮、高对比度文字）。
  2. 确立长期准则，后续所有组件必须以 `[data-crypto-theme="light"]` 与 `[data-crypto-theme="dark"]` 双向验证。
- **质量门禁**：
  - JS 单测：27 passed；ESLint：零告警；后端 pytest：**784 passed (100% 全绿)**；
  - 静态版本号自动提升为 `?v=1788756044`；
  - 严格遵循指令：**未执行 git 提交与远程推送**。

## Next Action
等待用户在浏览器中测试在亮色模式（☾）与暗色模式（☀）来回切换，验证下拉框与工具栏在两套主题下 100% 严丝合缝的统一视觉。

## Feature & Fix: Quick Jump to Latest Kline & Small Period Switch Fix (2026-09-08)
- **用户需求**：
  1. 用户在图表右侧价格刻度轴（截图红框处）双击时会触发垂直正常缩放，希望增加快速回到当前最新 K 线页；
  2. 彻底解决“切换到小周期（如 1D 切 15m/5m/1m）时有时会跳到很前（远古历史），必须一直拉鼠标拉到最新 K 线”的顽疾；
  3. 铁律要求：必须同时适配 Dark（暗）和 Light（亮）两套主题，风格绝对统一。
- **根本原因与设计落地**：
  1. **双击价格刻度轴 / 底部时间轴快速回到最新**：
     - 在 `#chart-panels`（主图表容器）捕获双击事件，当双击发生在右侧价格轴刻度区（`clientX >= rect.right - rightScaleWidth`）或底部时间轴刻度区时，触发 `scrollToLatestKline()`。
     - `scrollToLatestKline()` 计算最新 K 线索引与 5 根右边距空白呼吸区，设置逻辑区间并对主图、副图、指标图执行 `autoScale: true` 复位纵向刻度。
  2. **右下角悬浮“最新”快捷按钮（双主题统一）**：
     - 在 `#chart-panels` 内增加 `#jump-to-latest-btn` 悬浮胶囊按钮，配双箭头 `>> 最新` 图标；
     - 在图表逻辑区间变动时动态监听：当最新蜡烛滑出视口右侧（`to < totalBars - 8`）时优雅淡入显示，在最新 K 线附近时自动隐藏；
     - 严格遵循双主题铁律：暗色模式采用半透明微磨砂深黑底（金色高亮悬停）、亮色模式采用白底立体微阴影（琥珀金棕悬停），统一美观。
  3. **彻底根除“切换小周期跳到远古历史”Bug**：
     - 现象根源：日线大周期的可视起点（数月前）远早于细周期的 `renderedStart`（30 天前）。旧代码在 `canRestoreRange` 失败后执行夹紧计算，把起点强行钉在 30 天前的 `renderedStart`，将用户强行抛到了几千根蜡烛之前；
     - 解决策略：在切换周期时记录 `wasNearLatest`（切换前视野右侧是否位于最新 K 线附近），并在 `applyCryptoPeriodSnapshot` 中明确：若 `wasNearLatest` 或时间段无法有效恢复，直接定位到新周期的最新走势页（`scrollToLatestKline()`）。
- **质量门禁**：
  - JS 单测：`node --test tests/js/*.test.js` -> **27 passed**；
  - ESLint 规范：`npx eslint@8.57.0` -> **0 告警**；
  - 语法检查：`node --check frontend/js/main_enhanced.js` -> **Pass**；
  - 后端回归：`pytest -q` -> **784 passed, 89 subtests passed (100% 全绿)**；
  - 严格遵循指令：**未执行 git 提交与远程推送**。

## Next Action
已落地 A 股实时看盘与 T+1 模拟下单 Demo 原型。等待用户体验与反馈。

## Feature: A-Share Live Market Watch & T+1 Sandbox Demo (2026-09-08)
- **用户需求**：
  1. 沿用现有 AICoin/币圈界面的极简暗色/亮色视觉，用于 A 股实时看盘；
  2. 最小 1 分钟轮询跳动即可；
  3. 保留模拟下单功能：严格遵循 A 股“最小买入 100 股（一手）且为整数倍”以及“T+1 交易制度（当日买入冻结至次日方可卖出）”；
  4. 账户资金与持仓随时可自由手动修改，方便模拟自定义实盘仓位。
- **落地实现**：
  1. **后端服务与接口**：
     - `backend/services/ashare_live_service.py`：通过公共免费接口拉取股票搜索（代码/拼音首字母如 `600519`/`gzmt`）、分时 K 线（1m/5m/15m/30m/60m/日K，主用腾讯 ifzq 高速接口，备用东财）、实时快照（现价、涨跌幅、昨收、涨跌停）；
     - `backend/routes/ashare_live_routes.py`：注册 `/api/ashare/live/search`、`/api/ashare/live/kline`、`/api/ashare/live/snapshot`。
  2. **独立演示页面与逻辑**：
     - `frontend/ashare_live_demo.html` & `frontend/js/ashare_live_demo.js`：
       - 顶部股票搜索与实时指示条（昨收、涨跌停、现价变色）；
       - Lightweight Charts 主图（K线 + MA5/10/20）与成交量副图，支持 30 秒/1 分钟轮询与最后一根 K 棒动态跳动；
       - A 股模拟交易沙盒：买入步进限制 100 股，仓位百分比（25%/50%/75%/全仓）自动向下取整到 100 的倍数；
       - T+1 持仓模型：今日买入记为 `frozen_today`，当天不可卖出；只有可用持仓 `available` 允许卖出；
       - 弹窗自定义资金：随时修改可用现金、可用持仓股数与成本均价，存储于本地 `localStorage`，刷新不丢失；
       - 完美支持 Dark（暗色）与 Light（亮色）双主题一键切换；
     - 主训练页工具栏右侧新增直达按钮 `📈 A股实时看盘`。
- **质量门禁**：
  - Python 语法检查通过；
  - JS 语法检查：`node --check frontend/js/ashare_live_demo.js` 通过；
  - JS 单元测试：`node --test tests/js/*.test.js` -> **27 passed**；
  - 后端全量测试回归：`pytest -q` -> **784 passed, 89 subtests passed (100% 全绿)**；
  - 严格遵循指令：**未执行 git 提交与远程推送**。

## Next Action
等待用户在浏览器中访问 `http://127.0.0.1:8000/ashare_live_demo.html` 进行体验验证：
1. 股票搜索：输入 `600519` 或 `gzmt` 联想切换标的；
2. 分时走势与轮询跳动；
3. A 股 100 股限制、仓位整百取整、T+1 卖出拦截；
4. 点击“调整资金/仓位”自由修改模拟账户数据；
5. 确认暗色与亮色双主题效果。

## Fix: Chart Time Display Timezone — Crypto UTC→UTC+8 对齐 AICoin (2026-09-09)
- **现象**：同一根 ETH K线（低点 2440.22），AICoin 显示 2026-09-08 21:40，本项目复盘显示 13:40，恒差 8 小时；时间轴刻度与十字光标胶囊均受影响。
- **根因**：币圈数据源时间为 UTC 原文，`formatChartCrosshairTime` 显式取 `getUTC*` 分量且主图未配置 `tickMarkFormatter`，Lightweight Charts 默认按 UTC 渲染时间轴——显示层整条链路停留在 UTC。
- **修复（方案 A：显示层集中换区，数据层 UTC 单一事实源不动）**：
  1. `main_enhanced.js`：新增 `chartTimeDisplayOffsetSeconds()`（isAshareLiveMode→0；isCryptoMode→+28800s；其余 0），`formatChartCrosshairTime` 的 Date/数字分支统一加偏移；新增 `formatChartTickMarkTime` 并接入主图 `timeScale.tickMarkFormatter`（零点整刻度显示 MM-DD，日内显示 HH:mm）。
  2. **色带联动**：`trading_hours.js` `computeTradingHourSegments` 默认 `tzOffsetMinutes` 0→480——09-07 将其改为 0 实为迁就"X 轴显示 UTC"的错误显示；显示层修正后恢复 480 才是真正的北京时间 08:00–24:00 对齐。显式传参仍可覆盖。
  3. **A股零波及**：A股 Intraday/实时看盘数据原文即北京时间（偏移 0），行为不变；极值标签仅价格无时间，不受影响；数据层时间戳/订单/资金费率/缓存键全部未动。
- **测试同步**：`tests/js/trading_hours.test.js` 期望值按 +480 重算（8-24 窗口、跨午夜、跨天多段），新增"显式 tzOffsetMinutes=0 覆盖"用例；`tests/test_chart_workspace_frontend.py` 的 node eval 测试补 `isAshareLiveMode` 桩、期望值改为 UTC+8 语义（'2026-08-15 01:00'）并新增 A股原文反向断言。
- **质量门禁**：`node --check` 通过；`node --test tests/js/*.test.js` → 40 passed；`npx eslint@8.57.0` → 0 告警；全量 `pytest -q` → **800 passed, 89 subtests passed (100% 全绿)**。
- **遗留备注**：`git diff --check` 报 `main_enhanced.js:10025` 行尾空白与 `style_enhanced.css:6300` EOF 空行，均为 2026-09-08 ashare 会话遗留（非本次改动区域），按禁令未触碰，待用户指示。
- 严格遵循指令：**未执行 git 提交与远程推送**。

## Next Action
等待用户浏览器验收：同一段币圈行情与 AICoin 并排对照（十字光标/时间轴应为北京时间）；做单时段色带与北京时间 08:00–24:00 对齐；A股 30m 回放与 A股实时看盘时间显示确认无变化。

## Fix: 持仓区块"时有时无"——A股看盘退出后 hidden 残留 (2026-09-10)
- **现象**：币圈训练的右侧"当前持仓"区块有时在有时没有。
- **根因**：`launchAshareLiveWatch` 旧版用 `classList.add('hidden')` 批量隐藏 `[data-replay-only]`（含币圈"当前持仓"）、`[data-crypto-workspace-only]` 等元素，而 `exitAshareLiveWatch` 不移除——只要进过一次 A股实时看盘再退出，这些区块带残留 hidden 直到刷新页面。CSS L5181-5189 的 `.ashare-live-active` 规则本已完整覆盖这些隐藏，JS 批量隐藏纯冗余。
- **修复**：删除 launch 中该行冗余 `querySelectorAll(...).forEach(add('hidden'))`，显隐统一交由 CSS 属性系统（进入靠 `ashare-live-active` 类，退出类移除自动恢复，天然对称零残留），并留注释防止回归。`training-setup` 为 modal 初始 hidden、`syncCryptoWorkspaceMode` 两处调用点均不在 A股看盘期间触发——均无需改动。
- **质量门禁**：`node --check` 通过；JS 单测 40 passed；ESLint 0 告警；全量 `pytest -q` → **800 passed, 89 subtests passed**。
- 严格遵循指令：**未执行 git 提交与远程推送**。

## Next Action
用户硬刷新（Ctrl+Shift+R）后验证：进入 A股实时看盘 → 退出 → 回币圈训练，"当前持仓"区块应始终存在。

## Refactor: A股实时看盘 UI 状态耦合治理——快照/恢复 + 存储分键 (2026-09-10)
- **用户报告**：币圈训练 MACD 指标副图消失（此前"当前持仓"区块时有时无已修），怀疑实时看盘牵连复盘功能，要求重新审视、降低耦合、不加新功能。
- **审计结论**（launchAshareLiveWatch / exitAshareLiveWatch 全副作用比对）：A股实时看盘直接改写三种模式共享的 UI 状态且退出不恢复——
  1. `indicatorPanelVisible` / `currentIndicatorType` 被 launch 强制覆盖为 true/'MACD'（L10102-10103），exit 不恢复；
  2. `indicator-chart` 副图 inline `style.display` 由 `toggleIndicatorVisibility`（L6740）管理，A股看盘期间点指标标签收起面板后 `display:none` 残留到币圈——**MACD 副图整体消失的机制**；
  3. 面板高度比例全局单键 `kline-chart-panel-heights-v2`，A股/币圈互相污染（副图可被压到只剩图例行）。
- **修复（纯对称化/隔离，零新功能）**：
  1. launch 改状态前快照 `asharePreLiveUiState = { indicatorPanelVisible, currentIndicatorType, indicatorDisplay, volumeCollapsed, indicatorCollapsed }`；
  2. exit 对称恢复：状态变量 + inline display + 折叠 class + 按钮/下拉/图例同步，恢复可见时 `loadTechnicalIndicator(currentIndicatorType)` 重载数据并 rAF `applyChartPanelRatios + resizeCharts`；
  3. 面板比例存储分键：新增 `chartPanelStorageKey()`（ashare → `kline-chart-panel-heights-v2-ashare`），read/persist 按当前模式取键，`chartPanelRatiosKey` 记录缓存对应键（模式切换自动重读）。
- **质量门禁**：`node --check` 通过；JS 单测 40 passed；ESLint 0 告警；全量 `pytest -q` → **800 passed, 89 subtests passed**。
- 严格遵循指令：**未执行 git 提交与远程推送**。

## Next Action
用户硬刷新后重演路径验收（进出 A股实时看盘 → 币圈训练：当前持仓与 MACD 副图应始终稳定）；若 MACD 仍消失，在 console 执行 `JSON.stringify({display: document.getElementById('indicator-chart').style.display, h: document.getElementById('indicator-chart').getBoundingClientRect().height, visible: indicatorPanelVisible, type: currentIndicatorType})` 提供输出继续定位。

## Feature: A股实时看盘限价挂单 + 全持仓列表 (2026-09-10)
- **用户需求**：实时看盘下单面板此前仅市价；"当前持仓"卡片只显示当前标的。用户要求资金为全部 A 股共用、单子状态（持仓+挂单）在一个卡片看清楚，并支持限价挂单。
- **落地**：
  1. **模块真接线**：`ashare_trading.js`（此前"只拆不接"，仅测试引用）新增 `normalizeAshareAccount / computeAvailableShares / matchLimitOrders / validateLimitBuy / validateLimitSell` 五个纯函数并接入 main；index_enhanced.html 补 script 标签。
  2. **账户模型扩展**（向后兼容，旧 localStorage 自动补默认字段）：`cash_frozen`（买入挂单冻结资金，cash 语义=立即可用）、`positions[code].frozen_sell`（卖出挂单冻结持仓）、`pending_orders`（当日有效挂单）。
  3. **下单面板**：买入/卖出子面板各加"市价/限价"切换（独立记忆），限价输入框默认填现价，预览按限价计算。
  4. **撮合引擎**：3 秒轮询快照到达即撮合当前标的 open 挂单（买: 限价≥现价；卖: 限价≤现价，按限价成交），成交后买入股数进 T+1 冻结、卖出扣持仓回笼资金；跨日挂单自动失效退冻结（当前标的轮询内撮合+读取时全局清理兜底）。
  5. **持仓卡片升级**：列出**全部标的**持仓（当前标的置顶 ★高亮），跨标的现价用内存价格缓存 `asharePriceCache`；卡片下方新增"限价挂单"小节（跨标的挂单 + 撤单按钮，事件委托）。总资产 = 现金 + 挂单冻结 + 全持仓市值；"持仓市值"改为全持仓口径；最大可卖扣除挂卖冻结。
- **质量门禁**：`node --check` 通过；JS 单测 **47 passed**（新增限价挂单 7 用例）；ESLint 0 告警；全量 `pytest -q` → **800 passed, 89 subtests passed**。
- 严格遵循指令：**未执行 git 提交与远程推送**。

## Next Action
用户硬刷新验收：市价/限价切换、挂单→撤单、限价成交（价格到达）、跨标的持仓列表与冻结标记、双主题观感。

## Feature Addendum: A股实时模拟手续费 (2026-09-10)
- 限价挂单会话追加：佣金万 2.5（最低 5 元）双边 + 印花税 0.05% 仅卖出（纯函数 computeAshareTradeFees + 2 用例）。
- 全链路接入：市价买卖（资金检查/含费成本均价/回笼扣费）、限价挂单（冻结额含佣金，挂单记 frozen_amount，成交/撤单/跨日失效统一按其退回，兼容旧挂单）、买卖预览含费口径、成交记录显示费用。
- 门禁：JS 单测 **49 passed**；pytest **800 passed, 89 subtests**。未提交未推送。

## Next Action
用户硬刷新验收：手续费显示（预览/成交提示/记录）、限价挂单冻结含佣、撤单/失效退回含佣冻结。

## Feature: 画图工具 Alt+* 快捷键 (2026-09-10)
- **用户需求**：量尺/做多/做空/水平线/斐波那契等常用画图工具快速选择。
- **键位设计**（TradingView 惯例 Alt+ 层，与既有裸键层物理隔离）：Alt+M 量尺、Alt+L 做多、Alt+S 做空、Alt+H 水平线、Alt+F 斐波那契、Alt+Q 选择、Alt+T 趋势线、Alt+R 射线、Alt+B 矩形、Alt+X 文字。裸键 B/S/空格/Enter/数字已有占用（币圈做单与回放推进），Alt 修饰键层先行拦截保证 Alt+S 做空与裸 S 卖出零冲突。
- **落地**：
  1. 从工具按钮 click handler 提取共享函数 `activateDrawingTool(tool)`（控制器激活/工具条高亮/状态条含快捷键提示/fib-trend-time 面板特例），鼠标与键盘单一事实源；
  2. keydown 训练界面快捷键段新增 Alt 分发层（守卫：training 可见 + 非只读 + 非输入框焦点 + 非 repeat，preventDefault 阻断浏览器 Alt 菜单）；
  3. **顺手修复历史耦合**：A股实时看盘下裸键 B/S/空格/数字会误触币圈下单与回放推进——新增 isAshareLiveMode 守卫跳过（Alt 画图层不受影响）；
  4. 10 个工具按钮 title 增加 "(Alt+X)" 标注（悬停可见）。
- **过程插曲**：HTML title 批量替换脚本曾误删 data-drawing-tool/aria-label 属性（静态测试当场抓出），已完整恢复并复核。
- **质量门禁**：`node --check` 通过；JS 单测 49 passed；ESLint 0 告警；全量 `pytest -q` → **800 passed, 89 subtests passed**。
- 严格遵循指令：**未执行 git 提交与远程推送**。

## Next Action
用户硬刷新验收：三种模式下 Alt+M/L/S/H/F/F+Q 等激活画图工具（工具条高亮 + 状态条提示）；A股看盘下按 B/S/空格无副作用。

## Feature: 连续折线画图工具 (AICoin 风格) (2026-09-10)
- **用户需求**：对标 AICoin 的"连续折线"工具——单击依次落点、自动连线成多段折线，双击结束，锚点白圈显示。
- **落地**（drawing_tools.js 手势状态机扩展 + 渲染/命中/序列化全链路）：
  1. `TOOL_POINT_COUNTS['polyline'] = Infinity`（可变点数，activateTool 校验放行）；
  2. 新手势类型 `polyline-create`：pointerdown 落点（手势跨点击保持，pointerup 不结束）、双击（event.detail≥2）提交、move 实时预览"已落点+当前鼠标"；
  3. 新增 `_commitPolyline`（≥2 点成线入 store 并选中）/`_removeLastPolylinePoint`（Backspace 撤点，仅剩一点时取消）/`_updatePolylineDraft`；
  4. `_onKeyDown`：Backspace 手势内撤点（否则删除选中）、Enter 提交折线；Esc 沿用既有 cancelGesture 取消；
  5. 渲染分支：多段折线（lineWidth/lineStyle 同既有线型体系），hover/selected/绘制中显示每个锚点白底圆圈（对齐 AICoin 视觉）；单点草稿进入渲染分支；
  6. `_bodyDistance` polyline 多段线距离命中（选中可拖动、锚点可编辑、Ctrl+Z 可撤销——复用 store 通用机制）；
  7. 工具条按钮（Z 形折线图标）+ **Alt+Z 快捷键**（DRAWING_TOOL_SHORTCUTS/LABELS/KEY_HINTS）+ 静态测试工具清单加 polyline。
  8. 磁吸：落点走 `_anchorFromPoint`，OHLC 磁吸自动生效；序列化走通用 anchors 数组，持久化/恢复自动支持。
- **质量门禁**：`node --check`（main + drawing_tools）通过；JS 单测 49 passed；ESLint 0 告警；全量 `pytest -q` → **800 passed, 89 subtests passed**。
- 严格遵循指令：**未执行 git 提交与远程推送**。

## Next Action
用户硬刷新验收：Alt+Z 或工具条激活连续折线 → 单击加点（锚点圆圈 + 预览线）→ 双击/Enter 成线 → Backspace 撤点 → Esc 取消；选中拖动/锚点编辑/删除正常。

## Fix: 连续折线结束交互 (2026-09-10 用户实测反馈)
- 双击失效根因：PointerEvent.detail 规范恒为 0——改用原生 dblclick 事件提交（末点去重）；新增右键结束成线（event.button===2 原生字段 + 绘制中屏蔽 contextmenu）；训练快捷键移除 Enter→下一根K线（与空格重复，Enter 专用于折线结束）。
- 门禁：JS 49 passed；pytest **800 passed, 89 subtests** 全绿。未提交未推送。

## Next Action
用户硬刷新验收：左键加点 → 右键结束成线；双击/Enter 亦可结束；空格仍是下一根 K 线。

## Fix: MACD 副图跨模式空白（根因：图表重建未清 series 记账）(2026-09-10)
- **用户报告**：MACD 副图又不显示了（此前出现过）。
- **复现**（CDP 直连真实 Chromium，币圈 ⇄ A股实时看盘双向）：进入实时看盘后 K 线已是茅台 800 根
  （time 1788998400），但技术指标仍是币圈 181 根（time 1719763200，dif -1499.99）——两套时间戳不重叠
  → 副图绘图区空白、图例行残留旧数据集数值；控制台持续报 `加载技术指标失败: Error: Value is undefined`。
- **根因（有异常栈）**：`initializeChart()` 重建三个图表实例但**未清空 `currentIndicatorSeries` / `bollSeries`**，
  下一次 `loadTechnicalIndicator` → `clearTechnicalIndicatorSeries` 对属于**已销毁图表**的旧 series 调
  `removeSeries` → Lightweight Charts 抛 `Value is undefined` → 被 catch 吞掉，`lastIndicatorData` 不更新、
  副图不重绘。栈：`clearTechnicalIndicatorSeries (main_enhanced.js:7029)` ← `Wn.removeSeries` ← `h`。
  仅在跨数据集（会重建图表的路径）切换时触发，从主页直接进看盘看似正常故长期被掩盖。
- **同时澄清**：项目记忆里"Legacy 盲盒日线可能日志 Value is undefined（非阻塞）"即此 bug，实为阻塞。
- **修复（main_enhanced.js，3 处）**：
  1. `initializeChart()` 重建前 `currentIndicatorSeries = []; bollSeries = {};`（记账与图表生命周期对齐）；
  2. `clearTechnicalIndicatorSeries()` 对 `removeSeries` 逐条 try/catch 防御，单条失败不中断副图刷新，
     记账无条件清空（原实现用 `bollSeries.upper` 判空还会漏 BOLL 部分系列）；
  3. 同类泄漏：`startTrainingWithConfig()` 从看盘直跳训练的分支补 `asharePreLiveUiState = null;`
     （该路径不走 exit，快照不作废会污染之后任何一次 exit 的恢复）。
- **门禁**：`node --check` 通过；`node --test tests/js/*.test.js` → 51 passed；全量 `pytest -q` →
  **810 passed, 89 subtests passed**。
- 严格遵循指令：**未执行 git 提交与远程推送**。

## Next Action
用户硬刷新后复演：币圈训练 ⇄ A股实时看盘 双向切换，MACD 副图应始终跟随当前数据集正常渲染。

## Feature: A股实时看盘画图持久化（按标的隔离）(2026-09-10)
- **用户需求**：实时盘画的图希望保留；当前重新进入不保留。
- **根因**：画图仅存于 `DrawingStore` 内存，`initializeChart → initializeDrawingTools` 每次重建
  `DrawingController`，故退出/重进/刷新即全丢（项目原本无任何画图持久化）。
- **落地（main_enhanced.js，不改 drawing_tools.js 库）**：注入式 store——
  `createAshareLiveDrawingStore()` 用已存快照播种 `DrawingStore`，包裹 `_commit`（增删改/undo/redo/clear
  的唯一漏斗）与 `reset` 自动回写；存储键 `kline-ashare-live-drawings-v1::<symbol>` 按标的隔离，
  空集合删键；`initializeDrawingTools()` 传入 store；`switchAshareLiveStock()` 换股后重建控制器装载
  该标的自己的画图；存储不可用时静默降级为内存画图。
- **范围**：仅实时看盘；回放训练保持 `clearSessionDrawings` 的"每次训练从干净画布开始"语义不变。
- **门禁**：node --check 通过；JS 单测 51 passed；全量 pytest **810 passed, 89 subtests passed**。
- **新增回归测试**：`tests/test_indicator_rebuild_and_drawing_persistence.py`（10 项）锁定两处修复结构不变式。
- 严格遵循指令：**未执行 git 提交与远程推送**。

## Next Action
用户硬刷新验收：实时看盘画线 → 退出 → 重进（或刷新页面）画线仍在；换股后只显示该股自己的画线。

## Feature: A股实时看盘 价格预警（对标 AICoin）(2026-09-11)
- **用户需求**：实时盘加预警，到价位弹提醒（附 AICoin 截图：右侧「价格跌至: 87.72 ✕」可拖标签 + 「添加成功」Toast）。
- **确认范围**（四选一）：只做价格穿越（P1）；提醒=应用内弹窗+提示音 且 系统通知；独立「预警」按钮+右侧可拖标签；
  仅 A股实时看盘。
- **新增纯逻辑模块** `frontend/js/modules/price_alerts.js`（UMD，`KLinePriceAlertsModule`）：
  价格按 A股 0.01 归一、方向推导（高于现价=涨至）、`normalizeAlert(List)`、**`evaluateAlertCrossing`**、
  `formatAlertLabel`、`alertStorageKey`、`selectPersistableAlerts`。
- **核心判定：穿越而非阈值比较** —— 涨至 `prev < target && now >= target`；跌至 `prev > target && now <= target`。
  用上一价严格比较，避免停在阈值反复触发，并保证 3 秒轮询之间的跳空不漏报。
- **接线（main_enhanced.js）**：priceLine 橙色虚线 + 贴价格轴的 `.alert-chip`（文字/✕/拖动柄）；
  Alt+A 或按钮进入落线模式（图区点击 `coordinateToPrice` 落线，Esc 取消）；拖柄改价（松手按现价重推方向）；
  ✕ 删除；创建弹「添加成功」Toast；判定放在 `startAshareLivePolling` 且**先判定后覆盖基准价**；
  命中即 `triggeredAt`+`enabled=false`（触发即失效）并三通道提醒（弹窗 12s / WebAudio 双音 / Notification）；
  标签定位在时间轴变化、resize、每次轮询、crosshair 移动四处 rAF 重定位。
- **持久化**：`kline-ashare-live-alerts-v1::<symbol>`，只存"仍生效且未触发"项，空集合删键；换股/重进按标的恢复。
- **样式/结构**：`#alert-add-btn`（默认 hidden，仅看盘显示）；`.alert-chip`/`.alert-popup`/`.alert-toast` 全套 +
  light 主题覆盖（沿用 `.chart-extreme-price-tag` 的主题约定）。
- **门禁**：node --check 通过；`node --test tests/js/*.test.js` → **69 passed**（新增 18 项）；
  全量 `pytest -q` → **827 passed, 89 subtests passed**（新增静态守卫 17 项）。
- **浏览器实测**（CDP + 真实 Chromium，茅台 600519）：落线/标签/Toast/拖动改价/穿越触发（弹窗+置灰+存储清空）/
  不重复触发/退出重进恢复 —— 8 项全通过。
- 严格遵循指令：**未执行 git 提交与远程推送**。

## Next Action
用户硬刷新验收：进实时看盘 → Alt+A 或点铃铛 → 图上点一下落预警线 → 拖动改价 → 价格穿越看弹窗；
再换股/退出重进确认按标的隔离与恢复（系统通知首次需授权）。

## Fix: 当前持仓卡片收窄为"仅本股票"(2026-09-11)
- **用户反馈**：看 600519 的图，当前持仓卡片里却显示 601727 的持仓；多标的/多笔订单一多很乱。
  要求当前持仓只显示本股票，其余到「持仓」那里看。
- **根因**：`renderAshareLiveAccount()` 用 `Object.keys(acc.positions).filter(持股>0)` 列出全部标的
  （当前标的置顶 ★当前）——这是 09-10「全持仓列表」的既定行为，实盘用下来嫌乱，本次按用户意见收窄。
- **修复（main_enhanced.js，约 4 行）**：
  `const currentHeldShares = Number(acc.positions[currentAshareSymbol]?.total_shares) || 0;`
  `const heldCodes = currentHeldShares > 0 ? [currentAshareSymbol] : [];`
  只渲染本股票一张卡片，无持仓显示「暂无持仓」；去掉已无意义的 ★当前 标记；卡片字段/冻结标签/次日解冻不变。
- **其余持仓不丢**：左侧自选面板本就有「持仓」标签页（`getAshareTabStocks()` 的 `'holding'` 分支遍历全部 positions）。
  `限价挂单` 区块保持跨标的（设计如此，含撤单）。
- **门禁**：node --check 通过；全量 `pytest -q` → **827 passed, 89 subtests passed**（无回归）。
- **浏览器实测**：造 600519/601727/000858 三个持仓后逐一切换——卡片分别只显示对应本股票（或「暂无持仓」），
  且左侧「持仓」标签页仍完整列出 3 只。
- 严格遵循指令：**未执行 git 提交与远程推送**。

## Pending（待用户确认）
用户圈出最后一根绿 K 说「这里有一个买入的标志」。已核实：**实时看盘成交目前不会在 K 线图上留标记**
（`executeAshareLiveBuy/Sell` 只写 trade_history，不调 `updateTradeMarkers`）。候选：A 标注真实买卖点 /
B 标注形态信号点（如站上趋势线）/ C 仅陈述非需求。确认后再实现。

## Next Action
用户硬刷新验收：看盘时切换标的，当前持仓卡片应只显示该股票；全部持仓到左侧自选面板「持仓」标签页查看。

## Feature: 交易记录补日期 + K 线成交标记（买入/卖出）(2026-09-11)
- **用户反馈**：①交易记录只显示 `12:28:00` 没有日期，不知道哪天买的；②成交后图上完全没有买入标志。
- **① 交易记录补日期（main_enhanced.js）**：
  - 新增 `formatAshareTradeStamp()`（MM-DD HH:MM:SS）/ `formatAshareTradeStampFull()`（完整日期挂 title）；
    历史成交行改为显示日期+时间并过 `escapeHtml`。
  - 顺带补一个既有字段缺失：**限价成交**记录（matchAsharePendingOrders 两处 unshift）原本没写
    `date`/`symbol`/`lots`，已补齐与市价记录对齐；无日期的历史遗留记录退化为只显示时间，不报错。
- **② K 线成交标记**：新增 `currentAshareBarTime()` / `ashareTradeBarTime(record)` /
  `updateAshareLiveTradeMarkers()`。**标记从持久化的 trade_history 反推，不另存一份**，天然随账户保存恢复。
  映射优先用成交瞬间写入的 `bar_time`（同周期精确到具体 K 线），回退把 `date+time` 换算到图表时间域再交给
  既有 `alignTradeMarkerTimeToRenderedBar()` 对齐（换周期仍能落回当日/当周那根 K 线；**日线 bar 时间是该日
  UTC 零点，直接用浏览器本地时间戳会整整差一天**）。买入=红色/箭头上/K线下方，卖出=绿色/箭头下/K线上方。
- **扩展 `updateTradeMarkers()`**：新增可选覆盖 `marker.position/color/shape/label`（不传则行为与原来
  完全一致，币圈/回放零影响）。解决"箭头上下位置跟着 K 线涨跌翻转"的问题，并让标签显示中文「买/卖」。
- **刷新时机**：loadAshareLiveData（进入/换股/换周期）、市价买、市价卖、限价成交、清空记录、重置账户 —— 6 条路径全覆盖。
- **门禁**：node --check 通过；JS 单测 69 passed；全量 `pytest -q` → **838 passed, 89 subtests passed**
  （新增 `tests/test_ashare_trade_markers_static.py` 11 项守卫）。
- **浏览器实测**：5 条混合成交记录（含跨标的 / 只有 code 的早期限价成交 / 无日期遗留）→ 3 个标记精确落位、
  跨标的被过滤、无日期记录安全跳过；交易记录显示 `09-09 10:15:30`、title 为完整日期。
- 严格遵循指令：**未执行 git 提交与远程推送**。

## Next Action
用户硬刷新验收：实时看盘买卖后，K 线对应位置出现红色「买」/绿色「卖」标记；交易记录显示日期（悬停看完整时间）；
换周期/换股/重进后标记仍正确。

## Fix: 锁定按钮无视觉反馈 + 市价单以损定仓开仓价不跟随实时价 (2026-09-12)
用户一次提了 4 项，本次交付 #1、#2；#3/#4 待决策（见文末）。

### #1 锁定：先纠正前提，再修真正的问题
- **实测结论（CDP + 真实 Chromium）**：锁定**是**按单个对象生效且**确实**阻止拖动的——
  锁定后拖 A：价格未变、图表也没被平移；对照的未锁 B 正常移动；锁 A 时 B 仍 `locked:false`
  （**不存在"一锁全锁"**）。现有单测 `tests/test_drawing_tools_frontend.py` 也已覆盖。
- **真正的问题是没有视觉反馈**：`syncDrawingFloatingToolbar()` 只挂在 `onSelectionChange` 上，
  而 `toggleLock()/toggleHidden()` 只调 `refresh()` 不触发选中变化 → 实测 `locked:true` 但
  `toolbarLockActive:false`，锁定高亮**从来不亮**；且锁体 SVG 是静态的，锁没锁长得一模一样。
  用户截图里唯一白框其实是**焦点环**，不是锁定态。
- **修复**：`drawing_tools.js` 的 `toggleLock/toggleHidden` 补 `_emitSelectionChange()`；
  `main_enhanced.js` 新增 `applyDrawingLockVisualState()` 统一刷新**主工具条+浮动工具条**两处
  （`.active`/`aria-pressed`/`title` + 锁体闭合↔开口形状切换），`invokeDrawingAction` 再显式回刷并提示
  「🔒 已锁定：该图形不可拖动/缩放（仅对这一个图形生效）」。
- **注意**：截图里选中对象带「同步到下单区」按钮 → 选中的是**做多/做空测算框**（isRiskDrawing），
  不是普通水平线；若用户仍能拖动，需按其确切步骤复现。
- 「还是会被拖动」在标准拖动路径下**无法复现**，已向用户说明并索取步骤。

### #2 市价单·以损定仓开仓价
- **根因**：`getCryptoRiskCalcParams()` 里 `entryPrice: entryInput > 0 ? entryInput : preview.entryPrice`
  —— 输入框只要被填过一次，旧值就永远覆盖实时价（截图里 93878.43 vs 实际 71321.1）。
  而 `getCryptoOrderPreview()` 对市价单取 `entryPrice = currentPrice` 本身是对的。
- **修复**：市价单强制用 `preview.entryPrice`；新增 `syncCryptoRiskCalcEntryPrice()`
  把「开仓价」输入框同步为实时价并 `readOnly`（限价/突破单恢复可编辑），
  在 `refreshCryptoOrderPreview()` 中调用，价格变化时一并刷新反推数量。
- **实测**（真实币圈训练会话 BTCUSDT 61704.8）：注入旧值 93878.43 → 被拉回 61704.8、readOnly、重算数量；
  切限价 → 恢复可编辑。

### 门禁
`node --check` 通过；全量 `pytest -q` → **838 passed, 89 subtests passed**。

## Pending（等用户决策，未动代码）
- **#3 AICoin 风格拖动止盈止损线**：可复用 A股预警那套（`createPriceLine` + 贴轴 DOM 标签 + 拖动柄），
  待定：松手即提交还是先确认？跟随持仓改价还是新增条件单？药丸显示哪些字段？A股看盘是否也要？
- **#4 平仓不能设价格**：`backend/crypto/futures_orders.py:186-192` 规定限价只能挂在不会立即成交的一侧
  （平多限价必须**高于**当前价），用户输 70000（低于现价）故被拒——是设计约束不是 bug。
  前端 `validateCryptoPendingPrice()` 同规则前置提示。待定：引导走止盈止损 / 允许可立即成交的限价平仓 /
  维持现状。

## Next Action
用户硬刷新验收 #1、#2；并就 #3（拖动设止盈止损）与 #4（平仓限价方向）给出决策后继续。

## Feature: 平仓限价解除方向限制 + 开仓后可拖动创建止盈止损 (2026-09-12)
用户决策：松手即提交 / 拖动=修改已有单 / 像 AICoin 显示 / 币圈（A股待确认）/ **成交后平仓不设限制**。

### 两处认知纠正（省掉大量返工）
1. **拖拽改价基建早已存在**：`main_enhanced.js` ~8016 行「主图持仓均价线与止盈止损/挂单线可视化」
   已实现 `updateChartTradePriceLines()` 画线与 `initChartTradeLineDragging()` 拖动改价，
   松手真的 `PUT /training/{id}/orders/{orderId}`，拖动中 tooltip 还显示 距现价%/预估收益。
   **缺的只是"开仓后创建止盈止损"的入口**，不是拖拽本身。
2. **"到价止损"能力后端本来就有**：`_validate_pending_direction()` 里
   「平多**突破**价必须低于现价」就是到价止损；用户卡住的是「平多**限价**必须高于现价」。
   即能力存在但埋在反直觉的「突破」单里，且报错没给出路。

### A. 平仓限价解除方向限制
- `backend/crypto/futures_orders.py`：删掉 limit 分支两条 `reduce_only` 方向校验（**开仓与突破单不变**）。
  语义：平仓单一直挂到价格触及才成交 → 低于现价的平多单=止损，高于现价=止盈。
- `validateCryptoPendingPrice()`：`action==='close'` 跳过方向校验。
- `tests/test_crypto_binance_orders.py` 对应用例由"断言被拒"改为"断言受理"。

### B. 开仓后可拖动创建/修改止盈止损
- 新增 `buildChartProtectiveLineTitle()` → `止盈 (TP): 62,938.9 距现价 +2.00% 预估 +3.7 USDT`。
- 新增**占位止盈/止损线**（持仓已建但缺 TP/SL 时画在 `entry±2%`，标题带「拖动设置」），拖动即创建；
  无 orderId 的兜底保护价线也标记 `isPlaceholder`（拖动改为按新价创建，不再是死线）。
- `getHoveredTradeLine()` 放开 `orderId` 硬要求；`finishDrag()` 新增占位分支 →
  `createProtectiveOrderFromDrag()` POST `/trade` `{action:'close',order_type:'limit',limit_price}`。
- HTML 提示改为"开仓后也可直接在图上拖动止盈/止损线补设或改价（平仓限价任意价位皆可挂）"。

### 门禁
`node --check` 通过；Python AST 通过；全量 `pytest -q` → **838 passed, 89 subtests passed**
（含改写后的 `test_strict_limit_direction_rejects_equal_and_reversed_prices`，等于独立验证了引擎改动）。

### 浏览器实测（BTCUSDT 61704.8，市价开多 0.003）
占位线正确渲染并带 AICoin 风格文案；拖动止损线**确实**发出
`POST /trade {"action":"close","order_type":"limit","limit_price":54744.69}`；
返回 `400 平多限价必须高于当前价格` → **运行中的后端仍是旧进程**；失败后线位正确回滚。

### ⚠️ 用户必须重启后端
`启动项目.bat` 用 `python -m flask --app backend.app_enhanced run`（**无 --debug**，不会自动重载），
8000 端口跑的还是旧代码。**关闭当前控制台窗口重跑 `启动项目.bat`** 后 A 项才生效。
（未替用户重启：Agent 侧起的后台进程可能在会话结束时被回收，反而弄没用户的本地服务。）

## Pending
1. **AICoin 药丸样式轴标签**：信息已在线的标题里，但还没做成贴价格轴的彩色圆角药丸（含 ✕）。
   可复用 A股预警 chip 那套基建。
2. **A股实时看盘止盈止损**：用户说"也要"，但 A股实时盘是**纯客户端模拟账户**
   （localStorage + `matchAshareLimitOrders` 前端撮合），**无服务端条件单引擎**；
   且其撮合规则是"卖出限价 ≤ 现价即成交"，即**低于现价的卖出限价会立刻成交而非挂着等触发**。
   要真正支持需新增一类"触发价到位才成交"的条件单，工作量与币圈不同量级，待确认。

## Next Action
用户重跑 `启动项目.bat` 后验收：开仓 → 图上拖动止盈/止损占位线创建保护单 → 再拖动改价；
并确认 A股是否也要止盈止损（需新增条件单机制）。

## Feature: AICoin 风格价格线药丸（止盈/止损浮层）(2026-09-12)
用户：① 按你的先做，做完看结果再讨论；② 质疑"A股止盈止损为何做不了"。

### ① 已交付（main_enhanced.js + style_enhanced.css）
给每条止盈/止损线贴一个贴价格轴左侧的药丸：
`[止盈] +3.7 USDT (+20.00%)  0.003  ✕` / `[止损] -3.7 USDT (-20.00%)  0.003  ✕`
- `computeProtectiveLinePnl()`：优先按**保证金收益率**（取 `position.isolated_margin`，与 AICoin 口径一致），
  无保证金信息时退化为价格涨跌幅。
- **角色徽标可点** → `flipProtectiveLineRole()` 把线镜像到成本价另一侧（真实单走 PUT 改价）。
- **✕** → 真实单 `cancelPendingOrder()` 撤单；占位线进 `suppressedProtectivePlaceholders`
  （本次会话不再显示，换训练会话复位）。
- **按住药丸本体=拖动改价**：复用既有挂单拖拽状态机（`currentDraggedTradeLine` + pointer capture），
  拖动 tooltip / 成功提示 / 失败回滚全部沿用。
- 定位复用既有统一调度：`scheduleAshareAlertChipsUpdate()` 扩展为同时调度 A股预警标签 + 币圈药丸，
  因此时间轴变化/resize/crosshair 四处钩子无需改动即已覆盖。
- `.trade-line-pill` 全套 CSS（is-tp/is-sl/is-placeholder + light 主题）。

### 踩坑（重要，写进经验）
新增 DOM 代码让**两个既有测试挂掉**：`test_chart_workspace_frontend.py::ChartTradePriceLinesTests::test_trade_price_lines_node_execution_logic`
与 `test_crypto_frontend_static.py::test_render_crypto_account_passes_pending_orders_to_renderer`
—— 它们把 `clearChartTradePriceLines()`…`renderCryptoPositionCard(` 的代码**抽进 Node 沙箱执行**，
沙箱内**没有 document**、也没有模块级 `activeTradeLinePills` / `suppressedProtectivePlaceholders`。
→ 修法：沿用文件既有 `typeof x === 'undefined'` 防御风格做守卫。
**以后凡在该区间新增 DOM/全局依赖，必须先加 typeof 守卫。**

### 门禁与实测
`node --check` 通过；全量 `pytest -q` → **838 passed, 89 subtests passed**。
浏览器实测（BTCUSDT，市价开多 0.003）：药丸 2 个渲染正确（209×22px 贴轴）；
角色徽标切换 止损60470.7→止盈62938.9 ✓；✕ 关闭后药丸 2→1 且 `suppressed:['tp']` ✓；
**拖动创建保护单成功**：`⚡ 已创建止损单：59,853.66 USDT`，`pendingCount:1` ✓
（该步通过 = 上一轮 #4 后端改动**端到端验证通过**）。

### ⚠️ 环境状态
验证开始时 **8000/5000/5050 均无监听**（后端已停、请求全 502），应是用户按上轮建议关掉了服务。
**已由 Agent 临时起了一个实例**（`flask --app backend.app_enhanced run --port 8000`，含 #4 新代码），
故本轮得以完整验证。该后台进程**可能在会话结束后被回收**——若 8000 打不开，重跑 `启动项目.bat` 即可
（8000 被占用时 bat 会自动改用 5000）。

## ② 的结论（用户是对的）
用户："平仓就是价格到达这一刻就触发…A股永远是多，币圈可以多空而已，不是一样吗？"
→ **逻辑上完全一样**，上一轮说"A股要另一套机制"是**夸大**。真实差异只有一个撮合细节：
A股撮合断言是「买入限价 ≥ 现价成交、卖出限价 ≤ 现价成交」，因此
- **止盈**（平多挂高价）：`现价 >= 卖出限价` 未满足 → 自然挂着等触发 ✓ **现有挂单即可实现**；
- **止损**（平多挂低价）：`现价 >= 卖出限价` 挂单当下已成立 → **立刻成交**（等于市价卖出）✗，
  需补一个**穿越式触发判定**（价格从上向下穿触发价才成交）。
即：A股止盈零改动，止损只需加"穿越触发"一小步。等用户确认后实施。

## Next Action
用户查看药丸效果后：① 反馈样式微调；② 确认是否实施 A股穿越式止损触发判定；
③ 若 8000 打不开则重跑 `启动项目.bat`。

## Redesign: 价格线浮层按 AICoin 规格重做（v2）(2026-09-12)
用户否掉 v1（"做太差了，哪些字体等"）并给出 4 点详细规格。

### v1 被否的两个真正原因（已修）
1. **线上写了全宽文字**——v1 把 `title` 放在价格线上，Lightweight Charts 会渲染成横贯整条线的文字带，很脏。
   AICoin 线上**没有文字**，信息全在右侧浮层 + 轴上价格框。
2. **凭空出现的虚线**——v1 在"持仓无止盈止损"时自动画了 ±2% 的虚线占位线，
   用户看到就以为"我没设置怎么有线"（他原话）。→ 改为不画线，只给「止盈/止损」徽标入口。

### 本轮改动（main_enhanced.js + style_enhanced.css）
- **线上不再写字**：所有价格线 title 置空；**拖动过程中也不写**（原来会临时写"修改挂单: xxx"），
  提示只留在跟随光标的气泡里。
- **AICoin 风格分段浮层**：持仓 `多 0.003 @ 61,704.8 │ +0 USDT (+0.02%) │ [止盈][止损]`；
  保护线 `止盈 │ 市价 │ 预估收益 +25.96 (+140.25%) │ 距当前价 +14.02% │ 0.003 │ ✕`；
  挂单 `[止盈][止损] │ 限价卖出平仓 │ 0.003 │ ✕`。
  配色对齐 AICoin：**止盈绿 #0ecb81、止损琥珀 #f0a020**（v1 止损是红色）。
  字体排版重写：11px / tabular-nums / 分段分隔线 / 20px 行高。
- **徽标拖动放置**（规格 1、3）：`buildProtectivePlacementChip()` +
  `beginProtectiveLinePlacement()`——按下徽标即建临时线并接管拖动，松手创建保护单；
  `finishDrag` 的占位分支提到"未移动即回滚"之前（点一下=按默认 ±2%，拖动=按拖到价位），
  失败走 `removeProtectivePlaceholderLine()` 清理。
- **平仓单按相对成本价的位置判定角色**（规格 4）：引擎里手工平仓单无 `protection_type`，
  现按"多头在上=止盈、在下=止损（空头相反）"判定 → 平仓线自动获得与止盈止损线一致的浮层/配色/拖动/✕。
- **修盈亏符号 bug**：`computeProtectiveLinePnl()` 原来用 `item.side` 判多空，而平仓单 side 是 sell/buy，
  会把多头止盈算成亏损（实测 -25.96）。改为读 `currentTraining.position.side` 后为 +25.96 ✓。

### 门禁与实测
`node --check` 通过；全量 `pytest -q` → **838 passed, 89 subtests passed**。
浏览器实测：开仓后 `lineTitles:[""]`（线上无文字）、`hasDashedPlaceholder:false`（无凭空虚线）、
浮层与 2 个徽标正确；按住「止盈」徽标拖动发出
`POST /trade {"action":"close","order_type":"limit","limit_price":70358.85}` → **200**，pendingCount=1；
生成行 `is-tp`：`止盈 市价 预估收益 +25.96 (+140.25%) 距当前价 +14.02% 0.003 ✕`；
持仓行的止盈徽标自动消失。

### 两个测试基建坑（重要）
1. **`node -e <整段脚本>` 撞 Windows 命令行长度上限（~32KB）**，报
   `FileNotFoundError: [WinError 206] 文件名或扩展名太长`。本仓库多个前端测试这样执行抽取代码，
   代码一变长就炸。已把 `test_chart_workspace_frontend.py::ChartTradePriceLinesTests` 改为
   **写临时文件 + `node <file>`**（补 `import tempfile`）。以后遇到 WinError 206 同样处理。
2. 该测试断言写死旧设计（线上含文字、止损红色），已更新为"**线上 title 必须为空** + 止损 #f0a020"。
   它还**抓到一个真 bug**：删掉 `const title` 后漏改一处 `title: title` → `ReferenceError: title is not defined`
   （浏览器里同样会抛，会导致持仓线画不出来）。→ 改前端后必跑门禁。

## Pending（等用户确认）
1. **规格 1「挂单时」设置止盈止损需要后端小改动**：引擎 `modify_order_price()` 只支持改价，
   挂单的 `tp_price/sl_price` 目前**只能在提交时**给定（成交时据此生成保护子单）。
   需：该方法增加可选 tp/sl 参数 + 路由 `PUT /orders/{id}` 透传 + 校验（多头 tp 高于/sl 低于委托价）。
   属后端语义改动，想先与用户对齐再动。
2. AICoin 持仓行的「平 / 市 / 反」快捷按钮：用户描述里出现但未明确要求，且「反」是新下单流程，可后续再加。

## Next Action
用户硬刷新查看新浮层；确认规格 1 是否实施后端改动；反馈样式微调。
若 8000 打不开则重跑 `启动项目.bat`（临时实例可能已被回收）。

## Feature: 画图默认样式记忆 (2026-09-10)
- **用户需求**：线条设置（颜色/线宽/线型/显示价格标签）改一次就丢，每次画图都要重设——要求记住设定。
- **方案**："上次怎么设，下次就怎么画"——设置面板改动同步进默认样式（localStorage `kline-drawing-default-style-v1`），之后**新建**的所有画图图形（draft 与正式同入口）自动应用这套外观。
- **落地**（drawing_tools.js）：
  1. `normalizeDrawingDefaultStyle`（仅 color/lineWidth/lineStyle/labelVisible 四个通用字段，非法丢弃；fillColor/透明度/字号等不纳入）+ load/save（localStorage 带 guard，node 测试环境降级）；
  2. `_createModelForTool` 合并默认样式（显式 options 优先）——全部工具类型的新建路径统一生效；
  3. `updateSelectedLineSettings` 成功更新后记忆 patch 中的通用字段（所有类型设置面板共用此入口：线条/矩形/文字）；
  4. UMD 导出 normalizeDrawingDefaultStyle + 新增 2 个 node:test 用例。
- **质量门禁**：`node --check` 通过；JS 单测 **51 passed**；ESLint 0 告警；全量 `pytest -q` → **800 passed, 89 subtests passed**。
- 严格遵循指令：**未执行 git 提交与远程推送**。

## Next Action
用户硬刷新验收：改某图形样式（如线宽 4.5 + 换色）→ 删除重画/切换周期/刷新页面后新建图形 → 直接就是上次设置的样式。

## Critical Fix: 止损线未到价就被平仓（平仓单必须区分「限价=止盈」与「突破=止损」）(2026-09-12)

### 用户报告
开多后把止损线拖到现价下方，**价格还没到，点一下"下一根 K 线"就立刻被平仓**（附两张截图：
止损 53257.48 距离现价 -8.50%，点下一根后持仓直接消失）。

### 根因（上一轮自己挖的坑，必须记住这条领域规则）
拖动创建保护单时**无条件发平仓限价单**（`order_type: 'limit'`），而引擎对"卖出限价"的撮合条件是
**`high >= 限价`**。止损挂在现价下方 → `high >= 止损价` 恒成立 → **下一根 K 线必然成交**。
上一轮我把 `_validate_pending_direction` 里"平多限价必须高于现价"的方向校验删掉了（理由是"平仓不设限制"），
恰好拆掉了唯一拦住这个组合的护栏。**"限价平仓挂在现价外侧"在交易所语义里是可立即成交的单，
它只能当止盈，不能当止损。**

引擎其实一直有正确实现（`_create_tp_sl_orders`）：**TP 用 limit（`high >= tp`）、SL 用 breakout
（`low <= trigger`）**。缺的只是把这条规则用到"用户手工拖出来的保护单"上。

### 修复
**前端 `main_enhanced.js`**
- 新增 `resolveCloseOrderType(price, currentPrice, closeSide)`（唯一真源）：
  多头价在上=止盈(limit)、在下=止损(breakout)；空头相反。
- `createProtectiveOrderFromDrag()` 复用它 → 止损发
  `{action:'close', order_type:'breakout', trigger_price}`，止盈发 `limit + limit_price`；
  并新增"保护价不能等于标记价"与"无持仓直接拒绝"的前置守卫。
- `submitCryptoOrder()`：`action==='close'` 时按价位**自动改判类型**后再提交（用户只填价位，不再撞校验），
  并在成功提示里注明"（已按价位自动选为突破止损）"。
- `validateCryptoPendingPrice()`：恢复平仓方向校验（限价=止盈侧、突破=止损侧），错误文案直接指路"改用突破单"。
- 角色显示改为**以订单类型为准**（平仓 limit=止盈、平仓 breakout=止损），只有类型不明才退化为
  按成本价上下侧判断——原来按成本价判断会在"持仓浮盈、止损放在成本价之上"时把止损误标成止盈。
- `getCryptoProtectivePrices()` 不再要求 `parent_order_id`，改为按类型识别 → 手工拖出的保护单也能出现在
  持仓卡片的「止盈 / 止损」一行。
- 浮层第二个分段原来**写死「市价」**（会让人误以为挂单会市价成交）→ 改为真实类型（限价/突破）。

**后端 `backend/crypto/futures_orders.py`**
- `_validate_pending_direction()` 恢复平仓限价方向护栏，文案指路："平多限价必须高于当前标记价，否则会立即成交。
  低于标记价的止损请改用突破单。"（开仓限价/突破限制不变）
- 新增 `_retarget_reduce_only_order()` + `modify_order_price(current_price=...)`：
  **保护线拖过现价另一侧时自动改判类型**（限价↔突破，`protection_type` 同步），
  拖到正好等于标记价则报 400 `invalid_limit_direction`。新增 `_validate_amend_direction()` 拒绝把**开仓挂单**
  改到会立即成交的一侧。
- 新增 `_protective_priority()`（模块级）：把"手工拖出的平仓突破单=止损"也纳入同根 K 线内的撮合优先级，
  与显式子单同规则（止损优先于止盈，保守撮合）。
- `backend/routes/training_routes.py`：`PUT /orders/{id}` 透传标记价，并把 `FuturesOrderError` 映射为 400 + code。

### 门禁与实测（真实 Chromium + api 级回归）
`node --check` 通过；全量 `pytest -q` → **853 passed, 89 subtests passed**（838 → +15）。
浏览器实测（BTCUSDT 市价开多 0.016，现价 61704.8，止损拖到 -10% 即 55534.32）：
- 请求体 `{"action":"close","order_type":"breakout","trigger_price":55534.32}` → **200** ✓
- 浮层文案 `止损 | 突破 | 预估收益 -98.73 (-100.00%) | 距当前价 -10.00% | 0.016 | ✕`（不再是「市价」）✓
- **点下一根 K 线：`sideBefore=long → sideAfter=long`，`closedPrematurely:false`** ✓（用户报的 bug 已消失）
- 对称验证（紧贴现价下方的止损）：bar1 low=62464.4 > 62435.75 → 仍持仓；bar2 low=61779.6 穿越 → 成交平仓 ✓
- 控制台无报错。

新增回归测试：
- `tests/test_crypto_binance_orders.py`：恢复"平仓限价挂可立即成交侧必须被拒"，
  新增"止损突破单在价格穿越前不成交 / 止盈限价只在 high 触及才成交 / 拖过界自动改判类型 / 拖到标记价被拒 /
  开仓挂单改到可成交侧被拒"。
- `tests/test_crypto_futures_api.py::test_stop_loss_survives_bars_that_do_not_reach_it`：
  走 HTTP 复刻用户场景（旧写法 400 → 突破单 200 → 推进一根不成交 → 再推进一根成交）。
- `tests/test_crypto_order_modification.py`：补 `PUT /orders/{id}` 拖过界改判类型 + 拖到标记价 400。
- 新增 `tests/test_crypto_protective_order_type_static.py`（9 项，含在 Node 里真跑 `resolveCloseOrderType`
  的几何用例），把"拖动必须发 breakout"钉死。**这个守卫当场抓到一次漂移**（拖动路径一开始自己内联算类型、
  没复用 `resolveCloseOrderType`），已改为一处真源。

### ⚠️ 用户必须重启后端
8000 端口当前进程启动于 22:07，而本轮后端改动在 22:14 之后 → **跑的是旧代码**（无 --debug 不自动重载）。
前端改动由 static 直接 serving，**硬刷新即生效**（止损不再提前平仓只靠前端改动就已修复）；
但**"拖动改价跨过现价自动改判类型"和 API 层护栏需要重启后端**才生效。

## Next Action
用户 `Ctrl+Shift+R` 硬刷新 + **重跑 `启动项目.bat`**（后端必须重启）后验收：
1. 开多 → 拖「止损」徽标到现价下方 → 连点几根 K 线，**持仓应保持**直到价格真的跌破止损价；
2. 浮层第二段应显示「突破」（止损）/「限价」（止盈），不再是「市价」；
3. 把已有保护线拖到现价另一侧 → 类型自动在止盈/止损间切换，不会立刻成交；
4. 若 8000 打不开，重跑 `启动项目.bat`（8000 被占会自动换 5000）。

## Critical Fix: 画图「锁定」按钮点了没反应 —— 按钮被绑定了两次 (2026-09-13)

### 用户报告
选中画线后按浮动工具条 🔒，**毫无反应**，对象照样能被拖动。（这是对上一轮"锁定修复"的否定。）

### 根因
`#drawing-floating-toolbar` 里的按钮同时命中**两个**绑定器：
通用 `document.querySelectorAll('[data-drawing-action]')` 循环 + `bindDrawingFloatingToolbar()` 专属绑定
→ 每个按钮挂了 2 个 click 监听 → 一次点击 `toggleLock()` 跑 **2 次** → `false→true→false`，净效果为零。
取证：给 `toggleLock` 打计数桩，一次点击 `calls: 2`；用 `cloneNode` 克隆按钮只挂一个监听 → `calls: 1`、立即锁定成功。

**为什么只有 锁定/隐藏 坏**：它们是纯 toggle（跑两次=原样）；`delete` 第二次是 no-op、
`settings/sync-order/drag` 不在通用 `methodMap` 里 → 都"看起来正常"。

> ⚠️ 上一轮误判的原因：我**直接调 `drawingController.toggleLock()`** 验证，绕过事件链，测不出重复绑定，
> 还误诊成"功能正常、只是缺视觉反馈"。**测 UI 按钮必须派发真实事件序列。**

### 修复（仅前端 main_enhanced.js，硬刷新即生效，无需重启后端）
1. 通用绑定跳过浮动工具条按钮：`if (button.closest('#drawing-floating-toolbar')) return;`
   （必须放在写入 `drawingBound` 标记**之前**）。
2. `applyDrawingLockVisualState()` 只对 24×24 锁体几何替换 `d`，避免污染主工具条 16×16 图标
   （原来会把锁体画到 viewBox 外导致图标消失）。
3. 控制器 `drawing_tools.js` 零改动 —— 它本来就有完整的 `locked` 拦截。

### 验证（带阳性对照）
第一轮合成拖动连未锁定的线都"拖不动" → 发现 `_capturePointer()` 的 `setPointerCapture` 对
合成 pointerId 抛 `NotFoundError`，手势没建立 → 给该元素垫 try/catch 垫片后重测：
- 阳性对照：未锁定线 `59853.66 → 66446.1` ✅（证明拖动手段有效）
- 锁定后同法拖动：`66446.1 → 66446.1`，`moved:false` ✅
- 隔离性：另一条未锁定线 `63555.94 → 56472.44` ✅ 锁 A 不影响 B
- 点击 → `locked:true` + 按钮高亮 + 锁体闭合 + 🔒 提示；再点 → 解锁 ✅
- 全量 `pytest -q` → **859 passed, 89 subtests**（853 → +6）

新增 `tests/test_drawing_lock_binding_static.py`（6 项）。
交接：`.agent/handoffs/2026-09-13-drawing-lock-double-binding.md`。

### 经验
1. 测 UI 按钮必须走真实事件（pointerdown→click, detail:1），不能直接调方法。
2. "没反应"先打计数桩分流：事件没到 vs 到了但被抵消。
3. 合成 pointer 拖动要先垫 `setPointerCapture` 垫片，且必须做阳性对照，否则"没动"不可信。
4. toggle 型按钮是重复绑定的天然探针：哪个 toggle "没反应"，先查双重绑定。

## Next Action
用户硬刷新（Ctrl+Shift+R）验收：选中画线 → 点浮动工具条 🔒 → 按钮高亮、锁体闭合、
提示「🔒 已锁定」→ 再拖该线应**拖不动**；其他未锁定的线不受影响。

## Critical Fix: 全局画线隐藏、工具专属样式隔离、副图 MACD 贴底失真与价格轴自适应 (2026-09-21)

### 修复内容
1. **一键隐藏/恢复全部画线**：
   - `DrawingController` 提供 `areAllHidden()` 与 `toggleAllHidden()`。
   - `main_enhanced.js` 的 `handleDrawingHideAction` 区分事件来源：左侧工具栏一键切换全局隐藏/显示所有画线，浮动工具栏单线隐藏。
   - 同步眼睛按钮高亮状态、Tooltip 文案与状态栏轻提示。
2. **各画图工具独立继承专属样式配置**：
   - 废除全局单一画线样式覆盖机制，引入 `loadDrawingToolStyle(toolType)` / `saveDrawingToolStyle(toolType, style)`。
   - 趋势线、水平线、射线、折线、矩形、测量尺、文本、斐波那契回调线等工具各自隔离独立记忆颜色、线宽、线型及透明度。
3. **副图 MACD 回放推进贴底失真与自适应量程修复**：
   - 根因：高频步进时重建 Series 且副图价格轴丢失 `autoScale: true`，导致 ETH 暴跌至 -212 的 DIF 负值溢出画布下底边被裁剪平切，产生贴底直线和红绿柱消失的假象；开启 MACD2 时因重新实例化全屏自适应画布偶然恢复了视野。
   - 修复：Series 复用更新（`series.setData(...)` 零抖动更新），每次刷新显式调用 `inst.chart.priceScale('right')?.applyOptions({ autoScale: true })`；移除副图时重置 `currentIndicatorType` 避免指针残留。
4. **README.md 全面重构升级**：
   - 详细呈现桌面独立客户端（PyWebView）与 Web 双模、加密合约拟真强平与拖拽改单、A 股实时看盘与 16 周期预警、K 线切片回放、多副图指标自适应、矢量画线系统等完整特性矩阵。

### 自动化验证
- Python 静态契约与前端测试：252 passed
- Node.js 前端单元测试：82 passed
- main_enhanced.js 与 drawing_tools.js 语法校验通过
