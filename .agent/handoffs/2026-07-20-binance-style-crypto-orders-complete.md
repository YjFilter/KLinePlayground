# Binance-Style Crypto Orders Complete

## Scope
- Rebuilt the crypto futures order flow across backend, API, frontend, persistence, and tests.
- Preserved A-share trading behavior, drawing tools, existing uncommitted work, `.runtime/`, and offline market data.

## Delivered Behavior
- Supports market, limit, and breakout orders with strict Binance-style directional validation.
- Pending orders begin matching only on newly revealed candles after submission.
- Limit and breakout fills use the configured order price for deterministic replay.
- Opening orders may attach mark-price-triggered take-profit and stop-loss protection.
- Same-candle TP/SL conflicts resolve stop-loss first; a filled protection order cancels its OCO sibling.
- Duplicate active opening pending orders are rejected per direction.
- Pending cards support copy parameters and cancellation without silently resubmitting.
- API errors expose stable `code`, `message`, and `error` fields plus quantity/notional constraints.

## Final Review Fixes
- `frontend/js/main_enhanced.js`: `renderCryptoAccount()` now forwards `pendingOrders` instead of an undefined `orders` variable.
- `frontend/js/main_enhanced.js`: `updateCurrentInfo()` tolerates crypto progress payloads that do not include percentage/bar-count fields.
- `frontend/js/main_enhanced.js`: incremental crypto next-bar responses now refresh replay time, boundary, bar status, and current training timestamps.
- Added execution/static regressions in `tests/test_crypto_frontend_static.py` and `tests/test_crypto_workspace_interactions.py`.

## Browser Acceptance
- BTCUSDT market long with TP/SL created one position and two protection orders.
- Cancelling one protection order refreshed the pending list; market close flattened the position and removed the remaining OCO order.
- Invalid open-long limit above current price showed a clear direction error.
- Valid open-long limit at `117751.43` stayed pending on submission and filled on the next revealed underlying candle at the configured price.
- Copy parameters populated the form without submitting a duplicate order.
- Open-short breakout submitted and cancelled successfully.
- ETHUSDT loaded from offline data and advanced without console errors.
- ETH next-bar latency measured 348ms for partial-to-close and 414ms for cached incremental advancement.

## Verification
- `python -m pytest -q` -> `657 passed, 61 subtests passed in 46.57s`.
- `node --check frontend/js/main_enhanced.js` -> passed.
- `python -m compileall -q backend` -> passed.
- `git diff --check` -> passed; only existing LF/CRLF conversion warnings were printed.
- Independent read-only review found no remaining blocking state-machine, field-contract, A-share isolation, or UI-event issues after the final fixes.

## Runtime
- Server: `http://127.0.0.1:8000/`.
- LAN: `http://192.168.1.24:8000/`.
- Binding: `0.0.0.0:8000`.
- PID at handoff: `17568`.

## Safety
- No commit created.
- Existing uncommitted changes preserved.
- `.runtime/` and offline data were not modified, deleted, staged, or included.

## Next Action
- Use the running BTC/ETH replay normally.
- Before committing, review the entire working tree and explicitly exclude `.runtime/` and offline data.
