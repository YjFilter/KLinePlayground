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

---

## 14. 修复后无补丁复验（2026-07-14）

本节保留第 1-13 节第一次验收的完整 FAIL 历史、证据和根因分析，记录提交 `33ab2a2 fix: stabilize intraday data and playback` 合入后的最终复验。本节结论取代第 13 节的旧结论，作为 TASK-014 的最新最终结论。

### 14.1 无补丁环境与启动方式

| 项目 | 复验值 |
| --- | --- |
| 项目根目录 | `E:\Desktop\01_TODO\mimo\KLinePlayground` |
| 生产入口 | `backend\app_enhanced.py` |
| 服务器 URL | `http://127.0.0.1:5000/` |
| 健康检查 | `GET /api/health` -> HTTP 200 |
| 生产 Python PID | `11132`，命令行为 `python.exe backend\app_enhanced.py` |
| 浏览器 | `playwright-cli` Chromium，隔离会话 `task014-final` |
| 用户 | `acceptance_tester` |
| 模式 | 指定模式 |
| 股票 | `600000` |
| 起始日期 | `2024-01-02` |
| 初始周期 | `30m` |

实际启动命令为：

```powershell
cd E:\Desktop\01_TODO\mimo\KLinePlayground
$env:PYTHONPATH = (Get-Location).Path
python backend\app_enhanced.py
```

复验明确满足以下隔离条件：

- **没有 launcher**，未使用 `task014_launcher.py`。
- **没有 monkey-patch**，未替换 `datetime`、`IntradayDataService` 或任何生产对象。
- **没有冻结 `datetime.now()`**。
- **没有项目副本**，直接运行当前仓库的生产入口。
- 浏览器启动时没有残留 Playwright 会话；最终隔离验证使用新会话 `task014-final`。
- Console/Network 采集在打开新建训练弹窗后、发送本次 `/start` 前开始，因而不包含第一次验收的 legacy 会话记录。

### 14.2 真实数据与启动响应

修复后的第一次无补丁复验使用 BaoStock 缓存 4872 根 30 分钟 K 线，范围为 `2024-01-02 10:00:00` 至 `2026-07-10 15:00:00`。2026-07-14 最终隔离复验启动时，生产同步路径继续取得 8 根最新可用数据；本地缓存最终为 4880 根，范围为 `2024-01-02 10:00:00` 至 `2026-07-13 15:00:00`。两次都不需要冻结当前时间。

最终隔离会话的 `POST /api/training/start` 返回 HTTP 200，响应关键字段为：

- `id = acceptance_tester_20260714_020441`
- `data_mode = intraday_30m`
- `stock_code = 600000`
- `active_period = 30m`
- `current_time = 2024-01-02 10:00:00`
- `next_boundary = 2024-01-02 10:30:00`
- `current_bar_complete = true`
- 当前 base bar close = `6.64`

页面首次显示 `2024-01-02 10:00:00`，没有自动前进。以 `2024-01-02 00:00:00` 作为请求起点时，缓存首根为 10:00 仍能正常覆盖并启动，没有再次出现 `30m data unavailable`。

### 14.3 A-I 场景复验结果

| ID | 场景 | 结果 | 修复后无补丁证据 |
| --- | --- | --- | --- |
| A | 无补丁启动 | **Pass** | 直接运行生产入口；`/api/health` 200；600000/2024-01-02/30m 的 `/start` 200；首次时间 10:00，无自动前进。 |
| B | 缓存覆盖 | **Pass** | 请求从交易日 00:00 开始，缓存从 10:00 开始仍正常命中；最新可用缓存落后墙钟日期也可启动。 |
| C | 单次继续 | **Pass** | `2024-01-02 10:00:00` -> `10:30:00`；仅 1 个 `POST /next`，HTTP 200。 |
| D | 自动播放与暂停 | **Pass** | 0.5 秒档位运行远超 5 ticks；最终隔离采集共 27 个 `/next`（含单次继续，自动播放 26 个），所有响应 200；`maxInFlight = 1`；无 stale replay plan；暂停后等待 2.2 秒新增 `/next = 0`，时间保持 `2024-01-05 11:30:00`。 |
| E | 周期切换 | **Pass** | `30m -> daily -> 4h_session -> weekly -> 30m`；基准和最终 `current_time` 都是 `2024-01-05 11:30:00`；4 个 `POST /period` 均为 200，切换期间 `/next = 0`。daily 显示未收盘部分日 K，下一边界 15:00。 |
| F | 全新 intraday Console/Network 隔离 | **Pass** | 新浏览器会话中 Console error 0；HTTP 4xx 0；HTTP 5xx 0；105 个被监控 fetch 的状态集合仅包含 200；stale replay plan 0。Playwright 独立 `console error` 查询同样为 0。 |
| G | 交易 UI | **Pass** | 真实点击 `#buy-btn`，填写并保存 `#trade-reason-text`；当前 base close `¥6.70`，成交记录价格 `¥6.70`；1 手，含费用金额 `¥675.00`；现金 `¥100,000 -> ¥99,325`，持仓市值 `¥670`；`POST /trade` 200。此前无补丁会话在 daily 显示周期下也已验证成交价等于 base close。 |
| H | Reset | **Pass** | 点击 `#reset-training-btn` 并接受 confirm；恢复时间 `2024-01-02 10:00:00`、周期 `30m`、现金 `¥100,000`、持仓 `¥0`、交易记录为空。 |
| I | 盲盒兼容 | **Pass** | legacy daily 可启动，股票为 `300540 / 蜀道装备`；30m 盲盒显示“盲盒模式目前仅支持日线启动...”且不发送 `/start`。legacy daily 的技术指标错误单独记录于 14.5，不计入 intraday 失败。 |

### 14.4 最终 Console/Network 统计

| 指标 | 结果 | 预期 | 判定 |
| --- | ---: | ---: | --- |
| Intraday Console error | 0 | 0 | Pass |
| HTTP 4xx | 0 | 0 | Pass |
| HTTP 5xx | 0 | 0 | Pass |
| `/next` 请求总数 | 27 | 至少 6（单次 + 自动播放至少 5） | Pass |
| `/next` 最大并发 | 1 | 1 | Pass |
| stale replay plan | 0 | 0 | Pass |
| 暂停后新增 `/next` | 0 | 0 | Pass |
| 周期切换 `/period` | 4 | 4 | Pass |
| 周期切换期间 `/next` | 0 | 0 | Pass |
| 周期切换是否改变 current_time | 否 | 否 | Pass |

### 14.5 非阻塞 legacy 已知问题

盲盒日线路径（`legacy_daily`，300540 / 蜀道装备）仍可启动，但页面时间显示 `--`，Console 出现 6 条 `加载技术指标失败: Value is undefined`。该问题属于既有 legacy 技术指标路径，不发生在 `intraday_30m` 新鲜会话中，也不是本次 intraday 数据服务或串行播放修复的回归，因此记录为非阻塞已知问题，不计入 TASK-014 intraday 验收失败数。

盲盒选择非日线周期（例如 30m）时，前端正确阻止启动并显示“盲盒模式目前仅支持日线启动...”，Network 中没有 `/start` 请求。

### 14.6 修复后验收标准

- [x] A-I 所有要求场景都有浏览器或 API 明确证据。
- [x] 无补丁、无 launcher、无 monkey-patch，直接运行生产入口。
- [x] 未修改 frontend/backend 生产文件。
- [x] 单次继续、自动播放、暂停、周期切换、交易和重置均通过真实页面操作。
- [x] Console 和 Network 观察与 legacy 已知问题分开记录。
- [x] 没有新的可稳定复现 P0/P1 问题。

### 14.7 最新最终结论

**PASS。**

- Pass：9
- Fail：0
- Blocked：0

提交 `33ab2a2` 已消除第一次验收发现的 intraday 缓存覆盖和并发播放问题。最终复验不依赖任何运行时补丁；全新 intraday 会话的 Console error、HTTP 4xx、HTTP 5xx 和 stale replay plan 均为 0，`/next maxInFlight = 1`。TASK-014 可以归档。
