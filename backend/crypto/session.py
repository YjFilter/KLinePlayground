from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Any

import pandas as pd

from .aggregator import aggregate_bars, normalize_base_bars
from .models import CryptoPeriod, utc_datetime
from .replay_clock import CryptoReplayClock

AVAILABLE_PERIODS = ("5m", "15m", "30m", "1h", "4h", "daily", "weekly")
TIME_FORMAT = "%Y-%m-%d %H:%M:%S"

class CryptoReplaySession:
    def __init__(self, base_bars: pd.DataFrame, initial_time: datetime | None = None, *, symbol: str = "", source: str = "", active_period: CryptoPeriod | str = "5m", max_training_days: int | None = None, on_bar=None):
        required = {"timestamp", "open", "high", "low", "close", "volume", "turnover"}
        missing = sorted(required - set(base_bars.columns))
        if missing:
            raise ValueError(f"crypto replay bars missing columns: {', '.join(missing)}")
        frame = normalize_base_bars(base_bars)
        if frame.empty:
            raise ValueError("crypto replay bars cannot be empty")
        selected = frame.iloc[0]["timestamp"].to_pydatetime() if initial_time is None else utc_datetime(initial_time)
        if max_training_days is not None:
            if max_training_days <= 0:
                raise ValueError("max_training_days must be positive")
            cutoff_date = selected.date() + timedelta(days=max_training_days - 1)
            cutoff = datetime.combine(cutoff_date, time(23, 55), tzinfo=timezone.utc)
            frame = frame.loc[frame["timestamp"] <= pd.Timestamp(cutoff)].reset_index(drop=True)
        if frame.empty or pd.Timestamp(selected) not in set(frame["timestamp"]):
            raise ValueError("initial_time must exist within the crypto replay range")
        self._base_bars = frame
        self._initial_time = selected
        self._symbol = symbol.upper()
        self._source = source
        self._on_bar = on_bar
        self._clock = CryptoReplayClock(frame["timestamp"], initial_time=selected, active_period=active_period)
        self._aggregation_cache: dict[tuple[datetime, str], pd.DataFrame] = {}
        self._snapshot_cache: dict[tuple[datetime, str, int | None, datetime | None, datetime | None], dict[str, Any]] = {}

    @property
    def clock(self):
        return self._clock

    @property
    def base_bars(self):
        return self._base_bars

    def snapshot(
        self, *, max_bars: int | None = None, range_start: datetime | None = None,
        range_end: datetime | None = None,
    ) -> dict[str, Any]:
        if max_bars is not None and max_bars <= 0:
            raise ValueError("max_bars must be positive")
        normalized_start = None if range_start is None else utc_datetime(range_start)
        normalized_end = None if range_end is None else utc_datetime(range_end)
        current_time = self._clock.current_time
        period = self._clock.active_period.value
        cache_key = (current_time, period, max_bars, normalized_start, normalized_end)
        cached = self._snapshot_cache.get(cache_key)
        if cached is not None:
            return dict(cached)
        aggregation_key = (current_time, period)
        aggregated = self._aggregation_cache.get(aggregation_key)
        if aggregated is None:
            aggregated = aggregate_bars(self._base_bars, self._clock.active_period, current_time)
            self._aggregation_cache[aggregation_key] = aggregated
        plan = self._clock.plan_next()
        visible = aggregated
        if normalized_start is not None or normalized_end is not None:
            end_times = pd.to_datetime(aggregated["end_time"], utc=True)
            lower = pd.Timestamp(normalized_start) if normalized_start is not None else end_times.iloc[0]
            upper = pd.Timestamp(normalized_end) if normalized_end is not None else end_times.iloc[-1]
            matching = aggregated.index[(end_times >= lower) & (end_times <= upper)]
            if len(matching):
                focus_end = min(int(matching[-1]) + 51, len(aggregated))
            else:
                focus_end = min(int(end_times.searchsorted(upper, side="right")) + 50, len(aggregated))
            focus_start = 0 if max_bars is None else max(focus_end - max_bars, 0)
            visible = aggregated.iloc[focus_start:focus_end]
        elif max_bars is not None:
            visible = aggregated.tail(max_bars)
        if max_bars is not None and len(visible) > max_bars:
            visible = visible.tail(max_bars)
        kline_data = [self._serialize_aggregated(row) for row in visible.to_dict("records")]
        current_base = self._base_bars.loc[self._base_bars["timestamp"] == pd.Timestamp(current_time)]
        current_base_bar = None if current_base.empty else self._serialize_base(current_base.iloc[0])
        current_complete = bool(aggregated.iloc[-1]["complete"]) if not aggregated.empty else False
        snapshot = {
            "market_type": "crypto_perpetual",
            "data_mode": "crypto_5m",
            "symbol": self._symbol,
            "source": self._source,
            "current_time": current_time.strftime(TIME_FORMAT),
            "active_period": self._clock.active_period.value,
            "period": self._clock.active_period.value,
            "base_interval": "5m",
            "available_periods": list(AVAILABLE_PERIODS),
            "current_bar_complete": current_complete,
            "next_boundary": plan.target_time.strftime(TIME_FORMAT) if plan.target_time is not None else None,
            "kline_data": kline_data,
            "volume_data": [{"time": item["time"], "value": item["volume"]} for item in kline_data],
            "current_base_bar": current_base_bar,
            "finished": plan.finished,
        }
        self._snapshot_cache[cache_key] = snapshot
        return dict(snapshot)

    def set_period(
        self, period, *, max_bars: int | None = None, range_start: datetime | None = None,
        range_end: datetime | None = None,
    ):
        self._clock.set_period(period)
        return self.snapshot(max_bars=max_bars, range_start=range_start, range_end=range_end)

    def advance(self):
        plan = self._clock.plan_next()
        if plan.finished:
            snapshot = self.snapshot()
            snapshot["completed_times"] = []
            snapshot["order_events"] = []
            return snapshot
        completed = []
        for timestamp in plan.base_bar_times:
            row = self._base_bars.loc[self._base_bars["timestamp"] == pd.Timestamp(timestamp)].iloc[0]
            if self._on_bar is not None:
                self._on_bar(timestamp, row.copy())
            completed.append(timestamp)
        self._clock.advance(plan)
        self._invalidate_cache()
        snapshot = self.snapshot()
        snapshot["completed_times"] = [value.strftime(TIME_FORMAT) for value in completed]
        snapshot["order_events"] = []
        return snapshot

    def reset(self):
        self._clock.reset()
        self._invalidate_cache()
        return self.snapshot()

    def _invalidate_cache(self):
        self._aggregation_cache.clear()
        self._snapshot_cache.clear()

    @classmethod
    def _serialize_aggregated(cls, row):
        start = cls._datetime(row["start_time"])
        end = cls._datetime(row["end_time"])
        return {
            "period": row["period"], "time": end.strftime(TIME_FORMAT), "datetime": end.strftime(TIME_FORMAT),
            "start_time": start.strftime(TIME_FORMAT), "end_time": end.strftime(TIME_FORMAT),
            "open": cls._value(row["open"]), "high": cls._value(row["high"]), "low": cls._value(row["low"]), "close": cls._value(row["close"]),
            "volume": cls._value(row["volume"]), "turnover": cls._value(row["turnover"]),
            "source_bar_count": int(row["source_bar_count"]), "complete": bool(row["complete"]),
        }

    @classmethod
    def _serialize_base(cls, row):
        timestamp = cls._datetime(row["timestamp"])
        return {"time": timestamp.strftime(TIME_FORMAT), "datetime": timestamp.strftime(TIME_FORMAT), "open": cls._value(row["open"]), "high": cls._value(row["high"]), "low": cls._value(row["low"]), "close": cls._value(row["close"]), "volume": cls._value(row["volume"]), "turnover": cls._value(row["turnover"])}

    @staticmethod
    def _datetime(value):
        return value.to_pydatetime() if hasattr(value, "to_pydatetime") else value

    @staticmethod
    def _value(value):
        if isinstance(value, Decimal):
            return float(value)
        if hasattr(value, "item"):
            return value.item()
        return value

ReplaySession = CryptoReplaySession
