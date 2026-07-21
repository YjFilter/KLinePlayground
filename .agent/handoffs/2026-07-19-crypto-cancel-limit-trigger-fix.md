# Crypto Cancel and Limit Trigger Fix

## Scope
- Fixed stale or racing crypto pending-order cancellation.
- Verified daily limit-order matching and removed the old-server condition behind the reported missed fill.

## Changes
- `backend/app_enhanced.py`: cancellation now shares `_crypto_next_lock`, checkpoints successful cancellations, and returns structured missing/inactive-order state with the latest pending orders.
- `frontend/js/main_enhanced.js`: failed cancellation refreshes authoritative account/order state before displaying the error.
- `tests/test_crypto_futures_api.py`: covers immediate checkpointing and inactive-order responses.
- `tests/test_crypto_frontend_static.py`: covers removal of dead cancellation code and refresh-on-failure behavior.
- `tests/test_crypto_breakout_orders.py`: covers no future daily candles and exact underlying-candle execution for a BTCUSDT short limit.

## Root Cause
- The running Flask process predated the backend changes while static JavaScript was read from disk on each request. The browser therefore used a newer frontend against an older backend.
- The screenshot at replay time `2025-07-19 23:55:00` displayed the OHLC of the `2025-07-28` candle, confirming the old process leaked future chart bars.
- Current source correctly clips chart data to `current_time` and processes every underlying five-minute candle when advancing a daily bar.

## Verification
- Cancellation/daily/frontend focused set: 54 passed and 10 subtests.
- Orders/replay/persistence set: 40 passed and 10 subtests.
- Full suite: 642 passed and 47 subtests.
- `node --check frontend/js/main_enhanced.js`: passed.
- `python -m compileall -q backend tests`: passed.
- `git diff --check`: passed with line-ending warnings only.
- Stale project Flask processes were stopped; one fresh server is listening on `0.0.0.0:8000`, PID 24292, and returns HTTP 200.

## Safety
- No commit created.
- Existing uncommitted changes preserved.
- `.runtime/` and offline crypto data were not edited, deleted, staged, or included.

## Next Action
- Force-refresh the browser with `Ctrl+F5`.
- Submit a far-away limit order and cancel it; it should disappear immediately.
- Submit a short limit and advance the replay; it should fill only when a newly revealed underlying five-minute high reaches the limit.
