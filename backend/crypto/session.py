from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Any

import pandas as pd

from .aggregator import aggregate_bars
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
        frame = base_bars.copy()
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
        frame = frame.sort_values("timestamp").reset_index(drop=True)
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

    @property
    def clock(self):
        return self._clock

    @property
    def base_bars(self):
        return self._base_bars

    def snapshot(self) -> dict[str, Any]:
        current_time = self._clock.current_time
        aggregated = aggregate_bars(self._base_bars, self._clock.active_period, current_time)
        plan = self._clock.plan_next()
        kline_data = [self._serialize_aggregated(row) for row in aggregated.to_dict("records")]
        current_base = self._base_bars.loc[self._base_bars["timestamp"] == pd.Timestamp(current_time)]
        current_base_bar = None if current_base.empty else self._serialize_base(current_base.iloc[0])
        current_complete = bool(aggregated.iloc[-1]["complete"]) if not aggregated.empty else False
        return {
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

    def set_period(self, period):
        self._clock.set_period(period)
        return self.snapshot()

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
        snapshot = self.snapshot()
        snapshot["completed_times"] = [value.strftime(TIME_FORMAT) for value in completed]
        snapshot["order_events"] = []
        return snapshot

    def reset(self):
        self._clock.reset()
        return self.snapshot()

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
