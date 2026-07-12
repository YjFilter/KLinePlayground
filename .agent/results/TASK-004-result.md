# Task Result

## Task
- ID: TASK-004
- Owner: test-agent (external test-focused Agent)
- Final state requested: review

## Changed Files
- `tests/fixtures/intraday/validator_edge_cases.csv` (new) — deterministic two-trading-day 30m fixture (16 rows, 8 bars/day, 2025-01-02 and 2025-01-03).
- `tests/test_intraday_validator_edge_cases.py` (new) — 12 black-box edge-case tests.
- `.agent/tasks/review/TASK-004-intraday-validator-edge-tests.md` (moved from `ready/`) — `status` changed `ready` → `review`.

No other files were modified. Files under `backend/`, existing tests, `requirements.txt`, `scripts/quality_gate.py`, replay/trading/API/database code, and frontend were treated as read-only.

## Summary
Added offline, deterministic, black-box edge-case tests for `backend.intraday.validator.validate_30m_frame`. Tests assert only the public validation result (issue codes returned by the function), not internal implementation details. A reusable CSV fixture provides a clean two-trading-day frame; remaining cases mutate that frame in-code (mirroring the style of `tests/test_intraday_validator.py`).

The new suite covers boundaries not already asserted by the existing validator tests, and documents one suspected production defect (see "Suspected Production Defect" below). The defect-demonstrating tests assert the *actual* current behavior so the suite stays green while preserving evidence for Codex review.

## Acceptance Criteria
- [x] Add a reusable deterministic fixture or construct equivalent deterministic rows in the new test file. — `validator_edge_cases.csv` (16 rows, 2 complete trading days).
- [x] Cover a valid two-trading-day frame. — `test_valid_two_trading_day_frame_is_clean`.
- [x] Cover at least three distinct untested boundaries. — unsorted timestamps (`test_unsorted_timestamps_remain_valid`), null OHLC (`test_null_ohlc_high_is_flagged`, `test_null_ohlc_close_is_flagged`), high/low equality boundaries (`test_flat_bar_all_equal_is_valid`, `test_open_equals_high_boundary_is_valid`, `test_close_equals_low_boundary_is_valid`, `test_high_equals_low_with_matching_oc_is_valid`), empty frame (`test_empty_frame_is_valid`), nonnumeric/null volume+amount (`test_nonnumeric_volume_silently_accepted_DEFECT`, `test_null_volume_silently_accepted_DEFECT`, `test_null_amount_silently_accepted_DEFECT`).
- [x] Avoid duplicating existing duplicate-time, illegal-session, incomplete-day, invalid-OHLC, and negative-volume assertions. — None of the new tests duplicate those; invalid-OHLC here uses a *null* value (a genuinely different boundary from the existing `high = close - 1`).
- [x] `python -m unittest tests.test_intraday_validator_edge_cases -v` passes. — 12 tests, OK, exit 0.
- [x] `python scripts/quality_gate.py intraday` passes. — all 4 sub-profiles PASS (24 tests), exit 0.

## Test Scenarios Added (12)
| # | Test | Boundary | Expected | Actual |
|---|------|----------|----------|--------|
| 1 | `test_valid_two_trading_day_frame_is_clean` | valid 2-day frame | no issues | no issues ✓ |
| 2 | `test_unsorted_timestamps_remain_valid` | unsorted timestamps | no issues (order-independent) | no issues ✓ |
| 3 | `test_null_ohlc_high_is_flagged` | null OHLC (NaN high) | `invalid_ohlc` | `invalid_ohlc` ✓ |
| 4 | `test_null_ohlc_close_is_flagged` | null OHLC (NaN close) | `invalid_ohlc` | `invalid_ohlc` ✓ |
| 5 | `test_flat_bar_all_equal_is_valid` | equality boundary (open=high=low=close) | no issues | no issues ✓ |
| 6 | `test_open_equals_high_boundary_is_valid` | equality boundary (open==high) | no issues | no issues ✓ |
| 7 | `test_close_equals_low_boundary_is_valid` | equality boundary (close==low) | no issues | no issues ✓ |
| 8 | `test_high_equals_low_with_matching_oc_is_valid` | tightest equality boundary | no issues | no issues ✓ |
| 9 | `test_empty_frame_is_valid` | empty input | no issues | no issues ✓ |
| 10 | `test_nonnumeric_volume_silently_accepted_DEFECT` | nonnumeric volume | (expected: some issue) | **no issue — suspected defect** |
| 11 | `test_null_volume_silently_accepted_DEFECT` | null volume | (expected: some issue) | **no issue — suspected defect** |
| 12 | `test_null_amount_silently_accepted_DEFECT` | null amount | (expected: some issue) | **no issue — suspected defect** |

## Commands Run
| Command | Exit Code | Result |
| --- | ---: | --- |
| `D:/anaconda3/python.exe -m unittest tests.test_intraday_validator_edge_cases -v` | 0 | Ran 12 tests — OK (0.405s) |
| `D:/anaconda3/python.exe scripts/quality_gate.py intraday` | 0 | 4/4 sub-profiles PASS: source 7, validator 6, cache 5, service 6 = 24 tests OK |

Note: the repo's working Python is `D:/anaconda3/python.exe` (pandas 2.3.3); the default `python` on PATH lacks pandas. The documented `python` commands map to this interpreter.

## Suspected Production Defect (requires Codex review)
**Location:** `backend/intraday/validator.py`, negative-check loop (lines ~38–41).

**Root cause:** volume and amount are validated only via
```python
invalid = pd.to_numeric(working[column], errors="coerce") < 0
```
`pd.to_numeric(..., errors="coerce")` converts nonnumeric values and existing NaN to NaN, and `NaN < 0` evaluates to `False`. Therefore null (NaN) and nonnumeric volume/amount values produce **no issue**.

**Inconsistency:** OHLC columns ARE checked for NaN — `working[["open","high","low","close"]].isna().any(axis=1)` → `invalid_ohlc`. So a null OHLC value is flagged, but a null volume or amount is silently accepted. There is no `invalid_volume` / `null_volume` / `nonnumeric_value` issue code.

**Expected behavior:** null or nonnumeric volume/amount should surface a dedicated issue (mirroring the OHLC NaN handling), or at minimum be reported so downstream cache/sync does not silently ingest bad data.

**Actual behavior:** no issue emitted; `ValidationResult.is_valid` is `True`.

**Impact:** corrupted or partial CSV rows with blank/nonnumeric volume or amount pass validation and can enter the cache. Low likelihood for BaoStock-sourced data (always numeric), but relevant for manual imports / merge edges.

**Reproduce (from repo root):**
```
D:/anaconda3/python.exe -c "import pandas as pd; from backend.intraday.validator import validate_30m_frame; f=pd.read_csv('tests/fixtures/intraday/validator_edge_cases.csv', parse_dates=['datetime']); f.loc[0,'volume']=float('nan'); print([i.code for i in validate_30m_frame(f).issues])"
# -> []   (expected: a volume-related issue code)
```

**Action taken:** Per task constraints, production code was NOT modified. Three tests (`*_DEFECT`) assert the actual behavior to preserve evidence and are clearly named. No test was forced to fail, so both required commands pass; the defect is escalated here for Codex decision.

## Risks
- The `*_DEFECT` tests assert current (possibly unintended) behavior. If Codex fixes the validator to emit a volume/amount issue, these three tests must be updated to assert the new expected code — they are isolated and clearly named to make that flip safe and obvious.
- `test_nonnumeric_volume_silently_accepted_DEFECT` casts the volume column to `object` before assigning a string to avoid a pandas FutureWarning about dtype incompatibility; this does not change the validator's coercion path.
- Tests are offline and deterministic; no network or live BaoStock access.

## Unresolved Items
- Suspected defect above awaits Codex decision (fix validator vs. accept as-designed). Not marked `done`.
- No git operations performed; no commit/merge/push/reset.

## Scope Check
Confirmed: only files in the declared `write_scope` (`tests/fixtures/intraday/validator_edge_cases.csv`, `tests/test_intraday_validator_edge_cases.py`) were created/modified for production of tests, plus the task-file move and `status` edit required by the result contract. No file outside `write_scope` was modified. `backend/`, existing tests, `requirements.txt`, `scripts/quality_gate.py`, replay/trading/API/database, and frontend remain untouched.
