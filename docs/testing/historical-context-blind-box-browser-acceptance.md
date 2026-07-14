# Historical Context and Blind-Box Browser Acceptance

## Scope
Final Phase 5 acceptance for trading-day limits, two-year context, four-period replay, active no-future enforcement, intraday blind-box startup, bidirectional completed review, persistence, and Flask restart recovery.

## Environment
- Date: 2026-07-14
- Branch: `master`
- Baseline commit: `89330a8`
- Server: `python -m backend.app_enhanced`
- Browser: Codex in-app browser against `http://127.0.0.1:5000/`
- Intraday cache pool during acceptance: `600000`

## Result
- Pass: 11
- Fail: 0
- Blocked: 0
- Final conclusion: PASS

## Initial Failure and Fix
The first real blind-box request timed out after 240 seconds. Logs showed repeated AKShare/Eastmoney candidate lookups failing through the configured proxy. The 30-minute BaoStock cache was healthy, but the candidate provider did not use it.

Codex added a tested cache-first candidate policy: available `data/intraday/30m/*.csv` codes are filtered by sector and randomly selected before any online stock-universe lookup. With the current single-code cache, the stock candidate is `600000` while the real trading date remains random. The repeated request completed in 10.69 seconds.

## Acceptance Evidence

### A. Automated integration
- Frontend/static integration before final acceptance: 54 passed.
- API and trading-rule integration before final acceptance: 81 passed.
- Intraday integration before final acceptance: 318 passed.
- Final complete discovery: 361 passed.
- `node --check frontend/js/main_enhanced.js`: passed.
- `python scripts/agent_status.py .agent/tasks`: passed.
- `python scripts/quality_gate.py phase3`: passed.
- `git diff --check`: passed.

### B. Real intraday blind-box startup
Request:
- Mode: `random`
- Period: `30m`
- Requested date range: `2024-01-01` through `2025-12-31`
- Limit: `150` trading days

Response:
- HTTP: 200
- Elapsed: 10.69 seconds
- Stock: `600000`
- Selected start: `2024-05-27 10:00:00`
- Planned cutoff: `2025-01-02 15:00:00`
- Context window: `2022-05-27 10:00:00` through `2024-05-27 10:00:00`
- Initial context bars: 3873
- Active period: `30m`
- Initial `finished`: false

The selected date is inside the requested range and has exactly two years of prior context.

### C. Trading-day semantics
The replay frame between the selected start and cutoff contained:
- 150 distinct data-bearing trading dates;
- 1200 normalized 30-minute bars.

This proves the limit is 150 trading dates rather than 150 base bars.

### D. 30-minute advancement
One explicit `/next` advanced:
- Before: `2024-05-27 10:00:00`
- After: `2024-05-27 10:30:00`
- Finished: false

### E. Four-period switching
A specified `600000` session started at `2025-07-14 10:00:00`. Switching through `4h_session`, `daily`, `weekly`, and back to `30m` kept `current_time` exactly `2025-07-14 10:00:00` for every response.

### F. Independent no-future attack
An active chart request manually supplied:
- Requested end: `2026-12-31 15:00:00`
- Replay current time: `2025-07-14 10:00:00`

Server response:
- HTTP: 200
- `read_only`: false
- Effective `window_end`: `2025-07-14 10:00:00`
- Maximum returned bar end: `2025-07-14 10:00:00`

No future bar or future OHLCV value was returned.

### G. Existing history compatibility
An older completed `600000` report containing date-level metadata reopened successfully through the new history chart route. The frontend used `start_date` and `end_date` as fallbacks when exact timestamp metadata was absent.

### H. Completed history after Flask restart
Random session `acceptance_tester_20260714_212343` was completed and persisted with:
- `data_mode=intraday_30m`
- `base_interval=30m`
- `period=30m`
- `training_start=2024-05-27 10:00:00`
- `training_end=2024-05-27 10:30:00`
- `max_training_days=150`
- `stock_code=600000`

After terminating all Flask Python processes and starting a new process:
- Active `/data`: HTTP 404, proving no in-memory session survived.
- History chart: HTTP 200.
- Read-only: true.
- Returned bars: 5816.
- Returned volume points: 5816.
- Window: `2022-05-27 10:00:00` through `2025-05-27 15:00:00`.
- `has_earlier=true`, `has_later=true`.

### I. Trade markers after restart
A second short session bought one hand at `2025-07-14 10:00:00`, completed, and was followed by another full Flask restart.

After restart:
- Active `/data`: HTTP 404.
- History chart: HTTP 200.
- Read-only: true.
- Returned bars: 5808.
- Trade markers: 1.
- Marker: `B` at `2025-07-14 10:00:00`.
- Stored `display_period`: `30m`.

### J. Browser read-only and year loading
The completed report opened from the acceptance user's history after restart. Browser evidence confirmed:
- replay and trading controls disabled;
- technical indicator selector disabled;
- earlier and later year controls visible only in read-only review;
- later-year click completed with status `已加载后一年的只读走势。`;
- no active training was required.

### K. Specified setup visibility
The `训练交易日限制（0=不限制）` input is visible in specified mode and blind-box mode. A browser-specified `600000`, `30m`, 5-trading-day session started at `2025-07-14 10:00:00` and advanced exactly to `10:30:00` after one explicit action.

## HTTP and Error Summary
- Unexpected HTTP 4xx: 0
- Unexpected HTTP 5xx: 0
- Expected 404 checks after restart: 2
- Expected validation 400 from an intentionally oversized 100-hand trade: 1; retry with 1 hand passed.
- Application console errors observed: 0
- One browser-harness Statsig telemetry timeout was external to the application and excluded.

## Final Assessment
Phase 5 meets the approved specification. Blind-box selection is operational from the local intraday cache pool, trading limits count actual trading dates, active windows prevent future leakage, completed history supports bidirectional loading after restart, older reports retain best-effort compatibility, and read-only review cannot trade.
