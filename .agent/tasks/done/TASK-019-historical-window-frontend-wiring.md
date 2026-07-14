---
id: TASK-019
title: Wire historical chart windows and intraday blind-box setup
status: done
priority: P0
owner: workbuddy-019
depends_on:
  - TASK-018
write_scope:
  - frontend/js/main_enhanced.js
  - tests/test_intraday_frontend_static.py
  - tests/test_intraday_history_frontend_static.py
read_scope:
  - frontend/index_enhanced.html
  - frontend/css/style_enhanced.css
  - backend/app_enhanced.py
  - tests/test_intraday_blind_box_api.py
  - tests/test_intraday_history_chart_api.py
  - tests/test_intraday_context_static_ui.py
  - docs/superpowers/specs/2026-07-14-historical-context-trading-day-blind-box-design.md
  - docs/superpowers/plans/2026-07-14-historical-context-blind-box.md
quality_profiles:
  - frontend
---

## Goal
Wire the accepted historical-window controls and stable Flask API contract into the existing frontend without changing backend, HTML, CSS, persistence, dependencies, or Git state.

## Stable API Contract
- Start intraday sessions with `data_mode: "intraday_30m"` and `max_training_days` for both specified and random modes.
- Active window: `GET /api/training/{trainingId}/chart-window?period=...&range_start=...&range_end=...`.
- Completed review: `GET /api/users/{username}/history/{sessionId}/chart?period=...&range_start=...&range_end=...`.
- Active responses are server-capped at replay `current_time` and return `read_only: false`.
- Completed responses return `read_only: true`, `has_earlier`, `has_later`, K-line data, volume data, and trade markers.
- API timestamp fields use `YYYY-MM-DD HH:MM:SS`.

## Acceptance Criteria
- [ ] Training setup sends `max_training_days`, not a 30-minute bar-count interpretation.
- [ ] Random and specified modes both use `intraday_30m` for `30m`, `4h_session`, `daily`, and `weekly`.
- [ ] The old blind-box daily-only alert is removed.
- [ ] Starting a session renders at least the returned/requested two-year prior context without calling `/next`.
- [ ] `mergeChartWindow(existing, incoming)` deduplicates and chronologically sorts candles and volume points using the actual normalized time field.
- [ ] `loadEarlierYear()` prepends one calendar year and preserves the visible logical range.
- [ ] `loadLaterYear()` works only in completed read-only history when `has_later` is true.
- [ ] `#load-later-year-btn` stays hidden during active training.
- [ ] Both year-loading buttons disable while their own request is in flight and when no more data is available.
- [ ] `#chart-window-status` reports loading, success, empty, and error states.
- [ ] Historical review no longer calls `/api/training/{id}/full_data` and does not depend on an active in-memory training.
- [ ] Historical trade markers are rendered from the history chart response.
- [ ] Period switching and replay progression keep the current replay time unchanged except for explicit `/next` actions.
- [ ] New and existing static frontend tests pass.

## TDD Sequence
1. Add failing static tests for `max_training_days`, all-period random mode, `/chart-window`, the history chart route, `loadEarlierYear`, `loadLaterYear`, `mergeChartWindow`, and active later-button hiding.
2. Run the focused tests and confirm the new assertions fail for missing behavior.
3. Implement the minimum JavaScript required to pass.
4. Run syntax, focused tests, and diff checks.

## Constraints
- Modify only the three write-scope files.
- Do not modify backend, HTML, CSS, dependencies, `.agent`, generated data, caches, or user files.
- Do not run live BaoStock requests.
- Do not execute `git add`, `git commit`, `git checkout`, `git reset`, `git clean`, or create branches.
- Preserve existing chart library and page structure; do not redesign unrelated UI.
- Serialize chart-window requests so repeated clicks cannot race and overwrite newer state.
- Stop and report instead of editing outside scope.

## Required Verification
```powershell
node --check frontend/js/main_enhanced.js
python -m unittest tests.test_intraday_frontend_static tests.test_intraday_history_frontend_static tests.test_intraday_context_static_ui -v
git diff --check -- frontend/js/main_enhanced.js tests/test_intraday_frontend_static.py tests/test_intraday_history_frontend_static.py
git diff --stat -- frontend/js/main_enhanced.js tests/test_intraday_frontend_static.py tests/test_intraday_history_frontend_static.py
```

## Final Report
Reply with:
- changed files;
- implementation summary;
- commands actually run and exact pass/fail counts;
- any risks or unresolved items;
- confirmation that no files outside write scope and no Git state were modified.
