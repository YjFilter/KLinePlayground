# Crypto Extended Window And Independent Theme (2026-07-22)

## Root Cause
- `/chart-window` could display offline 2024 data, but `CryptoReplaySession` only held the training range plus its recent context.
- `/period` re-aggregated from session data, so a period change discarded the expanded offline chart window and returned the fast 300-bar view.
- The crypto shell was always dark while Lightweight Charts followed the independent global A-share theme, causing white charts inside a dark workspace.

## Completed
- Active crypto training remembers expanded `window_start`, `window_end`, and coverage state after an earlier-history load.
- `/period` keeps session replay/account/order state authoritative, but uses `CryptoChartWindowService` to re-aggregate expanded ranges from offline cache for the new period.
- Period-window results are cached per training and invalidated on next, reset, and end. Future bars remain capped by `current_time`.
- Frontend tracks `extended_history`, sends range bounds only for expanded windows, keeps one `/period` request, and updates state from explicit response boundaries.
- Timestamp parsing supports Date objects, numeric seconds/milliseconds, numeric strings, and formatted timestamps.
- Crypto theme now has independent `crypto_theme` and `cryptoUiTheme` values, defaults dark, persists per user/browser, and never mutates `document.body.dataset.theme`.
- A compact sun/moon button switches the full crypto workspace, all three charts, overlays, controls, and trade console between unified dark and light palettes.

## Verification
- Expanded-window regression switches BTCUSDT through `4h`, `1h`, and `15m`, retains the 2024 start, preserves replay time, and rejects the future fixture bar.
- Crypto-focused suite: `230 passed, 48 subtests passed`.
- Full suite: `683 passed, 66 subtests passed`.
- `node --check frontend/js/main_enhanced.js`, `python -m compileall -q backend`, and `git diff --check` passed.
- Browser acceptance loaded one earlier year on BTCUSDT and switched daily to 4-hour with 2024 candles still visible.
- Browser acceptance switched light/dark palettes and confirmed `body[data-theme]` remained unchanged.
- Local Flask service restarted on `0.0.0.0:8000`, PID 12792.

## Working Tree
- No commit was created.
- Existing unrelated launcher changes in `.gitignore` and `启动项目.bat` remain preserved.
- `.runtime/`, local users, offline market data, and credentials were not directly modified.

## Next Action
Hard-refresh the page and continue normal BTC/ETH replay. Review all uncommitted changes before creating any commit.
