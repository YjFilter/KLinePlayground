# Intraday Data Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a tested BaoStock-backed service that downloads, validates, incrementally caches, and serves five years of normalized 30-minute A-share data without changing replay or trading behavior.

**Architecture:** Introduce a focused `backend/intraday/` package with source, validation, cache, and orchestration boundaries. Store normalized CSV behind a cache interface for the first release; consumers remain independent of storage format so Parquet can be introduced later.

**Tech Stack:** Python 3.11, pandas, BaoStock 0.9.3, dataclasses, unittest, temporary filesystem fixtures.

---

## Preconditions

- Review and commit or isolate the current uncommitted training-review redesign.
- Execute on a dedicated feature branch or approved worktree.
- Replay, trading, API, and frontend files are read-only in this phase.

## File Map

- Modify `requirements.txt`.
- Create `backend/intraday/__init__.py`.
- Create `backend/intraday/models.py`.
- Create `backend/intraday/baostock_source.py`.
- Create `backend/intraday/validator.py`.
- Create `backend/intraday/cache.py`.
- Create `backend/intraday/service.py`.
- Create `tests/fixtures/intraday/600000_30m_sample.csv`.
- Create `tests/test_intraday_source.py`.
- Create `tests/test_intraday_validator.py`.
- Create `tests/test_intraday_cache.py`.
- Create `tests/test_intraday_service.py`.
- Create `scripts/verify_baostock_30m.py`.
- Modify `scripts/quality_gate.py` and `.agent/QUALITY_GATES.md`.

### Task 0: Establish a Clean Feature Baseline

**Files:**
- Modify: `.agent/STATE.md`
- Create: `.agent/tasks/ready/TASK-002-intraday-data-foundation.md`
- Create: `.agent/handoffs/2026-07-12-intraday-data-foundation-start.md`

- [ ] **Step 1: Verify baseline and tests**

Run:

```powershell
git status --short --branch
git log -3 --oneline
python scripts/quality_gate.py full
```

Expected: control-plane commit exists, tests pass, and the feature workspace contains no unrelated uncommitted business changes.

- [ ] **Step 2: Stop on a dirty shared baseline**

If backend, frontend, or `tests/test_trading_rules.py` remain uncommitted, move this phase task to blocked. Do not implement against an unowned shared diff.

- [ ] **Step 3: Create the phase task packet**

Declare Codex owner and this write scope:

```yaml
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
  - .agent/QUALITY_GATES.md
  - .agent/STATE.md
  - .agent/handoffs
```

- [ ] **Step 4: Record the start handoff**

Record branch/worktree, baseline tests, approved live BaoStock evidence, and out-of-scope business modules.

### Task 1: Add Dependency and Domain Models

**Files:**
- Modify: `requirements.txt`
- Create: `backend/intraday/__init__.py`
- Create: `backend/intraday/models.py`
- Test: `tests/test_intraday_source.py`

- [ ] **Step 1: Write the failing model test**

```python
import unittest
from datetime import datetime


class IntradayModelTests(unittest.TestCase):
    def test_intraday_range_reports_coverage(self):
        from backend.intraday.models import IntradayRange

        coverage = IntradayRange(
            start=datetime(2021, 7, 12, 10, 0),
            end=datetime(2026, 7, 10, 15, 0),
        )

        self.assertTrue(coverage.covers(datetime(2022, 1, 1), datetime(2025, 1, 1)))
        self.assertFalse(coverage.covers(datetime(2020, 1, 1), datetime(2025, 1, 1)))
```

- [ ] **Step 2: Verify RED**

Run `python -m unittest discover -s tests -p test_intraday_source.py -v`.

Expected: `ModuleNotFoundError` for `backend.intraday`.

- [ ] **Step 3: Add dependency**

Append exactly:

```text
baostock==0.9.3
```

- [ ] **Step 4: Implement minimal models**

```python
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class IntradayRange:
    start: datetime
    end: datetime

    def covers(self, start: datetime, end: datetime) -> bool:
        return self.start <= start and self.end >= end


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    timestamp: datetime | None = None


@dataclass
class ValidationResult:
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not self.issues
```

Export these names from `backend/intraday/__init__.py`.

- [ ] **Step 5: Verify GREEN**

Run `python -m unittest discover -s tests -p test_intraday_source.py -v`.

Expected: model test passes.

### Task 2: Implement BaoStock Source with TDD

**Files:**
- Create: `backend/intraday/baostock_source.py`
- Modify: `tests/test_intraday_source.py`

- [ ] **Step 1: Add failing source tests**

Test these behaviors with a fake BaoStock API:

- `test_fetch_30m_normalizes_symbol_timestamp_and_numeric_fields`: fake success row returns one timestamped numeric normalized row and logs out once.
- `test_fetch_30m_raises_when_login_fails`: fake login code `1001` raises `IntradaySourceError` and does not query.
- `test_fetch_30m_raises_when_query_fails`: successful login plus query code `1002` raises `IntradaySourceError` and logs out.
- `test_fetch_30m_returns_empty_normalized_frame_for_no_rows`: empty successful result returns zero rows with the seven normalized columns.

Use this successful fake row:

```python
[
    "2025-01-02", "20250102100000000", "sh.600000",
    "10.00", "10.20", "9.95", "10.10",
    "10000", "101000.00", "3",
]
```

Expected columns:

```python
["datetime", "open", "high", "low", "close", "volume", "amount"]
```

- [ ] **Step 2: Verify RED**

Run `python -m unittest discover -s tests -p test_intraday_source.py -v`.

Expected: missing `BaoStockSource` failure.

- [ ] **Step 3: Implement adapter**

Public API:

- `IntradaySourceError`, a `RuntimeError` subclass.
- Constructor: `BaoStockSource(api=None)` uses the real `baostock` module when no API is injected.
- Method: `fetch_30m(stock_code: str, start: datetime, end: datetime) -> pd.DataFrame`.

Requirements:

- Convert `600000` to `sh.600000`; other supported A-share prefixes use `sz.*`.
- Call `login()` and always `logout()` in `finally`.
- Query frequency `30`, adjust flag `3`, and BaoStock date/time/OHLCV/amount fields.
- Parse `YYYYMMDDHHMMSSmmm` timestamps.
- Convert numeric fields, sort, and remove duplicate timestamps keeping the latest row.
- Return normalized columns only.
- Map BaoStock error codes to `IntradaySourceError`.

- [ ] **Step 4: Verify GREEN**

Run `python -m unittest discover -s tests -p test_intraday_source.py -v`.

Expected: model and source tests pass offline.

### Task 3: Implement Validation with TDD

**Files:**
- Create: `backend/intraday/validator.py`
- Create: `tests/test_intraday_validator.py`
- Create: `tests/fixtures/intraday/600000_30m_sample.csv`

- [ ] **Step 1: Create two complete fixture days**

Use all eight legal timestamps per day with valid OHLCV values.

- [ ] **Step 2: Write failing tests**

- `test_complete_fixture_is_valid`: two complete fixture days produce no issues.
- `test_duplicate_timestamp_is_reported`: duplicating the first row produces `duplicate_timestamp`.
- `test_invalid_ohlc_is_reported`: setting high below close produces `invalid_ohlc`.
- `test_negative_volume_is_reported`: setting volume to `-1` produces `negative_volume`.
- `test_illegal_session_time_is_reported`: changing one timestamp to `12:00` produces `illegal_session_time`.
- `test_incomplete_day_is_reported`: removing the `15:00` row produces `incomplete_trading_day`.

- [ ] **Step 3: Verify RED**

Run `python -m unittest discover -s tests -p test_intraday_validator.py -v`.

Expected: missing `validate_30m_frame` failure.

- [ ] **Step 4: Implement validation**

```python
VALID_30M_TIMES = {
    "10:00", "10:30", "11:00", "11:30",
    "13:30", "14:00", "14:30", "15:00",
}

```

Public function: `validate_30m_frame(frame: pd.DataFrame) -> ValidationResult`.

Issue codes:

```text
duplicate_timestamp
invalid_ohlc
negative_volume
negative_amount
illegal_session_time
incomplete_trading_day
```

Only dates with at least one row are checked for eight complete timestamps; absent dates may be holidays or suspensions.

- [ ] **Step 5: Verify GREEN**

Run the validator test file and expect all six behaviors to pass.

### Task 4: Implement Cache with TDD

**Files:**
- Create: `backend/intraday/cache.py`
- Create: `tests/test_intraday_cache.py`

- [ ] **Step 1: Write failing cache tests**

- `test_save_and_load_round_trip`: save two rows, load them, and compare normalized columns and values.
- `test_merge_replaces_duplicate_and_sorts`: incoming duplicate replaces existing timestamp and result is sorted.
- `test_coverage_uses_first_and_last_timestamp`: coverage equals minimum and maximum cached datetime.
- `test_metadata_records_source_rows_and_issues`: JSON records source, row count, range, update time, and issue counts.
- `test_missing_stock_returns_empty_frame`: missing cache yields normalized empty frame, no metadata, and no coverage.

- [ ] **Step 2: Verify RED**

Run `python -m unittest discover -s tests -p test_intraday_cache.py -v`.

Expected: missing `IntradayCache` failure.

- [ ] **Step 3: Implement CSV-backed cache**

Public API:

- Constructor: `IntradayCache(root: Path)`.
- `load(stock_code: str) -> pd.DataFrame`.
- `save(stock_code: str, frame: pd.DataFrame, *, source: str, validation: ValidationResult) -> None`.
- `merge(existing: pd.DataFrame, incoming: pd.DataFrame) -> pd.DataFrame`.
- `coverage(stock_code: str) -> IntradayRange | None`.
- `metadata(stock_code: str) -> dict[str, object] | None`.

Paths:

```text
data/intraday/30m/600000.csv
data/intraday/metadata/600000.json
```

Write temporary sibling files and atomically replace targets.

- [ ] **Step 4: Verify GREEN**

Run cache tests and expect all five behaviors to pass.

### Task 5: Implement Cache-First Service with TDD

**Files:**
- Create: `backend/intraday/service.py`
- Create: `tests/test_intraday_service.py`

- [ ] **Step 1: Write failing service tests**

- `test_covered_cache_avoids_network`: covered cache returns requested slice and source call count stays zero.
- `test_missing_cache_downloads_validates_saves_and_returns_slice`: empty cache calls source once, saves valid data, and returns requested rows.
- `test_partial_cache_fetches_only_missing_range`: leading gap calls source with requested start through one base interval before cached start.
- `test_invalid_download_is_not_saved`: validation issue raises `IntradayDataUnavailable` and cache save count remains zero.
- `test_network_failure_uses_covered_cache`: source failure still returns data when cache covers the request.
- `test_network_failure_raises_for_insufficient_cache`: source failure plus uncovered range raises an error containing stock and range.

- [ ] **Step 2: Verify RED**

Run `python -m unittest discover -s tests -p test_intraday_service.py -v`.

Expected: missing service failure.

- [ ] **Step 3: Implement service**

Public API:

- `IntradayDataUnavailable`, a `RuntimeError` subclass.
- Constructor: `IntradayDataService(source: BaoStockSource, cache: IntradayCache)`.
- `get_30m(stock_code: str, start: datetime, end: datetime) -> pd.DataFrame`.
- `sync_30m(stock_code: str, start: datetime, end: datetime) -> pd.DataFrame`.

Rules:

- Covered cache avoids network.
- Fetch only missing leading or trailing ranges.
- Validate incoming data before merge and save.
- Any validation issue rejects the incoming synchronization in phase 1.
- Source failure falls back only to cache covering the requested range.
- Insufficient data raises `IntradayDataUnavailable` with requested range and cache coverage.

- [ ] **Step 4: Verify GREEN**

Run service tests and expect all six behaviors to pass.

### Task 6: Add Live Verification and Quality Profile

**Files:**
- Create: `scripts/verify_baostock_30m.py`
- Modify: `scripts/quality_gate.py`
- Modify: `.agent/QUALITY_GATES.md`
- Modify: `tests/test_quality_gate.py`

- [ ] **Step 1: Write failing profile test**

Assert `PROFILE_COMMANDS["intraday"]` contains all four intraday test files and `full` includes the same commands without duplication.

- [ ] **Step 2: Verify RED**

Run `python -m unittest discover -s tests -p test_quality_gate.py -v`.

Expected: missing `intraday` profile failure.

- [ ] **Step 3: Add intraday profile**

Commands:

```powershell
python -m unittest discover -s tests -p test_intraday_source.py -v
python -m unittest discover -s tests -p test_intraday_validator.py -v
python -m unittest discover -s tests -p test_intraday_cache.py -v
python -m unittest discover -s tests -p test_intraday_service.py -v
```

Include them in `full` and document the profile.

- [ ] **Step 4: Create optional live script**

CLI:

```powershell
python scripts/verify_baostock_30m.py --years 5 600000 600519 300750
```

It must print rows, first/last timestamp, trading days, and issue counts. Return nonzero on query failure, insufficient coverage, zero rows, or validation issues. Do not write cache unless `--save-cache` is supplied.

- [ ] **Step 5: Verify offline gates**

Run:

```powershell
python scripts/quality_gate.py intraday
python scripts/quality_gate.py full
```

Expected: both pass without network.

- [ ] **Step 6: Verify live data**

Run the three-stock command. Expected actual evidence is approximately 9,688 rows, 1,211 days, eight rows per complete day, and zero validation issues per stock.

### Task 7: Close Phase 1

**Files:**
- Move: `.agent/tasks/ready/TASK-002-intraday-data-foundation.md` to `.agent/tasks/done/`
- Modify: `.agent/STATE.md`
- Create: `.agent/handoffs/2026-07-12-intraday-data-foundation-complete.md`

- [ ] **Step 1: Review scope**

Run:

```powershell
git status --short
git diff --check
git diff --stat
python scripts/agent_status.py .agent/tasks
```

Expected: only phase-1 files and control-plane state records changed.

- [ ] **Step 2: Run final verification**

Run intraday and full quality profiles. Both must pass.

- [ ] **Step 3: Write completion handoff**

Record unit test counts, live results, CSV cache decision, network behavior, risks, and the next action: write the Phase 2 aggregation and replay-clock plan.

- [ ] **Step 4: Complete task after Codex acceptance**

Set task status to done, move it to `.agent/tasks/done/`, regenerate the snapshot, and do not commit or push without explicit owner authorization.

## Plan Self-Review

- Phase 1 covers BaoStock, five-year target, validation, cache-first behavior, incremental synchronization, offline tests, live evidence, quality profile, state, and handoff.
- Aggregation, replay clock, trading, API, frontend, reports, and database migration remain explicitly deferred.
- CSV storage is hidden behind `IntradayCache`; later Parquet migration does not affect consumers.
- No unresolved placeholder markers or undefined production interfaces remain.

