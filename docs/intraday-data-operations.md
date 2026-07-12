# Intraday Data Operations Guide

This guide describes how to operate and maintain the Phase 1 intraday (30-minute) data
foundation of KLinePlayground. It covers live verification, optional cache creation,
cache layout, cache-first synchronization, validation failure behavior, the Beijing
Exchange limitation, and troubleshooting.

Every command and behavior below is confirmed by the current repository implementation
in `backend/intraday/` and `scripts/verify_baostock_30m.py`. No new behavior is designed
here. Where the code is the only source of truth, this document defers to the code.

## 1. Canonical 30-minute data format

The intraday layer normalizes every 30-minute bar to the following seven columns,
defined as `NORMALIZED_COLUMNS` in `backend/intraday/baostock_source.py`:

| Column    | Type      | Meaning                                                         |
| --------- | --------- | --------------------------------------------------------------- |
| `datetime`| timestamp | Bar close time,Asia/Shanghai timezone, formatted `%Y-%m-%d %H:%M:%S` in the cache CSV |
| `open`    | float     | Open price of the 30-minute bar                                 |
| `high`    | float     | High price of the 30-minute bar                                 |
| `low`     | float     | Low price of the 30-minute bar                                  |
| `close`   | float     | Close price of the 30-minute bar                                |
| `volume`  | float     | Trade volume of the bar (shares)                                |
| `amount`  | float     | Trade turnover of the bar (currency)                            |

Source data is fetched from BaoStock with `frequency="30"` and `adjustflag="3"`
(unadjusted). Numeric columns are coerced with `pandas.to_numeric(errors="coerce")`,
and rows are de-duplicated on `datetime` keeping the last occurrence, then sorted
ascending by `datetime`.

### Valid session timestamps

A complete A-share trading day has exactly eight 30-minute bars. The validator
(`backend/intraday/validator.py`) accepts only these close times:

```
10:00  10:30  11:00  11:30
13:30  14:00  14:30  15:00
```

A trading date whose observed set of `HH:MM` differs from this set is reported as
`incomplete_trading_day` (see section 7).

### Supported stock symbols

`_to_baostock_symbol` in `backend/intraday/baostock_source.py` accepts a bare 6-digit
numeric code (a `sh.`/`sz.` prefix is also tolerated and stripped) and maps it to a
BaoStock symbol:

- Codes starting with `5`, `6`, or `9` → Shanghai (`sh.<code>`), e.g. `600000`,
  `601318`, `688981`, `600519`.
- All other 6-digit codes → Shenzhen (`sz.<code>`), e.g. `000001`, `002594`,
  `300750`, `301308`.

Codes that are not exactly 6 digits or not purely numeric raise `ValueError`.

Codes starting with `43`, `83`, `87`, or `92` (Beijing Stock Exchange) raise
`IntradaySourceError` and are not supported. See section 6.

The pinned data source is `baostock==0.9.3` (see `requirements.txt`).

## 2. Live verification

The operator entry point is `scripts/verify_baostock_30m.py`. It logs in to BaoStock,
fetches 30-minute history for each requested code, validates it, and prints one JSON
summary object per code to stdout.

### Command shape

```
python scripts/verify_baostock_30m.py [--years YEARS] [--save-cache] [--cache-root CACHE_ROOT] stock_code [stock_code ...]
```

Options (confirmed by `--help` and `argparse` in the script):

| Argument        | Default          | Meaning                                                                 |
| --------------- | ---------------- | ----------------------------------------------------------------------- |
| `stock_codes`   | (required, 1+)   | One or more bare 6-digit A-share codes.                                 |
| `--years`       | `5`              | History window in years.                                                |
| `--save-cache`  | off              | If set, write the fetched frame to the cache for each valid code.       |
| `--cache-root`  | `data/intraday`  | Cache root directory used together with `--save-cache`.                 |

The verification window is computed from the current date: `end` is yesterday at
`23:59:59`, and `start` is `end` minus `--years` years (via `subtract_years`, which
handles leap-day overflow by falling back to February 28).

### Verifying a single stock

```
python scripts/verify_baostock_30m.py 600000
```

This fetches the default five-year 30-minute window for `600000` (Shanghai Pudong
Development Bank) and prints a JSON summary. Exit code is `0` when the summary is
valid, `1` otherwise.

### Verifying the three representative stocks

This is the canonical five-year check referenced by `.agent/QUALITY_GATES.md` and
recorded in `.agent/STATE.md`:

```
python scripts/verify_baostock_30m.py --years 5 600000 600519 300750
```

It covers one Shanghai main-board blue chip (`600000`), one Shanghai main-board
consumer name (`600519`), and one Shenzhen ChiNext name (`300750`). In the recorded
Phase 1 evidence each returned 9,688 rows across 1,211 trading days with zero
validation issues.

### Summary object fields

Each printed JSON object contains exactly these keys:

| Key             | Meaning                                                                                  |
| --------------- | ---------------------------------------------------------------------------------------- |
| `stock_code`    | The code as passed on the command line.                                                  |
| `rows`          | Number of bars returned by BaoStock.                                                     |
| `first`         | ISO timestamp of the earliest bar, or `null` if empty.                                   |
| `last`          | ISO timestamp of the latest bar, or `null` if empty.                                     |
| `trading_days`  | Count of distinct trading dates in the frame.                                            |
| `coverage_days` | Calendar-day span `(last - first).days`, or `0` if empty.                                |
| `issues`        | Object mapping validation issue code → count (sorted). Empty when valid.                 |
| `valid`         | `true` only if the frame is non-empty, validation passes, and coverage is sufficient.    |

A frame is marked `valid: false` if any of these hold:

1. The frame is empty (BaoStock returned no rows).
2. `validate_30m_frame` reports one or more issues (see section 7).
3. `coverage_days < years * 365 - 21` (the `years_to_minimum_days` threshold).

When the script catches an exception for a code (for example a Beijing Exchange
rejection or a network error), it prints `{"stock_code": ..., "valid": false,
"error": "<message>"}` and continues with the next code. The process exit code is `1`
if any code failed, `0` otherwise.

## 3. Optional cache creation with `--save-cache`

`--save-cache` writes the freshly fetched, validated frame to the on-disk cache. It
interacts with the cache as follows (confirmed in `scripts/verify_baostock_30m.py`
and `backend/intraday/cache.py`):

- Saving happens **only for valid codes**. A code with `valid: false` is skipped even
  when `--save-cache` is set; no partial or invalid frame is written.
- The frame is re-validated with `validate_30m_frame` immediately before saving.
- `cache.save` normalizes the passed frame (de-duplicate on `datetime` keeping last,
  sort ascending) and writes it via a `.csv.tmp` file that is atomically renamed to
  the final path. The existing cache file for that code is **replaced** with the
  freshly fetched `--years` window; it is not merged with prior cache contents.
- A matching metadata JSON file is written atomically in the same step.

`--cache-root` selects the root directory for the cache. The default is the relative
path `data/intraday`, resolved against the current working directory of the process.

### Cache layout

```
<cache-root>/
  30m/
    <stock_code>.csv      # normalized 30-minute bars (columns from section 1)
  metadata/
    <stock_code>.json     # cache metadata for the same code
```

The data CSV uses the seven canonical columns with `datetime` formatted as
`%Y-%m-%d %H:%M:%S` and no row index.

The metadata JSON contains exactly these fields:

| Field          | Meaning                                                                                  |
| -------------- | ---------------------------------------------------------------------------------------- |
| `stock_code`   | The cached code.                                                                         |
| `interval`     | Always `"30m"`.                                                                          |
| `source`       | Always `"baostock"` (as passed by both the verify script and the service).              |
| `range_start`  | ISO timestamp of the earliest cached bar, or `null` if the cache is empty.              |
| `range_end`    | ISO timestamp of the latest cached bar, or `null` if the cache is empty.                |
| `updated_at`   | ISO timestamp (seconds precision) of the save.                                           |
| `rows`         | Number of cached bars.                                                                   |
| `validation`   | Object mapping validation issue code → count for the saved frame (sorted). Empty when valid. |

### Example: build the cache for the three representative stocks

```
python scripts/verify_baostock_30m.py --years 5 --save-cache 600000 600519 300750
```

This produces, under `data/intraday/` (or the configured `--cache-root`), six files:
`30m/600000.csv`, `metadata/600000.json`, and so on for `600519` and `300750`.

To use a custom location, for example an external drive:

```
python scripts/verify_baostock_30m.py --years 5 --save-cache --cache-root D:/kline-cache 600000
```

## 4. Cache-first synchronization behavior

`backend/intraday/service.py` (`IntradayDataService`) is the runtime read path. Its
`get_30m(stock_code, start, end)` method is cache-first:

1. It loads `cache.coverage(stock_code)`, which returns the `[range_start, range_end]`
   span of the existing cache file, or `None` if no cache exists.
2. If coverage exists **and fully covers** `[start, end]`, the service returns a slice
   from the cache only. **No network call is made.** This is the cache-first path.
3. Otherwise it calls `sync_30m`, which:
   - Loads any existing cached frame.
   - Computes the missing ranges relative to current coverage:
     - `(start, coverage.start - 30 minutes)` if `start` is before the cache start.
     - `(coverage.end + 30 minutes, end)` if `end` is after the cache end.
     - If no cache exists, the whole `(start, end)` range is fetched.
   - Fetches each missing range from `BaoStockSource.fetch_30m`.
   - Validates each incoming range with `validate_30m_frame`.
   - Merges incoming ranges into the existing frame with `cache.merge`
     (concatenate, de-duplicate on `datetime` keeping last, sort ascending).
   - Re-validates the merged frame.
   - Persists the merged frame with `cache.save` only when at least one range was
     fetched.
4. After sync, the service re-checks coverage. If the cache still does not cover
   `[start, end]`, it raises `IntradayDataUnavailable`.

The merge keeps the **last** value for any duplicated timestamp, so newly fetched bars
take precedence over previously cached bars for the same timestamp.

## 5. Validation failure behavior

Validation is performed by `validate_30m_frame` in `backend/intraday/validator.py`.
Failure handling differs by entry point but is consistent in one rule: **invalid data
is never written to the cache.**

### In the verify script (`scripts/verify_baostock_30m.py`)

- If `validate_30m_frame` reports any issue, `summary["valid"]` is `false`, the process
  exit code becomes `1`, and `--save-cache` is skipped for that code.
- The `issues` object in the printed summary lists each issue code and its count.

### In the service (`IntradayDataService.sync_30m`)

- If an **incoming** range fails validation, the service raises
  `IntradayDataUnavailable` with the failing issue codes and **does not save**.
- If the **merged** frame fails validation, the service raises
  `IntradayDataUnavailable` with the failing issue codes and **does not save**.
- If the source raises any other exception (for example a network error), the service:
  - Returns the cached slice if the existing cache now covers `[start, end]`.
  - Otherwise raises `IntradayDataUnavailable` with the cache coverage span and the
    original source error.

`IntradayDataUnavailable` is a `RuntimeError` subclass; callers are expected to catch
it and surface a user-facing message rather than retry blindly.

## 6. Beijing Exchange limitation and safe response

BaoStock 0.9.3 does not provide 30-minute data for Beijing Stock Exchange (BSE) names.
`_to_baostock_symbol` rejects BSE codes explicitly: any 6-digit code starting with
`43`, `83`, `87`, or `92` raises `IntradaySourceError` with the message
`BaoStock does not provide Beijing Stock Exchange 30m data: <code>`.

This is the current safe response:

- The rejection happens **before** any BaoStock login or query, so no partial session
  is left open and no malformed frame is produced.
- In the verify script the exception is caught and printed as
  `{"stock_code": ..., "valid": false, "error": "..."}`; the process exit code is `1`.
- In the service the exception propagates into the `except Exception` branch of
  `sync_30m` and is converted to `IntradayDataUnavailable`.

There is currently **no fallback source** for BSE 30-minute data. Operators should not
attempt BSE codes through this pipeline. A future fallback source or import path is
required before BSE replay can be supported (tracked as a known limitation in
`.agent/STATE.md`).

## 7. Validation issue reference

`validate_30m_frame` emits issue codes from `backend/intraday/validator.py`. Each issue
also carries a human-readable message and, where applicable, the offending timestamp.

| Code                      | Triggered when                                                                                       |
| ------------------------- | ---------------------------------------------------------------------------------------------------- |
| `missing_columns`         | Any of the seven canonical columns is absent. Returned alone; no further checks run.                 |
| `duplicate_timestamp`     | Two or more rows share the same `datetime`. One issue per duplicated timestamp.                      |
| `invalid_ohlc`            | `high < max(open, close, low)`, or `low > min(open, close, high)`, or any OHLC field is NaN.         |
| `invalid_volume`          | `volume` is null or nonnumeric. One issue per offending bar.                                         |
| `negative_volume`         | `volume < 0`. One issue per offending bar.                                                           |
| `invalid_amount`          | `amount` is null or nonnumeric. One issue per offending bar.                                         |
| `negative_amount`         | `amount < 0`. One issue per offending bar.                                                           |
| `illegal_session_time`    | A bar's `HH:MM` is not one of the eight valid session times in section 1.                            |
| `incomplete_trading_day`  | A trading date's observed set of `HH:MM` differs from the eight valid times. Reports missing/extra. |

A frame with no issues has `ValidationResult.is_valid == True` and an empty `issues`
list.

## 8. Troubleshooting

### Network failure

Symptom: the verify script prints `{"stock_code": ..., "valid": false, "error": "..."}`
with a BaoStock login or query error; the service raises `IntradayDataUnavailable`
referencing `source_error`.

What the code does: `BaoStockSource.fetch_30m` raises `IntradaySourceError` if
`api.login()` returns a non-zero `error_code`, or if
`api.query_history_k_data_plus` returns a non-zero `error_code`. The service wraps any
non-validation exception and, if the existing cache still covers the requested range,
returns the cached slice instead of failing.

Operator response:

1. Confirm network connectivity to BaoStock and retry the verify command for the
   affected code.
2. If a cache exists and covers the requested range, runtime reads continue to work
   from the cache; no action is required for read-only use.
3. If no cache exists or the cache does not cover the range, the request cannot be
   satisfied until BaoStock is reachable again. Do not manually edit cache files.

### Insufficient coverage

Symptom: the verify script prints a summary with `valid: false` and a non-empty
`issues` map, **or** with `coverage_days` below the `years * 365 - 21` threshold; the
service raises `IntradayDataUnavailable` with a `cache=...` span that does not cover
the request.

What the code does: the verify script marks a frame invalid when coverage is shorter
than the minimum day threshold even if every bar is individually valid. The service
re-checks coverage after sync and refuses to return data that does not cover the
requested range.

Operator response:

1. Re-run the verify script with the same `--years` to refresh the window; BaoStock
   may have back-filled the gap.
2. If the gap is at the recent end, confirm the requested `end` date is not in the
   future and that the market has actually traded through that date.
3. Use `--save-cache` only after the summary is `valid: true`, so the cache is not
   left in a partial state from this entry point. (The service never saves on
   validation failure.)

### Invalid data

Symptom: the verify summary or the service error mentions one or more issue codes
from section 7 (for example `duplicate_timestamp`, `invalid_ohlc`,
`illegal_session_time`, `incomplete_trading_day`).

What the code does: both the verify script and the service treat any non-empty issue
list as a hard failure. The verify script sets `valid: false` and skips
`--save-cache`. The service raises `IntradayDataUnavailable` and does not save.

Operator response:

1. Do not attempt to repair cache files by hand. The cache is written atomically and
   its metadata records the last validation result; manual edits break this contract.
2. Re-run the verify script for the affected code. Transient source issues sometimes
   resolve on retry.
3. If invalid data persists for the same code and window, record the code, the
   `--years` value, and the exact issue codes, and escalate as a source-data defect.
   Do not broaden `VALID_30M_TIMES` or relax the validator to make the data pass;
   those are trading-invariant checks owned by Codex.

### Beijing Exchange codes

Symptom: the verify script prints `valid: false` with
`error: "BaoStock does not provide Beijing Stock Exchange 30m data: <code>"` for any
code starting with `43`, `83`, `87`, or `92`.

Operator response: do not retry; this is an explicit, by-design rejection. Exclude
BSE codes from intraday verification and runtime reads until a fallback source is
introduced (see section 6).

## 9. Exit code reference

| Entry point                         | Exit code | Meaning                                                                 |
| ----------------------------------- | --------- | ----------------------------------------------------------------------- |
| `verify_baostock_30m.py`            | `0`       | Every requested code produced a `valid: true` summary.                  |
| `verify_baostock_30m.py`            | `1`       | At least one code was invalid, raised an exception, or was a BSE code.  |
| `quality_gate.py control-plane`     | `0`       | All control-plane commands passed.                                      |
| `quality_gate.py control-plane`     | non-zero  | A control-plane command failed; see the `[quality] FAIL` line for which. |

## 10. Required commands for this guide

The following commands are the ones an operator runs day-to-day. They are identical to
those listed in `.agent/QUALITY_GATES.md` and the Phase 1 evidence in
`.agent/STATE.md`.

```
# Inspect the verify script interface
python scripts/verify_baostock_30m.py --help

# Verify a single stock over the default five-year window
python scripts/verify_baostock_30m.py 600000

# Verify the three representative stocks over five years
python scripts/verify_baostock_30m.py --years 5 600000 600519 300750

# Build the cache for the three representative stocks
python scripts/verify_baostock_30m.py --years 5 --save-cache 600000 600519 300750

# Build the cache at a custom location
python scripts/verify_baostock_30m.py --years 5 --save-cache --cache-root D:/kline-cache 600000

# Run the control-plane quality profile (required for documentation-only changes)
python scripts/quality_gate.py control-plane
```

The optional live five-year verification command in `.agent/QUALITY_GATES.md` is
network-dependent and is not required for offline operation:

```
python scripts/verify_baostock_30m.py --years 5 600000 600519 300750
```
