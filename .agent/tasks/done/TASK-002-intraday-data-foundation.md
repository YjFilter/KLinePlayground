---
id: TASK-002
title: Build BaoStock intraday data foundation
status: done
priority: P0
owner: codex
depends_on: []
write_scope:
  - requirements.txt
  - backend/intraday
  - tests/fixtures/intraday
  - tests/test_intraday_source.py
  - tests/test_intraday_validator.py
  - tests/test_intraday_cache.py
  - tests/test_intraday_service.py
  - scripts/verify_baostock_30m.py
  - scripts/quality_gate.py
  - tests/test_quality_gate.py
  - .agent/QUALITY_GATES.md
  - .agent/STATE.md
  - .agent/handoffs
read_scope:
  - backend/data_manager.py
  - backend/kline_processor_enhanced.py
  - docs/superpowers/specs/2026-07-12-multi-timeframe-intraday-replay-design.md
quality_profiles:
  - intraday
  - full
---

## Background
The approved multi-timeframe design requires a stable five-year 30-minute data foundation before replay, trading, API, or UI changes.

## Goal
Provide a tested BaoStock source, validator, CSV cache, cache-first synchronization service, live verification script, and intraday quality profile.

## Non-Goals
- Do not modify replay, trading, Flask API, frontend, reports, or persistence behavior.
- Do not introduce period switching in this phase.

## Constraints
- Use offline deterministic unit tests for CI.
- Keep live BaoStock checks optional.
- Preserve valid cache on network or validation failure.

## Acceptance Criteria
- [x] BaoStock rows normalize into seven canonical columns.
- [x] Invalid or incomplete data is rejected with structured issues.
- [x] Cache round-trip, metadata, merge, and coverage are tested.
- [x] Covered cache avoids network and insufficient cache fails clearly.
- [x] Intraday and full quality profiles pass.
- [x] Three representative stocks pass live five-year verification.

## Required Commands
```powershell
python scripts/quality_gate.py intraday
python scripts/quality_gate.py full
python scripts/verify_baostock_30m.py --years 5 600000 600519 300750
```

## Result Contract
Move to review with exact test and live verification evidence. Only Codex may mark the task done.

## Completion Evidence
- Intraday profile passed with all source, validator, cache, and service tests.
- Full profile passed with 45 tests plus frontend JavaScript syntax validation.
- Live five-year verification passed for `600000`, `600519`, and `300750`: 9,688 rows, 1,211 trading days, and zero issues for each stock.
- Beijing Exchange limitation is explicit and documented.
