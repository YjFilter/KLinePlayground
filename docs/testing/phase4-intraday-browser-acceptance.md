# TASK-014 Intraday Browser Acceptance Report

- **Task ID:** TASK-014
- **Title:** Perform independent intraday browser acceptance
- **Status:** Completed with failures
- **Date:** 2026-07-13
- **Tester:** WorkBuddy (independent acceptance)
- **Final verdict:** **FAIL** — 8 Pass / 2 Fail / 0 Blocked (after runtime workaround of 2 production bugs that block startup)

## 1. Test Environment

| Item | Value |
| --- | --- |
| Project root | `E:\Desktop\01_TODO\mimo\KLinePlayground` |
| Server URL | `http://127.0.0.1:5000/` |
| Backend entry | `backend/app_enhanced.py` (Flask, debug=False) |
| Frontend entry | `frontend/index_enhanced.html` (served by Flask static handler) |
| Python runtime | `C:\Users\1111\AppData\Local\Programs\Python\Python311\python.exe` (3.11.9) |
| Browser automation | `playwright-cli` (Chromium) |
| OS | Windows (win32) |
| BaoStock availability | Available (login + query OK) |
| Cache coverage | 600000 30m: 2024-01-02 10:00:00 .. 2026-07-10 15:00:00 (4872 rows) |
| Real wall-clock date | 2026-07-13 (BaoStock 30m data lags ~3 days behind) |

### Startup command (with runtime patches)

The production Flask entry `backend/app_enhanced.py` was launched through an
external launcher script placed OUTSIDE the production codebase
(`E:\Desktop\01_TODO\trding\.scratch\task014_launcher.py`). The launcher
applies two runtime monkey-patches to work around two production bugs (see
Section 10 for details). No production file was modified.

```bash
cd "E:/Desktop/01_TODO/mimo/KLinePlayground"
PYTHONPATH="E:/Desktop/01_TODO/mimo/KLinePlayground" \
  C:/Users/1111/AppData/Local/Programs/Python/Python311/python.exe \
  "E:/Desktop/01_TODO/trding/.scratch/task014_launcher.py"
```

The launcher:
1. Replaces `backend.app_enhanced.datetime` with a subclass whose `now()`
   returns the fixed timestamp `2026-07-10 15:00:00` so that the hard-coded
   `end_dt = datetime.now()` inside `_start_intraday_training` falls inside
   the 30m cache coverage.
2. Replaces `IntradayDataService.get_30m` with a cache-first slice that
   returns cache data directly when the cache is non-empty, bypassing the
   broken `coverage.covers(start, end)` check in
   `backend/intraday/service.py:30`.

`debug=False` is used to avoid the Werkzeug reloader fork (which would
re-import the production module from scratch and lose the patches).

Without these two runtime patches, intraday_30m training can NEVER start
today because:
- BaoStock 30m data lags ~1-3 days behind the wall-clock date, and
- `end_dt = datetime.now()` is hard-coded in
  `backend/app_enhanced.py:502`, so the cache can never cover `end_dt`,
  and
- `coverage.covers(start, end)` in
  `backend/intraday/models.py:14-15` checks
  `self.start <= start and self.end >= end`, but `cache.start = 10:00`
  always exceeds `start = 00:00` (because `_parse_start_date` zeroes the
  time component), so the cache is never considered to "cover" the
  request.

These two bugs are documented as findings in Section 10.

## 2. Test Data

| Item | Value |
| --- | --- |
| Stock code | `600000` (Shanghai Pudong Development Bank, main board) |
| Start date | `2024-01-02` |
| Data source | `baostock` (intraday_30m) / `akshare` (legacy_daily) / `offline` (600519) |
| Initial capital | ¥100,000 |
| Training ID (all sessions) | `acceptance_tester_20260710_150000` (because datetime is patched to a fixed timestamp, all sessions share this ID; new sessions overwrite the previous one in `active_trainings`) |
| Test user | `acceptance_tester` |
| Beijing Stock Exchange codes | Not used (no 43/83/87/92 prefixes) |

## 3. Scenario Pass/Fail/Blocked Summary

| ID | Scenario | Result | Notes |
| --- | --- | --- | --- |
| A.1 | Start 30m | Pass (with launcher patch) | First real timestamp shown, no auto-advance |
| A.2 | Start 4h_session | Pass (with launcher patch) | First real timestamp, next_boundary = 15:00 |
| A.3 | Start daily | Pass (with launcher patch) | First real timestamp, next_boundary = 15:00 |
| A.4 | Start weekly | Pass (with launcher patch) | First real timestamp, next_boundary = next Friday 15:00 |
| B | Continue (30m) | Pass | 10:00 → 10:30, exactly one /next request |
| C | Period switching | Pass | current_time unchanged across all 4 switches, only /period used |
| D.1 | Advance in 4h_session | Pass | 10:30 → 15:00 (session boundary) |
| D.2 | Advance in daily | Pass | 2024-01-02 15:00 → 2024-01-03 15:00 (next day close) |
| D.3 | Advance in weekly | Pass | 2024-01-03 15:00 → 2024-01-05 15:00 (Friday close) |
| E | Status display & CSS classes | Pass | `bar-status-complete` / `incomplete-candle bar-status-incomplete` switch correctly |
| F | Market buy | Pass (via API; UI flow blocked by trade-reason modal + currentTraining scope) | Filled at base bar close ¥6.59, account/pending orders updated |
| G | Reset | Pass (via API) | Restores initial time, period, account, pending orders, trade history |
| H | Playback | **FAIL** | Concurrent /next requests cause 500 "cannot advance a stale replay plan" errors; pause does not stop in-flight requests |
| I.1 | Random + daily (legacy path) | Pass | /start returns 200, /data returns legacy_daily structure |
| I.2 | Random + non-daily | Pass | Front-end alert "盲盒模式目前仅支持日线启动…" blocks /start |
| J | Browser console & network | **FAIL** | 158 "获取下一根K线失败" errors, 18 "intraday next 失败" errors, 18 HTTP 500 responses |

**Totals: 8 Pass / 2 Fail / 0 Blocked**

## 4. Continue and Period-Switch Timestamps

### Scenario B — Continue in 30m

| Step | current_time | next_boundary | status |
| --- | --- | --- | --- |
| Before click | 2024-01-02 10:00:00 | 2024-01-02 10:30:00 | 已收盘 |
| After click | 2024-01-02 10:30:00 | 2024-01-02 11:00:00 | 已收盘 |

Network evidence: exactly 1 POST `/api/training/{id}/next` (903 ms).

### Scenario C — Period switching

| Switch | Before current_time | After current_time | After next_boundary | After status |
| --- | --- | --- | --- | --- |
| 30m → daily | 2024-01-02 10:30:00 | 2024-01-02 10:30:00 (unchanged) | 2024-01-02 15:00:00 | 未收盘 |
| daily → 4h_session | 2024-01-02 10:30:00 | 2024-01-02 10:30:00 (unchanged) | 2024-01-02 15:00:00 | 未收盘 |
| 4h_session → weekly | 2024-01-02 10:30:00 | 2024-01-02 10:30:00 (unchanged) | 2024-01-05 15:00:00 | 未收盘 |
| weekly → 30m | 2024-01-02 10:30:00 | 2024-01-02 10:30:00 (unchanged) | 2024-01-02 11:00:00 | 已收盘 |

Network evidence across all 4 switches: 0 new `/next` requests; 8
`/period` requests total (front-end appears to issue 2 per switch —
likely one to switch and one to refresh snapshot). Method = `POST`.

### Scenario D — Advance per period

| Step | Before current_time | After current_time | After next_boundary | After status |
| --- | --- | --- | --- | --- |
| D.1 4h_session click | 2024-01-02 10:30:00 | 2024-01-02 15:00:00 (session boundary) | 2024-01-03 15:00:00 | 已收盘 |
| D.2 daily click | 2024-01-02 15:00:00 | 2024-01-03 15:00:00 (next day close) | 2024-01-04 15:00:00 | 已收盘 |
| D.3 weekly click | 2024-01-03 15:00:00 | 2024-01-05 15:00:00 (Friday close) | 2024-01-12 15:00:00 | 已收盘 |

## 5. Key HTTP Requests

| Method | Path | Status | Notes |
| --- | --- | --- | --- |
| POST | `/api/users` (body: `{"username":"acceptance_tester"}`) | 200 | User created |
| GET | `/api/users` | 200 | Returns 4 users |
| GET | `/api/health` | 200 | `{"active_trainings":N,"status":"ok","timestamp":"2026-07-10T15:00:00"}` (timestamp frozen by launcher patch) |
| POST | `/api/training/start` (30m, intraday_30m, 600000, 2024-01-02) | 200 | Returns top-level snapshot with `data_mode=intraday_30m`, `current_time`, `next_boundary`, `kline_data`, `current_base_bar`, `current_bar_complete`, `available_periods` |
| POST | `/api/training/start` (4h_session / daily / weekly) | 200 | Same shape; only `active_period`, `kline_data[0].period`, `next_boundary`, `current_bar_complete` differ |
| GET | `/api/training/{id}/data` | 200 | Returns same snapshot shape as start response |
| POST | `/api/training/{id}/next` | 200 (single click) | Returns `{"finished":false,"data_mode":"intraday_30m","snapshot":{...},"order_events":[],"completed_times":[...],"pending_orders":{...}}` |
| POST | `/api/training/{id}/next` | **500** (during playback) | `{"error":"cannot advance a stale replay plan"}` |
| POST | `/api/training/{id}/period` (body: `{"period":"daily"}`) | 200 | Returns top-level snapshot with `active_period` updated; `current_time` unchanged |
| POST | `/api/training/{id}/trade` (market buy 100) | 200 | `{"success":true,"trade":{...},"pending_orders":{...},"data_mode":"intraday_30m"}` |
| GET | `/api/training/{id}/account` | 200 | `{"available_cash":34080.23,"position_value":65900.0,"total_assets":99980.23,"position_summary":{...},"pending_orders":{...},"active_period":"30m","current_time":...,"next_boundary":...,"finished":false}` |
| POST | `/api/training/{id}/reset` | 200 | `{"message":"训练已重置","snapshot":{...},"data_mode":"intraday_30m"}` |
| GET | `/api/training/{id}/trade_records` | 200 | `[]` after reset |
| POST | `/api/training/start` (random + daily, legacy_daily) | 200 | `{"data_source":"akshare","id":"...","mode":"random","period":"daily","start_date":"2024-12-21","stock_code":"300332"}` — no `data_mode` field, confirming legacy path |
| GET | `/api/training/{id}/data?view_period=daily` (legacy) | 200 | Returns `kline_data`, `volume_data`, `ma_data`, `progress`, `trade_markers`, `period`, `view_period`, `data_source`, `stock_name` — legacy shape, no `data_mode` |

## 6. Response-Shape Observations

### `/start` (intraday_30m)

Top-level snapshot fields:
- `id`, `data_mode` (`intraday_30m`), `stock_code`, `mode`, `data_source`,
  `initial_capital`
- `active_period`, `available_periods` (`["30m","4h_session","daily","weekly"]`),
  `base_interval` (`30m`)
- `current_time` (`"YYYY-MM-DD HH:MM:SS"`), `next_boundary` (same format or null),
  `finished` (bool), `current_bar_complete` (bool)
- `kline_data` (list of aggregated bar dicts with `period`, `start_time`,
  `end_time`, `open`, `high`, `low`, `close`, `volume`, `amount`,
  `source_bar_count`, `complete`)
- `current_base_bar` (the underlying 30m bar at `current_time`)

### `/start` (legacy_daily)

Returns only: `id`, `stock_code`, `start_date`, `mode`, `data_source`,
`period`. No snapshot — the front-end must call `/data` separately.

### `/next`

Intraday returns:
```json
{
  "finished": false,
  "data_mode": "intraday_30m",
  "snapshot": { ... same shape as /start top-level snapshot ... },
  "order_events": [],
  "completed_times": ["2024-01-02 10:30:00", ...],
  "pending_orders": { "buy_orders": [], "exit_orders": [] }
}
```

When finished: `{"finished": true, "data_mode": "intraday_30m", "report": {...}}`.

### `/period`

Returns the same top-level snapshot as `/start` (with `active_period`
updated). Does NOT include `order_events` or `completed_times`.

### `/reset`

Returns:
```json
{
  "message": "训练已重置",
  "snapshot": { ... same shape as /start top-level snapshot ... },
  "data_mode": "intraday_30m"
}
```

### `/trade` (intraday_30m, market buy)

```json
{
  "success": true,
  "trade": {
    "action": "buy",
    "quantity": 100,
    "price": 6.59,
    "amount": 65900.0,
    "commission": 19.77,
    "stamp_tax": 0.0,
    "net_amount": 65919.77,
    "bar_id": 40,
    "trade_date": "2024-01-08",
    "trade_time": "2024-01-08 15:00:00",
    "display_period": "30m",
    "stock_code": "600000",
    "reason": "...",
    "timestamp": "2026-07-13T13:50:11.937721"
  },
  "pending_orders": { "buy_orders": [], "exit_orders": [] },
  "data_mode": "intraday_30m"
}
```

`trade_time` is the full `YYYY-MM-DD HH:MM:SS` of the current base bar
(not just the date), and `display_period` echoes the active period — both
required for minute-level replay to support multiple independent trades
on the same day.

### `/account` (intraday_30m)

Returns legacy account fields plus:
- `data_mode: "intraday_30m"`
- `current_time`, `active_period`, `next_boundary`, `finished`
- `pending_orders` (embedded)

## 7. Browser Console Errors

Captured at end of session via `playwright-cli console`:

| Count | Message | Source |
| --- | --- | --- |
| 158 | `[ERROR] 获取下一根K线失败: Error: intraday 训练数据为空` | `main_enhanced.js:2962` (via `applyIntradaySnapshot` at `main_enhanced.js:158`) |
| 18 | `[ERROR] intraday next 失败: {error: cannot advance a stale replay plan}` | `main_enhanced.js:2876` |
| 18 | `[ERROR] Failed to load resource: the server responded with a status of 500 (INTERNAL SERVER ERROR) @ /api/training/{id}/next` | network |
| 1 | `[ERROR] 获取下一根K线失败: Error: Cannot update oldest data, last time=[object Object], new time=[object Object]` | `lightweight-charts.standalone.production.js:7:131240` (via `nextBar` at `main_enhanced.js:2918`) |

### Root causes

1. **"cannot advance a stale replay plan" (18 errors)** — Scenario H
   playback. `setInterval(nextBar, 500)` fires the next tick before the
   previous `nextBar()` Promise resolves. Two concurrent `/next` requests
   reach the Flask server (which runs threaded). Both call
   `session.advance()`; the second one's `plan.current_time` no longer
   matches `clock.current_time` because the first one already advanced
   it, triggering `ValueError("cannot advance a stale replay plan")` in
   `backend/intraday/replay_clock.py:105`.

2. **"intraday 训练数据为空" (158 errors)** — After Scenario I.1 started
   a `legacy_daily` random session via API (which overwrote the intraday
   session because all sessions share the same patched `training_id`),
   the front-end's `currentTraining` object still referenced the old
   `intraday_30m` snapshot. Subsequent `nextBar()` calls went through the
   intraday branch, fetched `/next`, and the response could not be
   applied because the intraday kline_data was empty. This is a
   front-end state staleness bug, NOT a back-end bug.

3. **"Cannot update oldest data" (1 error)** — Lightweight-charts library
   error when trying to update a bar with a timestamp older than the
   last bar. Likely a side effect of the staleness above.

## 8. Network Failed Requests

| Count | Method | Path | Status | Response body |
| --- | --- | --- | --- | --- |
| 18 | POST | `/api/training/{id}/next` | 500 | `{"error":"cannot advance a stale replay plan"}` |

All 18 failures occurred during Scenario H playback. No 4xx errors. No
404 errors. No other 5xx errors.

Additional observation: during playback, `/next` request durations
reached 72-79 seconds because Flask's threaded mode queued concurrent
requests while the in-flight `nextBar()` was still processing. The
front-end kept firing new `/next` calls every 500 ms, building up a
backlog.

## 9. Reproducible Failure Steps

### Failure H-1: Playback produces 500 "stale replay plan"

1. Launch the patched Flask server (see Section 1).
2. Open `http://127.0.0.1:5000/` in Chromium via `playwright-cli open`.
3. Log in as `acceptance_tester`.
4. Click "新建训练" → 指定模式 → fill `600000` / `2024-01-02` / 30分钟 →
   click "开始训练". Wait for the chart to render at
   `2024-01-02 10:00:00`.
5. Set playback speed to `0.5 s/bar`.
6. Click the play/pause button (`#play-pause-btn`).
7. Wait ~3 seconds.
8. Open DevTools Console.

Expected: chart advances one 30m bar every 0.5 s, no errors.
Actual: console floods with
`[ERROR] intraday next 失败: {error: cannot advance a stale replay plan}`
and DevTools Network shows HTTP 500 responses on `/next`.

Root cause: `frontend/js/main_enhanced.js:2845`
`playbackInterval = setInterval(nextBar, interval);` does not await the
previous `nextBar()` Promise. `backend/intraday/replay_clock.py:99-110`
`advance(plan_or_target)` rejects any plan whose `current_time` no longer
matches `self.current_time`. With Flask threaded mode, two concurrent
`/next` calls race and the loser raises.

### Failure J-1: Front-end keeps intraday path after legacy_daily overwrite

1. After Scenario H, start a `legacy_daily` random session via API:
   `POST /api/training/start` with `{"mode":"random","data_mode":"legacy_daily","period":"daily",...}`.
   Because `datetime.now()` is patched, the new session gets the same
   `training_id` as the previous intraday session and overwrites it in
   `active_trainings`.
2. The front-end's `currentTraining` variable still references the old
   intraday snapshot (it is a module-scoped `let` in
   `main_enhanced.js`, not re-fetched).
3. Press the spacebar or click "下一根K线".

Expected: front-end detects `data_mode !== 'intraday_30m'` and calls
the legacy `/next` path.
Actual: front-end still calls the intraday `/next` branch, response
snapshot is empty, console logs
`[ERROR] 获取下一根K线失败: Error: intraday 训练数据为空` 158 times.

Note: this is a secondary failure triggered by the test harness using
the same `training_id` for two different data modes. In normal user
flow (without the launcher patch), `training_id` includes the real
wall-clock timestamp and collisions do not occur. The bug is therefore
a test-harness artifact, but it reveals that the front-end has no
defensive check when the back-end session is silently replaced.

## 10. External Blockers & Production Bug Findings

### 10.1 External BaoStock / network availability

BaoStock was reachable throughout the test:
- `bs.login()` returned `error_code=0`
- `bs.query_history_k_data_plus()` for `sh.600000` 30m bars returned 8
  rows per trading day as expected.

No external BaoStock or network blocker occurred. The intraday_30m
startup failure (Section 1) is caused by production code bugs, NOT by
BaoStock unavailability.

### 10.2 Production bug #1 — `end_dt = datetime.now()` hard-coded

File: `backend/app_enhanced.py:502`

```python
def _start_intraday_training(...):
    ...
    end_dt = datetime.now()  # hard-coded
    try:
        service = _get_intraday_data_service()
        base_bars = service.get_30m(stock_code, start_dt, end_dt)
    except Exception as e:
        return jsonify({'error': f'intraday 数据加载失败: {e}'}), 400
```

Impact: BaoStock 30m data typically lags 1-3 days behind the wall-clock
date. When `datetime.now()` exceeds the cache coverage end,
`IntradayDataService.get_30m` raises `IntradayDataUnavailable` and the
start endpoint returns HTTP 400. Any user who tries to start an
intraday_30m session on a day when BaoStock has not yet published data
will see:

```
{"error":"intraday 数据加载失败: 30m data unavailable for 600000 2024-01-02..2026-07-13; cache=2024-01-02T10:00:00..2026-07-10T15:00:00"}
```

Recommended fix: accept an optional `end_date` parameter from the
request, or fall back to `cache.coverage.end` when `datetime.now()`
exceeds cache coverage.

### 10.3 Production bug #2 — `coverage.covers` rejects valid cache

File: `backend/intraday/models.py:14-15`

```python
def covers(self, start: datetime, end: datetime) -> bool:
    return self.start <= start and self.end >= end
```

File: `backend/intraday/service.py:28-32`

```python
def get_30m(self, stock_code, start, end):
    coverage = self.cache.coverage(stock_code)
    if coverage and coverage.covers(start, end):
        return self._slice(self.cache.load(stock_code), start, end)
    return self.sync_30m(stock_code, start, end)
```

Impact: `_parse_start_date` (in `backend/app_enhanced.py:101-103`)
zeroes the time component:

```python
def _parse_start_date(start_date_str):
    return datetime.strptime(start_date_str, '%Y-%m-%d')  # 00:00:00
```

But BaoStock 30m bars begin at 10:00, so `cache.start = 10:00` and
`start = 00:00`. `self.start <= start` evaluates to
`10:00 <= 00:00` → `False`, so `coverage.covers` always returns False
even when the cache has data for the requested date. The code then
calls `sync_30m`, which queries BaoStock, merges, re-validates with
the same broken `covers` check, and raises `IntradayDataUnavailable`.

This bug exists independently of bug #1. Even if `end_dt` were
correctly bounded, `start = 00:00` would still fail the coverage check.

Recommended fix: either align `start` to the first 30m bar at or after
`start_dt` before calling `covers`, or relax `covers` to compare dates
only (not sub-day timestamps), or change `_parse_start_date` to return
the first 30m bar's timestamp.

### 10.4 Production bug #3 — Playback race condition (Scenario H)

File: `frontend/js/main_enhanced.js:2837-2846`

```js
function startPlayback() {
    isPlaying = true;
    ...
    playbackInterval = setInterval(nextBar, interval);
}
```

`nextBar` is `async` (returns a Promise) but `setInterval` does not
await it. If `nextBar` takes longer than `interval` (e.g. due to
network latency or server-side processing), the next tick fires before
the previous one resolves, sending a second `/next` request while the
first is still in flight. Flask threaded mode serves both concurrently,
and the second `session.advance()` raises
`ValueError("cannot advance a stale replay plan")` in
`backend/intraday/replay_clock.py:105`.

Recommended fix (front-end): replace `setInterval(nextBar, interval)`
with a self-scheduling `setTimeout` that only fires after the previous
`nextBar()` Promise resolves:

```js
async function playbackTick() {
    if (!isPlaying) return;
    await nextBar();
    if (isPlaying) playbackInterval = setTimeout(playbackTick, interval);
}
```

Alternative fix (back-end): serialize `/next` requests per session
using a per-session lock.

### 10.5 Production bug #4 — Front-end `currentTraining` staleness

After the back-end silently replaces a session (because the test
harness reused the same `training_id`), the front-end's
`currentTraining` variable still references the old snapshot. There is
no defensive check on `data_mode` before dispatching into the intraday
branch. This caused 158 "intraday 训练数据为空" console errors.

In normal user flow this does not happen because `training_id` includes
a real wall-clock timestamp. The bug is therefore low-severity but
worth a defensive guard.

## 11. Production-File Integrity Confirmation

```
$ cd E:/Desktop/01_TODO/mimo/KLinePlayground
$ git status --short
(empty output)

$ git status
On branch master
Your branch is ahead of 'origin/master' by 16 commits.
nothing to commit, working tree clean
```

- No production file was modified.
- No Git operation (add / commit / checkout / reset / clean / branch)
  was performed.
- The only file created by this acceptance task is this report:
  `docs/testing/phase4-intraday-browser-acceptance.md`.
- The launcher script and scratch files live outside the production
  codebase at `E:\Desktop\01_TODO\trding\.scratch\task014_launcher.py`
  and are not part of the project repository.
- The BaoStock 30m cache file `data/intraday/30m/600000.csv` was
  created by the production code's normal sync path (not by manual
  editing) and is gitignored.

## 12. Acceptance Criteria Checklist

- [x] All required scenarios have explicit evidence (Sections 3-9).
- [x] No production files were modified (Section 11).
- [x] Any failure includes reproducible steps (Section 9).
- [x] Browser and API observations are separated from assumptions
      (Section 7-8 distinguish observed errors from inferred root
      causes; Section 10 labels each finding as a production bug with
      file/line references).

## 13. Final Verdict

**FAIL.**

8 scenarios Pass, 2 scenarios Fail (H Playback, J Browser console &
network). 0 Blocked.

The 2 failures are caused by production bugs (Section 10.3-10.4), not
by external BaoStock/network unavailability. The 8 passing scenarios
required 2 runtime monkey-patches (Section 1) to work around 2
independent production bugs (Section 10.1-10.2) that otherwise make
`intraday_30m` startup impossible whenever BaoStock 30m data lags even
one day behind the wall-clock date.

Recommended next steps before re-running acceptance:
1. Fix `backend/app_enhanced.py:502` to accept `end_date` from the
   request or fall back to cache coverage end.
2. Fix `backend/intraday/models.py:14-15` or
   `backend/app_enhanced.py:101-103` so `coverage.covers` does not
   reject valid cache hits due to the 10:00 vs 00:00 mismatch.
3. Fix `frontend/js/main_enhanced.js:2845` to await `nextBar()` before
   scheduling the next playback tick.
4. Re-run this acceptance without the launcher patches.
