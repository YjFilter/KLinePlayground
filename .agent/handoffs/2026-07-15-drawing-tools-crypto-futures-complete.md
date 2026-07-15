# Drawing Tools and Crypto Futures Complete

## Completed
- TradingView-style Fibonacci, ruler, long-position, and short-position drawing tools with editing/history controls.
- Binance-first and Bybit-fallback USDT perpetual instrument/data layer with persistent monthly trade, mark, funding, and instrument caches.
- Canonical 5-minute replay with 5m/15m/30m/1h/4h/daily/weekly views and no future leakage.
- Isolated-margin long/short simulator with 1-20x leverage, market/limit orders, funding, mark-price liquidation, reversals, cancellation, persistence, reports, and restart recovery.
- Full Flask and frontend integration for setup, search, trading, account/position state, markers, reports, and completed-history charts.
- Active futures sessions now checkpoint their full training/runtime metadata and automatically restore replay time, position, pending orders, IDs, and funding progress on the first API request after Flask restart.
- Bybit funding history uses backward endTime pagination rather than unsupported cursor pagination, so ranges above 200 events remain complete.

## Acceptance
- Real Bybit BTCUSDT: 30-day cached bundle loaded in 3.64s; training start completed in 5.42s; next 5-minute bar completed in 1.25s.
- Real Bybit ETHUSDT: 288 trade bars, 288 mark bars, and 3 funding events downloaded for January 1, 2025.
- Browser: all seven periods, market open/close, limit order/cancel, next-bar advance, Fibonacci, ruler, long/short risk boxes, report generation, and restart history reconstruction passed.
- Browser console errors: 0.
- Restart runtime: exact replay time, long position, and one pending limit order restored in 3.88s.
- Long-range funding: 274 BTCUSDT events returned for January 1 through April 1, 2024.
- Automated: 116 focused tests plus 24 subtests passed; full suite 511 tests plus 37 subtests passed.
- Static: JavaScript syntax checks, Python compile checks, and git diff check passed (line-ending warnings only).

## Important Notes
- Binance returned HTTP 418/IP restriction from this environment; Bybit fallback supplied real data successfully.
- .runtime/ remains intentionally untracked and must not be committed or modified.
- TASK-020, TASK-021, and TASK-022 are complete and moved to .agent/tasks/done/.

## Next Action
Normal product use and user feedback. No implementation work remains for this milestone.
