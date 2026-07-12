# Intraday Data Foundation Completion Handoff

## Outcome
Phase 1 established the canonical real 30-minute data foundation without changing replay, trading, API, frontend, report, or persistence behavior.

## Delivered
- BaoStock 0.9.3 source with canonical `stock_code`, `datetime`, `open`, `high`, `low`, `close`, and `volume` columns.
- Validation for schema, duplicates, legal A-share session timestamps, complete eight-bar trading days, OHLC consistency, and non-negative volume.
- CSV-backed cache abstraction with metadata, sorted duplicate replacement, coverage reporting, and incremental missing-range synchronization.
- Cache-first service behavior that preserves valid cached data on network or validation failure.
- Optional live verification CLI and an `intraday` quality profile included in the full gate.

## Verification
- Focused intraday tests: 24 passed.
- Full suite: 45 tests passed.
- Frontend JavaScript syntax check passed.
- Live five-year checks for `600000`, `600519`, and `300750`: 9,688 rows, 1,211 trading days, 2021-07-12 10:00 through 2026-07-10 15:00, zero validation issues for each.

## Decisions
- CSV remains the first storage format behind `IntradayCache`; consumers do not depend on the file format, allowing a later Parquet migration.
- Network verification remains optional so CI and normal quality gates stay deterministic and offline.

## Known Risk
BaoStock does not support Beijing Exchange intraday symbols. Prefixes `43`, `83`, `87`, and `92` raise an explicit source error until a fallback provider or manual import workflow is added.

## Next Phase
Implement aggregation and a canonical replay clock so ????? advances by the selected period: `30m`, `4h_session`, `daily`, or `weekly`.
