# Crypto Trigger Orders and Incremental Replay Complete

## Scope
- Added A-share-style aggregated market, limit, and breakout order entry to crypto replay.
- Added opening and closing trigger-order execution.
- Optimized the next-bar path for incremental chart/account updates.

## Implementation
- `backend/crypto/futures_orders.py`: validates market/limit/breakout orders, persists trigger prices, applies maker/taker fee semantics, and prevents same-candle trigger fills.
- `backend/crypto/futures_engine.py`: passes bar open into matching and falls back to close for legacy bar payloads without open.
- `backend/crypto/session.py`: advances using period-bucket deltas and only emits a bounded refresh snapshot when the active aggregated candle must be rebuilt.
- `backend/app_enhanced.py`: exposes the delta response, rejects concurrent next-bar advances with 409, accepts breakout trigger prices, and coalesces replay-only checkpoints.
- `frontend/index_enhanced.html`, `frontend/css/style_enhanced.css`, `frontend/js/main_enhanced.js`: provide the segmented order UI, shared trigger field, click feedback, request de-duplication, and incremental series/account rendering.
- `tests/test_crypto_breakout_orders.py` and `tests/test_crypto_next_incremental.py`: cover trigger rules, persistence, no same-bar fill, delta-only responses, and duplicate request protection.

## WorkBuddy Review
- TASK-023 was reviewed and moved to `.agent/tasks/done/` with a result report.
- Worker scope was limited to HTML, CSS, and static frontend tests; Codex owned backend/JavaScript integration and final review.

## Verification
- Focused crypto set: 110 passed and 10 subtests passed.
- Compatibility regression set: 23 passed and 10 subtests passed.
- Full suite: 621 passed and 47 subtests passed.
- `node --check frontend/js/main_enhanced.js`: passed.
- `node --check frontend/js/drawing_tools.js`: passed.
- `python -m compileall -q backend tests`: passed.
- `git diff --check`: passed with existing line-ending warnings only.

## Browser Acceptance
- Running at `http://127.0.0.1:8000/` and LAN `http://192.168.1.24:8000/`, PID 15680.
- At 1366x768, DOM acceptance confirmed labels `市价 | 限价 | 突破`, unique ids, synchronized active/`aria-pressed` states, market hiding the trigger field, and limit/breakout showing it.
- Real offline BTCUSDT and ETHUSDT in-memory API acceptance completed market, limit, and breakout opening/closing without writing user history.
- Twenty sequential next-bar calls measured BTCUSDT first 5.8ms / median 4.7ms / max 6.3ms and ETHUSDT first 4.5ms / median 4.6ms / max 6.6ms after data loading.
- Flask route-level restart acceptance restored a missing active session from temporary SQLite state and continued at the next five-minute candle with no full snapshot.
- Responsive browser acceptance at 1366x768 and 1920x1080 measured three equal-width 114.66–114.67px buttons with no overflow and correct trigger-field visibility.

## Safety and Git State
- No commit was created.
- Existing uncommitted changes remain intact.
- `.runtime/` and offline market data were not modified, staged, deleted, or included in validation scope.

## Next Action
User visually checks BTCUSDT/ETHUSDT order placement and next-bar feel in the running app. Before committing, review the complete uncommitted diff and continue excluding `.runtime/` and offline data.
