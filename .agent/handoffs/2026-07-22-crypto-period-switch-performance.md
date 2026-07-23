# Crypto Period Switch Performance (2026-07-22)

## Root Cause
- Expanded-history period switches rebuilt the full trading bundle for every cold period, including trade, mark, funding, validation, and repeated gzip/Decimal conversion.
- The backend then serialized up to 105,121 bars row by row and returned duplicate K-line and volume arrays; `/next` discarded all derived caches.

## Completed
- Added a chart-only trade-candle loader with float cache reads and no mark/funding work.
- Cached the normalized expanded 5-minute frame in active training state and reused it for all period aggregation.
- Appended the newly revealed 5-minute bar to that frame on `/next`, while invalidating only derived period payloads.
- Replaced row iteration with vectorized time/value serialization.
- Added compact OHLCV period responses and an 8-entry browser period snapshot cache with explicit invalidation boundaries.
- Preserved expanded window bounds, replay time, future-data isolation, rapid-switch cancellation, visible-range restoration, and API compatibility for clients that do not request compact output.

## Performance Evidence
- BTCUSDT one-year Flask route: `4h 0.17s`, `1h 0.30s`, `15m 0.82s`, `5m 1.70s`, `daily 0.09s`.
- Repeated `4h`: `0.01s`; browser cache avoids the repeated request entirely.
- Compact 5m payload: about `11.0MB`, down from about `31.9MB`.

## Verification
- Crypto-focused tests: `236 passed, 48 subtests passed`.
- Full suite: `690 passed, 66 subtests passed`.
- `node --check frontend/js/main_enhanced.js`, `python -m compileall -q backend`, and `git diff --check` passed.
- Final service: `http://127.0.0.1:8000/`, listening on `0.0.0.0:8000`, PID `9268`.

## Working Tree
- No commit was created.
- Existing uncommitted feature work remains intact.
- `.runtime/`, offline data, local users, credentials, `.gitignore`, and `启动项目.bat` were not modified by this task.

## Next Action
Hard-refresh the browser, load earlier history once, and verify repeated BTCUSDT/ETHUSDT period switches during normal replay.
