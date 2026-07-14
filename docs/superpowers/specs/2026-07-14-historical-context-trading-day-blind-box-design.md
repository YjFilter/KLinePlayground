# Historical Context, Trading-Day Limits, and Intraday Blind-Box Design

**Date:** 2026-07-14  
**Status:** Approved for implementation planning  
**Project:** KLinePlayground

## 1. Objective

Extend every training mode so users can inspect meaningful historical context without future leakage, interpret the training limit as real trading days, revisit completed sessions after a server restart, and use blind-box mode with the intraday replay engine.

The feature must support `30m`, `4h_session`, `daily`, and `weekly` while preserving one canonical 30-minute replay timeline.

## 2. User Semantics

### 2.1 Training-day limit

The existing UI label `K线数量限制（0=不限制）` becomes `训练交易日限制（0=不限制）`.

A value such as `150` means 150 distinct data-bearing trading dates, regardless of display period:

- `30m`: all revealed 30-minute bars within those 150 trading dates;
- `4h_session`: session candles spanning the same 150 trading dates;
- `daily`: 150 daily candles;
- `weekly`: weekly aggregation over the same 150 trading dates.

Weekends, holidays, suspensions, and dates without data do not consume the limit. Switching display period does not reset or reinterpret the limit. A value of zero means replay may continue to the latest available base timestamp.

### 2.2 Blind-box selection

Blind-box mode respects the selected sector, requested date range, trading-day limit, and display period.

The system:

1. obtains candidate stocks from the requested sector/universe;
2. excludes BaoStock-unsupported BSE prefixes `43`, `83`, `87`, and `92`;
3. loads or synchronizes normalized 30-minute data;
4. finds real data-bearing trading dates inside the requested date range;
5. randomly chooses a valid trading start date, not necessarily the beginning of the range;
6. requires sufficient future trading dates for the requested limit when the limit is non-zero;
7. requires at least two calendar years of prior market context; newly listed or incomplete candidates that cannot provide it are rejected;
8. retries another date or stock when a candidate is unusable.

If no valid candidate exists after a bounded number of attempts, the API returns an actionable error asking the user to widen the date range, reduce the trading-day limit, or change the sector. The system must not silently start with less than two years of prior context.

### 2.3 Initial historical context

Every new training session initially displays at least two calendar years of data before `training_start`, plus the candle at the current replay timestamp.

Historical context:

- is chart-only observation data;
- does not consume the training-day limit;
- does not alter cash, orders, positions, replay time, or statistics;
- must never include a timestamp later than the current replay time while training is active.

The selected display period is derived from the same 30-minute base data.

## 3. Chart Window Model

Each chart response uses an explicit window:

- `window_start`: earliest displayed timestamp;
- `window_end`: latest displayed timestamp;
- `training_start`: canonical replay start;
- `training_end`: final replay timestamp when completed, otherwise null;
- `current_time`: active replay timestamp;
- `has_earlier`: whether earlier data can be requested;
- `has_later`: whether later data can be requested in read-only review;
- `read_only`: whether post-training data is permitted.

During active training:

```text
window_end <= current_time
```

During completed-session review, the user may extend the window beyond `training_end`, but the report and trading state remain immutable.

## 4. Incremental Loading

### 4.1 Active training

The training screen exposes only `往前加载一年`.

Each request extends `window_start` backward by one calendar year. It does not call `/next`, advance the replay clock, or reveal later data. Newly returned bars are merged by timestamp and deduplicated.

### 4.2 Completed review

The completed-session chart initially displays:

```text
training_start - 2 calendar years ... training_end
```

It exposes:

- `往前加载一年`: extend earlier than the current `window_start`;
- `往后加载一年`: extend later than the current `window_end`, capped at the latest available market data.

Post-training bars are read-only context. They cannot change the original return, trades, account state, or report.

## 5. Historical Persistence and Rehydration

Historical chart access must not depend on `active_trainings` or an in-memory `KLineProcessorEnhanced`.

The saved session metadata must contain, where available:

- `session_id`;
- `user`;
- `stock_code` and stock name;
- `data_mode`;
- source/base interval;
- initial display period;
- `training_start` with full timestamp for intraday sessions;
- `training_end` with full timestamp;
- configured trading-day limit;
- trade details with `trade_time`, `display_period`, price, action, and quantity.

A history chart endpoint rehydrates market data from the shared cache/source and aggregates it on demand. Existing records receive best-effort compatibility using their available start/end dates and report details. Missing metadata produces a specific message rather than a generic full-data failure.

Proposed route:

```http
GET /api/users/{username}/history/{session_id}/chart
```

Query parameters:

```text
period=30m|4h_session|daily|weekly
range_start=YYYY-MM-DD
range_end=YYYY-MM-DD
```

The route returns chart bars, volume, trade markers, window metadata, and source metadata. It is read-only.

## 6. Active Training Chart API

The active intraday snapshot remains the authoritative replay state. Historical context is supplied through a separate read-only window endpoint or explicit window fields, so `session.snapshot()` stays focused on revealed replay state.

A proposed active route is:

```http
GET /api/training/{training_id}/chart-window
```

It accepts `period`, `range_start`, and `range_end`, but enforces `range_end <= current_time` server-side.

The frontend may combine the context window with the latest session snapshot. The server remains responsible for the no-future boundary.

## 7. Trading-Day Cutoff

The replay session records an ordered tuple of distinct trading dates from normalized base bars. Given a configured limit `N > 0`, the allowed timeline ends at the final base timestamp of the Nth trading date starting from the selected training date.

All replay periods share this cutoff. A daily or weekly advance cannot cross it. If a requested period boundary lies beyond the cutoff, the advance stops at the cutoff's final base timestamp and reports `finished`.

The cutoff must be tested for:

- single 30-minute advances;
- session/daily/weekly large steps;
- period switching;
- holidays and suspensions;
- a limit larger than remaining data;
- zero/unlimited mode.

## 8. Blind-Box API Contract

Starting `intraday_30m` with `mode=random` no longer requires the client to provide `stock_code` or `start_date`.

The request includes:

```json
{
  "mode": "random",
  "data_mode": "intraday_30m",
  "sector": "all",
  "date_start": "2024-01-01",
  "date_end": "2026-01-01",
  "max_training_days": 150,
  "period": "30m"
}
```

For backward compatibility, the backend may temporarily accept `max_bars`, but it must normalize it to `max_training_days` and interpret it as trading days for the new intraday mode.

The response includes the selected stock and real training timestamp only after a valid candidate has been chosen.

## 9. Frontend Behavior

### Setup

- Rename the limit label and helper text to trading days.
- Allow all four periods in specified and blind-box modes.
- Show the actual intraday source as BaoStock/cache instead of implying that the legacy AKShare selector supplies 30-minute bars.
- Remove the blind-box non-daily alert.
- Explain that the system selects a random real trading date inside the requested range.

### Active chart

- Render two years of prior context on start.
- Visually distinguish context before `training_start` from the active training range without hiding it.
- Provide `往前加载一年`.
- Keep later loading unavailable during active training.

### Completed review

- Use the historical chart API rather than `/training/{id}/full_data`.
- Render prior context, the complete training interval, and trade markers.
- Provide both one-year loading directions.
- Remain strictly read-only.

## 10. Data and Performance

The design reuses the existing normalized cache instead of storing duplicate multi-year chart arrays in every report.

Responses should request only the required date window. The frontend merges incremental pages by timestamp. The backend may cap individual windows when needed, but a two-year 30-minute context for one A-share is expected to be manageable.

Network synchronization failures may fall back to available cache when the requested start is covered, following the existing latest-available-data semantics.

## 11. Compatibility

- Existing legacy daily sessions continue to open through best-effort historical rehydration.
- Existing intraday sessions without full timestamps fall back to date boundaries.
- Existing `max_bars` values in legacy mode preserve their old behavior unless explicitly migrated.
- New intraday sessions use `max_training_days` semantics.
- BSE intraday remains unsupported until another source/import path is added.

## 12. Acceptance Criteria

1. Blind-box `30m`, `4h_session`, `daily`, and `weekly` sessions start successfully from a random real trading date within the requested range.
2. `150` limits replay to 150 distinct trading dates, not 150 displayed/base candles.
3. Every new session initially displays at least two years of prior context when data exists.
4. Active training can load one earlier year without advancing or leaking future data.
5. Completed review initially shows prior context plus the full training interval and trade markers.
6. Completed review can load one earlier or later year per action.
7. Historical charts work after server restart and do not require an active in-memory session.
8. Loading context never changes account, orders, trades, replay time, or report metrics.
9. Old records produce usable best-effort charts or specific metadata errors.
10. Focused API, replay, no-future-leakage, frontend, and browser acceptance tests pass.

## 13. Out of Scope

- Continuing to trade after a session has ended;
- rewriting original report performance using post-training data;
- BSE 30-minute sourcing;
- storing a separate full chart copy for every session;
- arbitrary custom window sizes beyond the one-year controls in this phase.
