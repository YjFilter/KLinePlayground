# Crypto Two-Year History And Continuity (2026-07-22)

## Completed
- Added crypto-only `history_years` validation and setup UI (`2–5`, default `2`).
- Added background history prepare create/get/delete APIs, one-time consumption, progress/cancel handling, source isolation, and per-contract locking.
- Added natural-month history preparation in `CryptoDataService`, with cache reuse, aligned 5-minute validation, pre-download progress, and cancellation checks.
- Training runtime now stores complete prepared history through the replay time, persists its metadata, and restores it from offline cache after restart.
- Fixed multi-base-bar append for 1h/4h replay advances and added sparse-tail repair.
- Added 12,000-bar segmented rendering for 5m/15m, aligned earlier-segment boundaries, runtime-only segment reads, and frontend auto-merge near the left edge.
- Optimized next-bar history updates with a monotonic append fast path.

## Verification
- `node --check frontend/js/main_enhanced.js`: passed.
- `python -m compileall -q backend`: passed.
- Crypto tests: `262 passed, 53 subtests passed`.
- Full tests: `717 passed, 71 subtests passed`.
- `git diff --check`: passed with existing CRLF warnings only.
- Browser BTCUSDT acceptance: 25/25 prepared months, two-year history, 12,000-bar 5m/15m segments, aligned earlier segment, rapid final 1h switch, continuous 4h advance, and approximately 0.3s next-bar response after the append optimization.

## Working Tree
- No commit was created.
- Existing unrelated `.gitignore` and launcher changes remain untouched.
- `.runtime/`, offline market files, user data, and credentials were not edited or removed.

## Next Action
Hard-refresh the local app, verify the same default two-year flow with ETHUSDT, and review the entire uncommitted diff before committing.
