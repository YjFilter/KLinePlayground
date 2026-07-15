# Compact Layout and Daily Marker Repair Complete

## Completed
- Compressed the active-training global toolbar, stock header, history toolbar, and replay status bar.
- Changed panel defaults to prioritize the K-line view and lowered volume/indicator minimum heights for meaningful resizing.
- Added immediate intraday trade-marker payloads to buy/sell responses.
- Preserved marker state across snapshots and chart-window refreshes.
- Aligned marker timestamps to the current rendered period and reused one marker primitive.

## Verification
- 19 TDD-focused tests: PASS.
- 132 frontend/history/intraday API focused tests: PASS.
- Full suite: 373 tests PASS.
- JavaScript syntax checks: PASS.
- git diff --check: PASS with line-ending warnings only.
- Browser desktop dimensions: toolbar 42px, chart header 48px, history toolbar 29.8px, replay bar 27.2px.
- Browser drag: main chart 584px -> 714px; volume 89px -> 39px; indicator 138px -> 58px.
- Browser daily markers without period switching: B at 2025-07-14 10:00, B at 15:00, S at 2025-07-15 15:00.
- Browser console errors: 0.

## Files
- backend/app_enhanced.py
- frontend/css/style_enhanced.css
- frontend/js/main_enhanced.js
- tests/test_intraday_api.py
- tests/test_chart_workspace_frontend.py
- .agent/STATE.md
- .agent/handoffs/2026-07-15-compact-layout-daily-markers-complete.md

## Git State
- The prior chart-workspace/local-indicator changes and this follow-up repair remain uncommitted.
- .runtime/ remains intentionally untracked and must not be committed.
