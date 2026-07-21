# Crypto Funding Cutoff and Editable Fee Settings Complete

## Reported Symptom
- Session: `yj_20260717_131521`
- Gross realized PnL: +99.4823 USDT
- Trading fees: 49.8388 USDT
- Incorrect historical funding: paid 208.0038 USDT, received 4.9596 USDT
- Stored final return: -1.5340%

## Root Cause
A new `FuturesReplayExecutor` retained the full funding history. On the first replay advance after opening a position, `FuturesEngine.process_bar()` settled every event whose timestamp was before the new bar, including funding events that happened before the selected replay start time.

## Changes
- `backend/crypto/trading.py`: filters funding events to timestamps strictly after the replay start.
- `backend/crypto/futures_orders.py`: adds validated runtime fee-rate updates.
- `backend/app_enhanced.py`: adds default/range constants, `POST /api/training/<id>/fee-rates`, flat/no-pending validation, runtime/reset persistence, and report fee-rate fields.
- `frontend/index_enhanced.html`: adds compact Maker/Taker percentage inputs and an Apply button inside the crypto trade console.
- `frontend/js/main_enhanced.js`: synchronizes backend rates, converts percentage inputs to decimal rates, saves inline without alerts, and locks editing while a position or pending order exists.
- `frontend/css/style_enhanced.css`: adds compact dark-theme fee editor styling.
- Regression coverage added in crypto replay, futures API, frontend static, and workspace interaction tests.

## Fee Semantics
- Defaults: Maker 0.02%, Taker 0.05%.
- Allowed range: 0%–1%.
- Changes affect subsequent fills only.
- Editing requires a flat position and no pending orders.
- Custom values persist through reset and runtime rehydration.

## Live Acceptance
A temporary acceptance session replayed BTCUSDT from 2025-07-17 05:10 to 05:50 with Maker 0.01% and Taker 0.03%. The result was realized PnL +9.9246 USDT, fees 2.9832 USDT, no funding transfers, final equity 10006.9414 USDT, and total return +0.0694%. The temporary session and history record were cleaned up.

## Verification
- Focused: 81 passed and 4 subtests passed.
- Full: 597 passed and 37 subtests passed.
- JavaScript syntax, Python compileall, and git diff check passed.

## Runtime and Safety
- Server: `http://127.0.0.1:8000/`, PID 4380.
- No commit was created.
- `.runtime/` was not modified; offline market data was not modified or staged.
- The existing affected `yj` history record remains unchanged to avoid silently rewriting user data.
