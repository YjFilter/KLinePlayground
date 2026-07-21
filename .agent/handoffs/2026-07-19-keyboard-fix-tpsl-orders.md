# Keyboard Fix and TP/SL Orders Handoff

## Completed Work

### 1. Keyboard Shortcut Bug Fix
- Root cause: `setupKeyboardShortcuts()` only checked if focus was on the A-share `trade-quantity` input. All other inputs (crypto trigger price, margin, fee rate) had their number keys intercepted by `preventDefault()` and redirected to the A-share quantity field.
- Fix: the handler now returns early when `document.activeElement` is any `INPUT`, `SELECT`, or `TEXTAREA`. The `event.repeat` check was also simplified.
- File: `frontend/js/main_enhanced.js`

### 2. Take-Profit / Stop-Loss Orders
- Backend (`backend/crypto/futures_orders.py`):
  - `FuturesOrder` gained `tp_price`, `sl_price`, `parent_order_id` fields with full serialization support.
  - `submit_order` validates TP/SL directionally (long: tp > entry > sl; short: tp < entry < sl).
  - `_fill_order` creates TP (limit reduce_only) and SL (breakout reduce_only) child orders after an opening fill.
  - OCO: `_cancel_sibling_tp_sl` cancels the sibling when one child fills.
  - `_cancel_orphaned_tp_sl` cleans up when position goes flat.
  - `process_bar` sorts SL children before TP children for conservative same-bar resolution.
- Backend (`backend/app_enhanced.py`): `/trade` accepts `tp_price`/`sl_price` with Chinese error messages.
- Frontend (`frontend/index_enhanced.html`): TP/SL toggle, two price inputs, PnL display spans.
- Frontend (`frontend/js/main_enhanced.js`): toggle logic, PnL estimation, submit integration, reset, enhanced pending order display.
- Frontend (`frontend/css/style_enhanced.css`): dark-theme TP/SL section styling with green/red accents.

### 3. Tests
- New file: `tests/test_crypto_tp_sl.py` — 18 tests covering creation, validation, trigger, OCO, same-bar conflict, manual close, and persistence round-trip.
- Full suite: 639 passed + 47 subtests (was 621 + 47).

## Modified Files
- `frontend/js/main_enhanced.js` (keyboard fix + TP/SL JS)
- `frontend/index_enhanced.html` (TP/SL HTML)
- `frontend/css/style_enhanced.css` (TP/SL CSS)
- `backend/crypto/futures_orders.py` (TP/SL order logic)
- `backend/app_enhanced.py` (API parameter pass-through + error map)
- `tests/test_crypto_tp_sl.py` (new)
- `.agent/STATE.md` (this update)

## Verification
- `python -m py_compile backend/crypto/futures_orders.py` — OK
- `python -m py_compile backend/app_enhanced.py` — OK
- `node -c frontend/js/main_enhanced.js` — OK
- `python -m pytest tests/test_crypto_tp_sl.py -v` — 18 passed
- `python -m pytest -x -q` — 639 passed, 47 subtests passed

## Pending
- Server restart required to load new backend code.
- Visual browser acceptance of TP/SL panel not yet performed.
- LAN access investigation still pending client-side evidence.
- Port conflict: agent-orchestrator (PID 12048) on 127.0.0.1:8000 shadows KLinePlayground for localhost.

## Safety
- No commit created. All existing uncommitted changes preserved.
- `.runtime/` and offline market data untouched and excluded.
