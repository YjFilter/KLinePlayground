# Historical Context and Intraday Blind-Box Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make trading limits count real trading days, give every session at least two years of prior chart context, support bidirectional one-year loading in completed reviews, and enable all intraday periods in blind-box mode.

**Architecture:** Keep `IntradayReplaySession` focused on the bounded replay timeline and add pure modules for trading-day cutoff, chart-window aggregation, and blind-box candidate selection. Flask routes compose those modules, persist the metadata needed for server-restart-safe history, and expose read-only chart-window endpoints. The frontend consumes explicit window metadata and never reveals data after `current_time` during active training.

**Tech Stack:** Python 3.11, Flask, pandas, existing BaoStock/cache layer, unittest, vanilla JavaScript, Lightweight Charts.

---

## File Structure and Ownership

### New backend modules

- `backend/intraday/training_window.py` — distinct trading-date calculation and replay cutoff.
- `backend/intraday/chart_window.py` — read-only date-window loading, aggregation, serialization, and pagination metadata.
- `backend/intraday/random_selector.py` — bounded retry selection of a stock and real intraday start date.

### Existing backend integration

- `backend/intraday/__init__.py` — export stable public contracts.
- `backend/app_enhanced.py` — start-session integration, active/history chart routes, persistence metadata.
- `backend/user_manager_enhanced.py` — only if a focused helper is needed to read stored session metadata; arbitrary report JSON storage stays unchanged.

### Frontend

- `frontend/index_enhanced.html` — rename the limit, add context-loading controls.
- `frontend/css/style_enhanced.css` — layout and disabled/loading states for window controls.
- `frontend/js/main_enhanced.js` — blind-box request contract, chart-window merge, active no-future behavior, historical bidirectional loading.

### Tests

- `tests/test_intraday_training_window.py`
- `tests/test_intraday_chart_window.py`
- `tests/test_intraday_random_selector.py`
- `tests/test_intraday_history_chart_api.py`
- `tests/test_intraday_blind_box_api.py`
- `tests/test_intraday_frontend_static.py`
- `docs/testing/historical-context-blind-box-browser-acceptance.md`

## Dependency and Parallelism

- Tasks 1, 2, and 3 have disjoint write scopes and may run simultaneously.
- Task 4 integrates Tasks 1-3 into the Flask hotspot and must run alone after their contracts are accepted.
- Task 5 may run in parallel with Task 4 because it changes only HTML/CSS.
- Task 6 must wait for Task 4's API contract and Task 5's element IDs.
- Task 7 runs only after all implementation commits are integrated.

---

### Task 1: Trading-Day Replay Window

**Files:**
- Create: `backend/intraday/training_window.py`
- Test: `tests/test_intraday_training_window.py`

- [ ] **Step 1: Write failing tests for distinct trading-day cutoff**

```python
from datetime import datetime
import unittest
import pandas as pd

from backend.intraday.training_window import build_training_window


def make_bars(days):
    rows = []
    for day in days:
        for time_text in ("10:00", "10:30", "11:00", "11:30", "13:30", "14:00", "14:30", "15:00"):
            rows.append({
                "datetime": pd.Timestamp(f"{day} {time_text}"),
                "open": 10.0,
                "high": 10.2,
                "low": 9.8,
                "close": 10.1,
                "volume": 1000,
                "amount": 10000,
            })
    return pd.DataFrame(rows)


class TrainingWindowTests(unittest.TestCase):
    def test_150_means_trading_dates_not_base_bars(self):
        days = pd.bdate_range("2025-01-02", periods=151).strftime("%Y-%m-%d").tolist()
        result = build_training_window(
            make_bars(days),
            datetime.fromisoformat(f"{days[0]} 10:00:00"),
            max_training_days=150,
        )
        self.assertEqual(len(result.trading_dates), 150)
        self.assertEqual(result.cutoff_time, datetime.fromisoformat(f"{days[149]} 15:00:00"))
        self.assertEqual(len(result.replay_bars), 150 * 8)

    def test_zero_limit_uses_all_remaining_dates(self):
        frame = make_bars(["2025-01-02", "2025-01-03", "2025-01-06"])
        result = build_training_window(frame, datetime(2025, 1, 3, 10), 0)
        self.assertEqual(result.trading_dates, (
            datetime(2025, 1, 3).date(),
            datetime(2025, 1, 6).date(),
        ))
        self.assertEqual(result.cutoff_time, datetime(2025, 1, 6, 15))

    def test_limit_larger_than_remaining_data_uses_available_dates(self):
        frame = make_bars(["2025-01-02", "2025-01-03"])
        result = build_training_window(frame, datetime(2025, 1, 2, 10), 150)
        self.assertEqual(len(result.trading_dates), 2)
        self.assertEqual(result.cutoff_time, datetime(2025, 1, 3, 15))
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```powershell
python -m unittest tests.test_intraday_training_window -v
```

Expected: import failure because `backend.intraday.training_window` does not exist.

- [ ] **Step 3: Implement the immutable training-window contract**

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

import pandas as pd


@dataclass(frozen=True)
class TrainingWindow:
    start_time: datetime
    cutoff_time: datetime
    trading_dates: tuple[date, ...]
    replay_bars: pd.DataFrame


def build_training_window(
    base_bars: pd.DataFrame,
    start_time: datetime,
    max_training_days: int,
) -> TrainingWindow:
    if max_training_days < 0:
        raise ValueError("max_training_days must be non-negative")
    frame = base_bars.copy()
    frame["datetime"] = pd.to_datetime(frame["datetime"], errors="coerce", format="mixed")
    if frame["datetime"].isna().any():
        raise ValueError("base_bars contains invalid datetime values")
    if frame["datetime"].duplicated().any() or not frame["datetime"].is_monotonic_increasing:
        raise ValueError("base_bars timestamps must be unique and increasing")
    remaining = frame.loc[frame["datetime"] >= pd.Timestamp(start_time)].copy()
    if remaining.empty or remaining.iloc[0]["datetime"] != pd.Timestamp(start_time):
        raise ValueError("start_time must exist in base_bars")
    available_dates = tuple(dict.fromkeys(remaining["datetime"].dt.date.tolist()))
    selected_dates = available_dates if max_training_days == 0 else available_dates[:max_training_days]
    if not selected_dates:
        raise ValueError("no trading dates available from start_time")
    replay_bars = remaining.loc[remaining["datetime"].dt.date.isin(selected_dates)].reset_index(drop=True)
    cutoff_time = replay_bars.iloc[-1]["datetime"].to_pydatetime()
    return TrainingWindow(
        start_time=start_time,
        cutoff_time=cutoff_time,
        trading_dates=selected_dates,
        replay_bars=replay_bars,
    )
```

Do not modify `backend/intraday/__init__.py` in this task; Codex adds the public export during integration.

- [ ] **Step 4: Add edge tests for holidays, start-in-middle, and input validation**

Add tests asserting:

```python
self.assertEqual(
    build_training_window(
        make_bars(["2025-01-03", "2025-01-06"]),
        datetime(2025, 1, 3, 10),
        2,
    ).trading_dates,
    (datetime(2025, 1, 3).date(), datetime(2025, 1, 6).date()),
)
```

Also assert negative limits, duplicate timestamps, and a missing `start_time` raise `ValueError`.

- [ ] **Step 5: Run focused tests**

```powershell
python -m unittest tests.test_intraday_training_window -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```powershell
git add backend/intraday/training_window.py tests/test_intraday_training_window.py
git commit -m "feat: add trading-day replay windows"
```

---

### Task 2: Read-Only Chart Window Service

**Files:**
- Create: `backend/intraday/chart_window.py`
- Test: `tests/test_intraday_chart_window.py`

- [ ] **Step 1: Write failing tests for active and completed windows**

```python
from datetime import datetime
import unittest
import pandas as pd

from backend.intraday.chart_window import ChartWindowService


TIMES = ("10:00", "10:30", "11:00", "11:30", "13:30", "14:00", "14:30", "15:00")


def make_multi_year_frame():
    rows = []
    for day in pd.bdate_range("2021-12-30", "2026-01-05"):
        for time_text in TIMES:
            rows.append({
                "datetime": pd.Timestamp(f"{day.date()} {time_text}"),
                "open": 10.0,
                "high": 10.2,
                "low": 9.8,
                "close": 10.1,
                "volume": 1000,
                "amount": 10000,
            })
    return pd.DataFrame(rows)


class FakeCache:
    def __init__(self, frame):
        self.frame = frame

    def coverage(self, stock_code):
        from backend.intraday.models import IntradayRange
        return IntradayRange(
            self.frame["datetime"].min().to_pydatetime(),
            self.frame["datetime"].max().to_pydatetime(),
        )


class FakeLoader:
    def __init__(self, frame):
        self.frame = frame
        self.cache = FakeCache(frame)

    def get_30m(self, stock_code, start, end):
        mask = (self.frame["datetime"] >= pd.Timestamp(start)) & (self.frame["datetime"] <= pd.Timestamp(end))
        return self.frame.loc[mask].reset_index(drop=True)


class ChartWindowTests(unittest.TestCase):
    def setUp(self):
        self.loader = FakeLoader(make_multi_year_frame())
        self.service = ChartWindowService(self.loader)

    def test_active_window_caps_end_at_current_time(self):
        result = self.service.load(
            stock_code="600000",
            period="daily",
            range_start=datetime(2022, 1, 1),
            range_end=datetime(2026, 1, 1),
            current_time=datetime(2025, 1, 10, 10),
            read_only=False,
        )
        self.assertLessEqual(result.window_end, datetime(2025, 1, 10, 10))
        self.assertTrue(all(bar["end_time"] <= "2025-01-10 10:00:00" for bar in result.kline_data))

    def test_completed_window_can_extend_after_training_end(self):
        result = self.service.load(
            stock_code="600000",
            period="weekly",
            range_start=datetime(2023, 1, 1),
            range_end=datetime(2026, 1, 1),
            current_time=datetime(2024, 6, 30, 15),
            read_only=True,
        )
        self.assertGreater(result.window_end, datetime(2024, 6, 30, 15))

    def test_window_metadata_reports_earlier_and_later_availability(self):
        result = self.service.load(
            stock_code="600000",
            period="30m",
            range_start=datetime(2023, 1, 1),
            range_end=datetime(2024, 1, 10, 15),
            current_time=datetime(2024, 1, 10, 15),
            read_only=True,
        )
        self.assertIsInstance(result.has_earlier, bool)
        self.assertIsInstance(result.has_later, bool)
```


- [ ] **Step 2: Run the focused test and verify it fails**

```powershell
python -m unittest tests.test_intraday_chart_window -v
```

Expected: import failure.

- [ ] **Step 3: Implement `ChartWindowResult` and `ChartWindowService`**

The public contract is:

```python
from dataclasses import dataclass
from datetime import datetime
import pandas as pd

from .aggregator import aggregate_bars

_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def _serialize_aggregated_bar(row):
    return {
        "period": str(row["period"]),
        "start_time": pd.Timestamp(row["start_time"]).strftime(_TIME_FORMAT),
        "end_time": pd.Timestamp(row["end_time"]).strftime(_TIME_FORMAT),
        "open": float(row["open"]),
        "high": float(row["high"]),
        "low": float(row["low"]),
        "close": float(row["close"]),
        "volume": float(row["volume"]),
        "amount": float(row["amount"]),
        "source_bar_count": int(row["source_bar_count"]),
        "complete": bool(row["complete"]),
    }


def _volume_point(bar):
    return {
        "time": bar["end_time"],
        "value": bar["volume"],
        "color": "#ff4d4f" if bar["close"] >= bar["open"] else "#008000",
    }


@dataclass(frozen=True)
class ChartWindowResult:
    period: str
    window_start: datetime
    window_end: datetime
    kline_data: list[dict[str, object]]
    volume_data: list[dict[str, object]]
    has_earlier: bool
    has_later: bool
    read_only: bool


class ChartWindowService:
    def __init__(self, data_service):
        self.data_service = data_service

    def load(
        self,
        *,
        stock_code: str,
        period: str,
        range_start: datetime,
        range_end: datetime,
        current_time: datetime,
        read_only: bool,
    ) -> ChartWindowResult:
        effective_end = range_end if read_only else min(range_end, current_time)
        if range_start > effective_end:
            raise ValueError("range_start must not exceed the visible end")
        frame = self.data_service.get_30m(stock_code, range_start, effective_end)
        aggregated = aggregate_bars(frame, period, effective_end)
        visible = aggregated.loc[
            (aggregated["end_time"] >= pd.Timestamp(range_start))
            & (aggregated["end_time"] <= pd.Timestamp(effective_end))
        ]
        coverage = self.data_service.cache.coverage(stock_code)
        serialized = [_serialize_aggregated_bar(row) for _, row in visible.iterrows()]
        return ChartWindowResult(
            period=period,
            window_start=range_start,
            window_end=effective_end,
            kline_data=serialized,
            volume_data=[_volume_point(bar) for bar in serialized],
            has_earlier=bool(coverage and coverage.start < range_start),
            has_later=bool(read_only and coverage and coverage.end > effective_end),
            read_only=read_only,
        )
```

Serialization must match `IntradayReplaySession.snapshot()` fields: `period`, `start_time`, `end_time`, OHLCV, `amount`, `source_bar_count`, and `complete`.

Compute availability from `data_service.cache.coverage(stock_code)` when present. `has_later` is always false for active training even if the cache contains future bars.

- [ ] **Step 4: Add tests for all periods, dedupe-safe boundaries, and no future leakage**

Test exact periods `30m`, `4h_session`, `daily`, and `weekly`. Add an attack test with an extreme future high and assert it does not appear when `read_only=False`.

- [ ] **Step 5: Run focused tests**

```powershell
python -m unittest tests.test_intraday_chart_window tests.test_intraday_no_future_leakage -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```powershell
git add backend/intraday/chart_window.py tests/test_intraday_chart_window.py
git commit -m "feat: add read-only chart windows"
```

---

### Task 3: Intraday Blind-Box Candidate Selector

**Files:**
- Create: `backend/intraday/random_selector.py`
- Test: `tests/test_intraday_random_selector.py`

- [ ] **Step 1: Write failing selector tests**

```python
from datetime import datetime
import random
import unittest
import pandas as pd

from backend.intraday.random_selector import IntradayRandomSelector


TIMES = ("10:00", "10:30", "11:00", "11:30", "13:30", "14:00", "14:30", "15:00")


def make_frame(start, periods):
    rows = []
    for day in pd.bdate_range(start, periods=periods):
        for time_text in TIMES:
            rows.append({
                "datetime": pd.Timestamp(f"{day.date()} {time_text}"),
                "open": 10.0,
                "high": 10.2,
                "low": 9.8,
                "close": 10.1,
                "volume": 1000,
                "amount": 10000,
            })
    return pd.DataFrame(rows)


def make_five_year_frame():
    return make_frame("2021-01-04", 1300)


def make_short_frame(days):
    return make_frame("2025-01-02", days)


class SequenceProvider:
    def __init__(self, codes):
        self.codes = list(codes)
        self.index = 0

    def __call__(self, sector, date_start, date_end):
        code = self.codes[min(self.index, len(self.codes) - 1)]
        self.index += 1
        return code


class FrameService:
    def __init__(self, frames):
        self.frames = frames

    def get_30m(self, stock_code, start, end):
        frame = self.frames[stock_code]
        mask = (frame["datetime"] >= pd.Timestamp(start)) & (frame["datetime"] <= pd.Timestamp(end))
        return frame.loc[mask].reset_index(drop=True)


class RandomSelectorTests(unittest.TestCase):
    def test_selects_real_date_inside_requested_range(self):
        selector = IntradayRandomSelector(
            candidate_provider=SequenceProvider(["600000"]),
            data_service=FrameService({"600000": make_five_year_frame()}),
            rng=random.Random(7),
            max_attempts=5,
        )
        result = selector.select(
            sector="all",
            date_start=datetime(2024, 1, 1),
            date_end=datetime(2025, 1, 1),
            max_training_days=150,
        )
        self.assertEqual(result.stock_code, "600000")
        self.assertGreaterEqual(result.start_time.date(), datetime(2024, 1, 1).date())
        self.assertLessEqual(result.start_time.date(), datetime(2025, 1, 1).date())
        self.assertEqual(result.start_time.time().isoformat(), "10:00:00")

    def test_rejects_bse_and_candidates_without_two_year_context(self):
        selector = IntradayRandomSelector(
            candidate_provider=SequenceProvider(["430001", "600000"]),
            data_service=FrameService({
                "430001": make_five_year_frame(),
                "600000": make_five_year_frame(),
            }),
            rng=random.Random(7),
            max_attempts=5,
        )
        result = selector.select(
            sector="all",
            date_start=datetime(2024, 1, 1),
            date_end=datetime(2025, 1, 1),
            max_training_days=20,
        )
        self.assertEqual(result.stock_code, "600000")
        self.assertNotIn(result.stock_code[:2], {"43", "83", "87", "92"})

    def test_requires_enough_future_trading_dates(self):
        selector = IntradayRandomSelector(
            candidate_provider=SequenceProvider(["600000"]),
            data_service=FrameService({"600000": make_short_frame(days=20)}),
            rng=random.Random(7),
            max_attempts=1,
        )
        with self.assertRaisesRegex(ValueError, "valid intraday blind-box candidate"):
            selector.select(
                sector="all",
                date_start=datetime(2025, 1, 1),
                date_end=datetime(2025, 12, 31),
                max_training_days=150,
            )
```

- [ ] **Step 2: Run and verify failure**

```powershell
python -m unittest tests.test_intraday_random_selector -v
```

Expected: import failure.

- [ ] **Step 3: Implement the selector contract**

```python
from dataclasses import dataclass
from datetime import datetime
import random
import pandas as pd


@dataclass(frozen=True)
class RandomIntradaySelection:
    stock_code: str
    start_time: datetime
    context_start: datetime
    available_training_days: int
    base_bars: pd.DataFrame


class IntradayRandomSelector:
    def __init__(self, candidate_provider, data_service, rng=None, max_attempts=20):
        self.candidate_provider = candidate_provider
        self.data_service = data_service
        self.rng = rng or random.Random()
        self.max_attempts = max_attempts

    def select(self, *, sector, date_start, date_end, max_training_days):
        requested_context_start = (pd.Timestamp(date_start) - pd.DateOffset(years=2)).to_pydatetime()
        for _ in range(self.max_attempts):
            stock_code = self.candidate_provider(sector, date_start, date_end)
            if stock_code.startswith(("43", "83", "87", "92")):
                continue
            try:
                frame = self.data_service.get_30m(stock_code, requested_context_start, datetime.now())
            except Exception:
                continue
            if frame is None or frame.empty:
                continue
            frame = frame.copy()
            frame["datetime"] = pd.to_datetime(frame["datetime"], errors="coerce", format="mixed")
            if frame["datetime"].isna().any():
                continue
            dates = tuple(dict.fromkeys(frame["datetime"].dt.date.tolist()))
            eligible = []
            for index, trading_date in enumerate(dates):
                if not (date_start.date() <= trading_date <= date_end.date()):
                    continue
                start_ts = frame.loc[pd.to_datetime(frame["datetime"]).dt.date == trading_date, "datetime"].iloc[0]
                if start_ts.time().isoformat() != "10:00:00":
                    continue
                if (selected_context_days := (start_ts.date() - frame["datetime"].min().date()).days) < 730:
                    continue
                remaining = len(dates) - index
                if max_training_days and remaining < max_training_days:
                    continue
                eligible.append(start_ts.to_pydatetime())
            if eligible:
                selected = self.rng.choice(eligible)
                return RandomIntradaySelection(
                    stock_code=stock_code,
                    start_time=selected,
                    context_start=(pd.Timestamp(selected) - pd.DateOffset(years=2)).to_pydatetime(),
                    available_training_days=len([day for day in dates if day >= selected.date()]),
                    base_bars=frame,
                )
        raise ValueError("no valid intraday blind-box candidate; widen the date range, reduce training days, or change sector")
```

Use `pandas.DateOffset(years=2)` rather than adding a new `dateutil` dependency if the project does not already depend on it.

The candidate provider adapter in Flask calls `data_manager.get_random_stock(sector, date_start.isoformat(), date_end.isoformat(), source=data_source, interval="daily")` and uses only the returned stock code; the selector chooses the real intraday date from normalized data.

- [ ] **Step 4: Add deterministic retry tests**

Verify the selector retries after:

- a BSE code;
- an empty data frame;
- less than two years of history;
- fewer than `max_training_days` remaining dates;
- a source exception.

- [ ] **Step 5: Run focused tests**

```powershell
python -m unittest tests.test_intraday_random_selector -v
```

Expected: all tests pass without network access.

- [ ] **Step 6: Commit**

```powershell
git add backend/intraday/random_selector.py tests/test_intraday_random_selector.py
git commit -m "feat: add intraday blind-box selection"
```

---

### Task 4: Flask and Persistence Integration

**Files:**
- Modify: `backend/app_enhanced.py`
- Modify only if required: `backend/user_manager_enhanced.py`
- Test: `tests/test_intraday_blind_box_api.py`
- Test: `tests/test_intraday_history_chart_api.py`
- Modify: `tests/test_intraday_api.py`

- [ ] **Step 1: Write failing blind-box API tests**

Test `POST /api/training/start` with:

```python
payload = {
    "user": TEST_USER,
    "mode": "random",
    "data_mode": "intraday_30m",
    "sector": "all",
    "date_start": "2024-01-01",
    "date_end": "2026-01-01",
    "max_training_days": 150,
    "period": "30m",
    "initial_capital": 100000,
}
```

Assert:

```python
self.assertEqual(response.status_code, 200)
body = response.get_json()
self.assertEqual(body["data_mode"], "intraday_30m")
self.assertEqual(body["active_period"], "30m")
self.assertEqual(body["max_training_days"], 150)
self.assertGreaterEqual(len(body["context_kline_data"]), 1)
self.assertGreaterEqual(body["training_start"][:10], "2024-01-01")
self.assertLessEqual(body["training_start"][:10], "2026-01-01")
```

Mock the random selector; never call BaoStock live.

- [ ] **Step 2: Write failing history chart API tests**

Persist a completed intraday session through the mocked `user_manager`, clear `active_trainings`, then call:

```text
GET /api/users/test_user/history/session_1/chart?period=30m&range_start=2022-01-01&range_end=2025-01-01
```

Assert HTTP 200, chart bars, volume, trade markers, `read_only=true`, and that no active session is required.

Add a legacy record test and a missing-metadata 400 test with a specific error message.

- [ ] **Step 3: Run focused tests and verify failure**

```powershell
python -m unittest tests.test_intraday_blind_box_api tests.test_intraday_history_chart_api -v
```

Expected: routes/contracts are missing.

- [ ] **Step 4: Normalize setup inputs**

In `start_training()` use:

```python
max_training_days = int(data.get("max_training_days", data.get("max_bars", 0)) or 0)
if max_training_days < 0:
    return jsonify({"error": "训练交易日限制不能为负数"}), 400
```

Pass `max_training_days` into intraday startup. Keep legacy `max_bars` behavior unchanged.

- [ ] **Step 5: Add random intraday startup**

When `mode == "random"`, call the accepted `IntradayRandomSelector`. When specified, load two years before the requested start date:

```python
context_start = start_dt - pd.DateOffset(years=2)
market_bars = service.get_30m(stock_code, context_start.to_pydatetime(), datetime.now())
initial_time = _choose_initial_time(market_bars, start_dt)
window = build_training_window(market_bars, initial_time, max_training_days)
session = IntradayReplaySession(
    base_bars=window.replay_bars,
    initial_time=initial_time,
    stock_code=stock_code,
    simulator=trade_simulator,
    order_manager=order_manager,
    initial_period=period,
)
```

Store `market_bars` only if needed for the active chart route; prefer reloading through `ChartWindowService` to avoid duplicated state.

- [ ] **Step 6: Persist complete chart metadata**

Add these fields to start/end session records:

```python
{
    "data_mode": "intraday_30m",
    "base_interval": "30m",
    "period": active_period,
    "training_start": initial_time.isoformat(sep=" "),
    "training_end": current_time.isoformat(sep=" "),
    "max_training_days": max_training_days,
}
```

Preserve `trade_time` and `display_period` inside `report_data.trade_details`.

- [ ] **Step 7: Add active chart-window route**

```python
def _parse_datetime_arg(name):
    value = request.args.get(name)
    if not value:
        raise ValueError(f"缺少 {name} 参数")
    return datetime.fromisoformat(value)


def _get_chart_window_service():
    from backend.intraday.chart_window import ChartWindowService
    return ChartWindowService(_get_intraday_data_service())


def _chart_window_payload(result, training):
    return {
        "stock_code": training["stock_code"],
        "period": result.period,
        "window_start": result.window_start.isoformat(sep=" "),
        "window_end": result.window_end.isoformat(sep=" "),
        "kline_data": result.kline_data,
        "volume_data": result.volume_data,
        "has_earlier": result.has_earlier,
        "has_later": result.has_later,
        "read_only": result.read_only,
        "training_start": training["training_start"],
        "training_end": training.get("training_end"),
    }


@app.get("/api/training/<training_id>/chart-window")
def get_training_chart_window(training_id):
    training = active_trainings.get(training_id)
    if not training:
        return jsonify({"error": "训练会话不存在"}), 404
    if not _is_intraday_session(training):
        return jsonify({"error": "该会话不支持分钟级上下文窗口"}), 400
    snapshot = training["intraday_session"].snapshot()
    result = _get_chart_window_service().load(
        stock_code=training["stock_code"],
        period=request.args.get("period", snapshot["active_period"]),
        range_start=_parse_datetime_arg("range_start"),
        range_end=_parse_datetime_arg("range_end"),
        current_time=datetime.fromisoformat(snapshot["current_time"]),
        read_only=False,
    )
    return jsonify(_chart_window_payload(result, training))
```

Reject a requested end after current replay time by capping it server-side.

- [ ] **Step 8: Add history chart route**

Read the stored report with `user_manager.get_session_report(username, session_id)`. Resolve best-effort timestamps, then call `ChartWindowService.load(stock_code=stock_code, period=period, range_start=range_start, range_end=range_end, current_time=training_end, read_only=True)`.

Trade markers must use full `trade_time` when available, otherwise `trade_date`. For `data_mode == "legacy_daily"`, load daily/weekly bars through `data_manager.get_stock_data(stock_code, source=data_source, interval=period)`, slice the requested window, and serialize the legacy OHLCV fields instead of requiring a 30-minute cache.

- [ ] **Step 9: Run focused and regression tests**

```powershell
python -m unittest tests.test_intraday_blind_box_api tests.test_intraday_history_chart_api tests.test_intraday_api tests.test_trading_rules -v
python scripts/quality_gate.py phase3
```

Expected: all pass.

- [ ] **Step 10: Commit**

```powershell
git add backend/app_enhanced.py backend/user_manager_enhanced.py tests/test_intraday_blind_box_api.py tests/test_intraday_history_chart_api.py tests/test_intraday_api.py
git commit -m "feat: integrate trading-day and history chart APIs"
```

---

### Task 5: Static UI Controls

**Files:**
- Modify: `frontend/index_enhanced.html`
- Modify: `frontend/css/style_enhanced.css`
- Test: `tests/test_intraday_context_static_ui.py`

- [ ] **Step 1: Write failing static tests**

Assert the HTML contains exactly one of each:

```text
#load-earlier-year-btn
#load-later-year-btn
#chart-window-status
#training-day-limit-help
```

Assert the label includes `训练交易日限制（0=不限制）` and no longer includes the old K-line-count wording.

- [ ] **Step 2: Run and verify failure**

```powershell
python -m unittest tests.test_intraday_context_static_ui -v
```

- [ ] **Step 3: Add controls**

Place the earlier button in the active chart toolbar. Place both buttons in the read-only historical chart toolbar, or reuse the same controls with the later button hidden during active training.

Use exact IDs:

```html
<button id="load-earlier-year-btn" type="button">往前加载一年</button>
<button id="load-later-year-btn" type="button" class="hidden">往后加载一年</button>
<span id="chart-window-status" aria-live="polite"></span>
```

Update the limit label and help text to explain real trading days.

- [ ] **Step 4: Add focused styles**

Add loading, disabled, and compact toolbar styles without redesigning unrelated panels.

- [ ] **Step 5: Run static checks**

```powershell
python -m unittest tests.test_intraday_context_static_ui -v
node --check frontend/js/main_enhanced.js
git diff --check
```

- [ ] **Step 6: Commit**

```powershell
git add frontend/index_enhanced.html frontend/css/style_enhanced.css tests/test_intraday_context_static_ui.py
git commit -m "feat: add historical chart window controls"
```

---

### Task 6: Frontend Chart-Window and Blind-Box Wiring

**Files:**
- Modify: `frontend/js/main_enhanced.js`
- Modify: `tests/test_intraday_frontend_static.py`
- Create: `tests/test_intraday_history_frontend_static.py`

- [ ] **Step 1: Write failing static contract tests**

Assert:

```python
self.assertIn("max_training_days", js)
self.assertNotIn("盲盒模式目前仅支持日线启动", js)
self.assertIn("/chart-window", js)
self.assertIn("/history/${", js)
self.assertIn("loadEarlierYear", js)
self.assertIn("loadLaterYear", js)
self.assertIn("mergeChartWindow", js)
```

Also assert the active branch never enables later loading.

- [ ] **Step 2: Run and verify failure**

```powershell
python -m unittest tests.test_intraday_frontend_static tests.test_intraday_history_frontend_static -v
```

- [ ] **Step 3: Send the new setup contract**

Use:

```javascript
const maxTrainingDays = parseInt(document.getElementById('max-training-bars')?.value, 10) || 0;
const trainingConfig = {
    user: currentUser,
    mode: isRandomMode ? 'random' : 'specified',
    initial_capital: initialCapital,
    data_mode: INTRADAY_DATA_MODE,
    max_training_days: maxTrainingDays,
    period: getSelectedKlinePeriod(),
};
```

Remove the blind-box non-daily alert. Blind-box and specified modes both use `intraday_30m` for all four selected periods.

- [ ] **Step 4: Load the initial two-year active window**

After start, request:

```javascript
GET /api/training/{id}/chart-window?period={active_period}&range_start={trainingStartMinusTwoYears}&range_end={current_time}
```

Render context plus the current snapshot. Do not call `/next`.

- [ ] **Step 5: Implement stable merging**

```javascript
function mergeChartWindow(existing, incoming) {
    const byTime = new Map();
    [...existing, ...incoming].forEach((bar) => byTime.set(bar.time, bar));
    return [...byTime.values()].sort((a, b) => Number(a.time) - Number(b.time));
}
```

Use the same merge for candle and volume arrays. Preserve the visible logical range when prepending earlier bars.

- [ ] **Step 6: Implement one-year controls**

`loadEarlierYear()` subtracts one calendar year from `window_start`. `loadLaterYear()` adds one calendar year to `window_end` and is callable only when `isViewOnlyMode` is true and the history payload reports `has_later`.

Disable a button while its request is in flight and when the corresponding availability flag is false.

- [ ] **Step 7: Replace historical `/full_data` usage**

`viewFullChart()` must request:

```text
/api/users/{currentUser}/history/{sessionId}/chart
```

It must not depend on `currentTraining` or `active_trainings`. Set the page to read-only, show both loading controls, and render returned trade markers.

- [ ] **Step 8: Preserve no-future behavior**

Add a static test that the active window request uses `current_time` as its maximum end and that `load-later-year-btn` stays hidden outside read-only history.

- [ ] **Step 9: Run frontend and API tests**

```powershell
node --check frontend/js/main_enhanced.js
python -m unittest tests.test_intraday_frontend_static tests.test_intraday_history_frontend_static tests.test_intraday_context_static_ui -v
git diff --check
```

- [ ] **Step 10: Commit**

```powershell
git add frontend/js/main_enhanced.js tests/test_intraday_frontend_static.py tests/test_intraday_history_frontend_static.py
git commit -m "feat: wire historical chart windows"
```

---

### Task 7: Full Integration and Browser Acceptance

**Files:**
- Modify: `.agent/STATE.md`
- Create: `docs/testing/historical-context-blind-box-browser-acceptance.md`
- Create/modify task files under `.agent/tasks/` as directed by Codex integration.

- [ ] **Step 1: Run the complete automated suite**

```powershell
python -m unittest discover -s tests -v
node --check frontend/js/main_enhanced.js
python scripts/agent_status.py .agent/tasks
git diff --check
```

Expected: all tests pass.

- [ ] **Step 2: Run independent no-future attack acceptance**

Verify active training cannot request or render a `range_end` after `current_time`, even when the browser manually changes query parameters.

- [ ] **Step 3: Browser-test specified mode**

For `600000`, test all four periods with a non-zero trading-day limit. Confirm two years of prior context, one-year backward loading, stable replay time, and exact trading-day cutoff.

- [ ] **Step 4: Browser-test blind-box mode**

Use a bounded date range and `150` trading days. Record the randomly selected stock/date, confirm the date is within range, verify it has two prior years, and confirm 30-minute playback does not finish after 150 base bars.

- [ ] **Step 5: Browser-test completed history after restart**

Finish a short session, restart Flask, open the saved history report, and verify:

- prior two-year context;
- complete training interval;
- trade markers;
- earlier-year loading;
- later-year loading;
- no active session dependency;
- no ability to trade.

- [ ] **Step 6: Record evidence**

The report must include HTTP status codes, before/after window dates, replay timestamps, Console errors, 4xx/5xx counts, selected blind-box candidate, and Pass/Fail/Blocked totals.

- [ ] **Step 7: Final integration commit**

```powershell
git add .agent docs/testing/historical-context-blind-box-browser-acceptance.md
git commit -m "test: accept historical context and blind-box replay"
```

---

## WorkBuddy Assignment Strategy

### Parallel Round 1

- WorkBuddy Agent 1: Task 1 only.
- WorkBuddy Agent 2: Task 2 only.
- WorkBuddy Agent 3: Task 3 only.

These agents may run simultaneously because their primary implementation and test files are disjoint. `backend/intraday/__init__.py` is a shared export file; external agents must not modify it. Codex adds all exports during integration to avoid conflicts.

### Round 2

- WorkBuddy Agent 4: Task 5 HTML/CSS only.
- Codex: review and integrate Tasks 1-3, add public exports, define the final Flask contract.

Task 5 may run while Codex performs backend integration.

### Round 3

- WorkBuddy Agent 5: Task 6 frontend JavaScript after Codex publishes the accepted API contract.
- Codex: Task 4 Flask hotspot integration and all critical fixes.

Do not run Agent 5 until Task 4 is committed.

### Round 4

- WorkBuddy Agent 6: independent browser acceptance only.
- Codex: final review, quality gates, task-state updates, and commits.

## Plan Self-Review

- Spec coverage: trading-day semantics, random intraday selection, two-year context, active backward loading, completed bidirectional loading, restart-safe history, legacy compatibility, and no-future enforcement all map to Tasks 1-7.
- Placeholder scan: no incomplete implementation calls or undefined helper names remain. Python tuple type annotations and JavaScript spread syntax use ellipses only as language syntax.
- Type consistency: `max_training_days`, `training_start`, `training_end`, `ChartWindowResult`, `RandomIntradaySelection`, and the two chart routes use the same names throughout the plan.
