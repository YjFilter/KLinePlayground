# Phase 5 Flask Integration Completion

## Session Goal
Integrate the accepted trading-day replay, chart-window, and intraday blind-box contracts into Flask startup, persistence, and history review APIs.

## Completed Work
- Added specified intraday startup with two years of requested context and distinct trading-day replay truncation.
- Added random intraday startup through `IntradayRandomSelector` using a real selected trading timestamp.
- Added `GET /api/training/<training_id>/chart-window` with server-side active-session future capping.
- Added `GET /api/users/<username>/history/<session_id>/chart` that works after Flask restart and without `active_trainings`.
- Added best-effort legacy daily/weekly history serialization.
- Persisted `data_mode`, `base_interval`, active period, exact training timestamps, data source, and `max_training_days` in completed report data.
- Added API tests for random startup, negative limits, active windows, completed intraday review, legacy review, and missing metadata.

## Active Tasks
- None. The next WorkBuddy task should be JavaScript-only and consume the now-stable API contract.

## Blocked Work
- None.

## Git Status
- Branch: `master`.
- `.runtime/` remains intentionally untracked and must not be committed.
- This integration commit owns `backend/app_enhanced.py`, three API test files, state, and this handoff.

## Verification
| Command | Exit Code | Result |
| --- | ---: | --- |
| `python -m pytest tests/test_intraday_blind_box_api.py tests/test_intraday_history_chart_api.py tests/test_intraday_api.py -q` | 0 | 72 passed. |
| `python -m pytest tests/test_intraday_blind_box_api.py tests/test_intraday_history_chart_api.py tests/test_intraday_api.py tests/test_trading_rules.py -q` | 0 | 80 passed. |
| `python scripts/quality_gate.py phase3` | 0 | All phase3 quality groups passed. |
| `python -m unittest discover -s tests -p 'test_intraday*.py'` | 0 | 297 passed. |
| `python -m py_compile backend/app_enhanced.py` | 0 | Compile passed. |
| `git diff --check` | 0 | No whitespace errors. |

## Decisions
- Startup passes the complete market frame only to previous-close construction; the replay session receives the immutable trading-day-limited frame.
- Active history requests reload through `ChartWindowService` rather than retaining duplicate market data in memory.
- Completed review is read-only and may request later market years, while active review remains capped at the current replay timestamp.
- Older reports without reconstruction metadata return a specific HTTP 400 instead of a misleading not-found result.

## Risks
- The frontend still needs to replace its one-shot chart assumptions with explicit window state and request serialization.
- BaoStock still excludes Beijing Exchange prefixes `43`, `83`, `87`, and `92` for intraday blind-box selection.

## Next Action
Create and run a JavaScript-only WorkBuddy task for TASK-018 control wiring, then let Codex review the diff, run static/API regressions, and perform browser acceptance.
