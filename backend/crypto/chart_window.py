from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

import pandas as pd
import numpy as np

from .aggregator import aggregate_bars, normalize_base_bars
from .models import CryptoPeriod, CryptoRange, utc_datetime

TIME_FORMAT = "%Y-%m-%d %H:%M:%S"

@dataclass(frozen=True)
class CryptoChartWindowResult:
    source: str
    symbol: str
    period: str
    window_start: datetime
    window_end: datetime
    kline_data: list[dict[str, object]]
    volume_data: list[dict[str, object]]
    has_earlier: bool
    has_later: bool
    read_only: bool
    base_bars: pd.DataFrame | None = field(default=None, repr=False, compare=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source, "symbol": self.symbol, "period": self.period,
            "window_start": self.window_start.strftime(TIME_FORMAT), "window_end": self.window_end.strftime(TIME_FORMAT),
            "kline_data": self.kline_data, "volume_data": self.volume_data,
            "has_earlier": self.has_earlier, "has_later": self.has_later, "read_only": self.read_only,
        }

class CryptoChartWindowService:
    def __init__(self, data_service):
        self.data_service = data_service

    def load(self, *, symbol: str, source: str, period: CryptoPeriod | str, range_start: datetime, range_end: datetime, current_time: datetime, read_only: bool, trade_bars: pd.DataFrame | None = None) -> CryptoChartWindowResult:
        replay_period = CryptoPeriod.parse(period)
        range_start = utc_datetime(range_start)
        range_end = utc_datetime(range_end)
        current_time = utc_datetime(current_time)
        effective_end = range_end if read_only else min(range_end, current_time)
        if range_start > effective_end:
            raise ValueError("range_start must not exceed the visible end")
        fetch_start = self._bucket_start(range_start, replay_period)
        resolved_source = source
        if trade_bars is None:
            chart_loader = getattr(self.data_service, "get_chart_bars", None)
            if callable(chart_loader):
                resolved_source, trade_bars = chart_loader(symbol, fetch_start, effective_end, source=source)
            else:
                bundle = self.data_service.get_bundle(symbol, fetch_start, effective_end, source=source)
                resolved_source, trade_bars = bundle.source, bundle.trade_bars
        normalized = normalize_base_bars(trade_bars)
        base_bars = normalized.loc[
            (normalized["timestamp"] >= pd.Timestamp(fetch_start))
            & (normalized["timestamp"] <= pd.Timestamp(effective_end))
        ].reset_index(drop=True)
        base_bars = normalize_base_bars(base_bars)
        aggregated = aggregate_bars(base_bars, replay_period, effective_end)
        visible = aggregated.loc[(pd.to_datetime(aggregated["end_time"], utc=True) >= pd.Timestamp(range_start)) & (pd.to_datetime(aggregated["end_time"], utc=True) <= pd.Timestamp(effective_end))]
        serialized = self._serialize_many(visible)
        coverage = self._coverage(resolved_source, symbol)
        return CryptoChartWindowResult(
            source=resolved_source, symbol=symbol.upper(), period=replay_period.value,
            window_start=range_start, window_end=effective_end,
            kline_data=serialized, volume_data=[self._volume(item) for item in serialized],
            has_earlier=bool(coverage and coverage.start < range_start),
            has_later=bool(read_only and coverage and coverage.end > effective_end), read_only=read_only,
            base_bars=base_bars,
        )

    @staticmethod
    def _bucket_start(value: datetime, period: CryptoPeriod) -> datetime:
        timestamp = pd.Timestamp(value)
        if period == CryptoPeriod.WEEKLY:
            return (timestamp.normalize() - pd.Timedelta(days=timestamp.weekday())).to_pydatetime()
        if period == CryptoPeriod.DAILY:
            return timestamp.normalize().to_pydatetime()
        minutes = {
            CryptoPeriod.MINUTE_5: 5, CryptoPeriod.MINUTE_15: 15,
            CryptoPeriod.MINUTE_30: 30, CryptoPeriod.HOUR_1: 60,
            CryptoPeriod.HOUR_4: 240,
        }[period]
        minute_of_day = timestamp.hour * 60 + timestamp.minute
        bucket_minutes = minute_of_day - minute_of_day % minutes
        return (timestamp.normalize() + pd.Timedelta(minutes=bucket_minutes)).to_pydatetime()

    def _coverage(self, source, symbol) -> CryptoRange | None:
        cache = getattr(self.data_service, "cache", None)
        coverage = getattr(cache, "coverage", None)
        if not callable(coverage):
            return None
        trade = coverage(source, symbol, "trade")
        return trade

    @classmethod
    def _serialize_many(cls, frame):
        if frame.empty:
            return []
        start_times = cls._time_strings(frame["start_time"])
        end_times = cls._time_strings(frame["end_time"])
        periods = frame["period"].astype(str).to_numpy()
        numeric = [
            pd.to_numeric(frame[column], errors="coerce").to_numpy(dtype=float)
            for column in ("open", "high", "low", "close", "volume", "turnover")
        ]
        counts = frame["source_bar_count"].to_numpy(dtype=int)
        complete = frame["complete"].to_numpy(dtype=bool)
        return [
            {
                "period": str(period), "time": str(end_time),
                "start_time": str(start_time), "end_time": str(end_time),
                "open": float(open_value), "high": float(high_value),
                "low": float(low_value), "close": float(close_value),
                "volume": float(volume), "turnover": float(turnover),
                "source_bar_count": int(source_bar_count), "complete": bool(is_complete),
            }
            for period, start_time, end_time, open_value, high_value, low_value,
            close_value, volume, turnover, source_bar_count, is_complete in zip(
                periods, start_times, end_times, *numeric, counts, complete
            )
        ]

    @staticmethod
    def _time_strings(values):
        timestamps = pd.to_datetime(values, utc=True).dt.tz_localize(None).to_numpy(dtype="datetime64[s]")
        return np.char.replace(np.datetime_as_string(timestamps, unit="s"), "T", " ")

    @classmethod
    def _serialize(cls, row):
        start = pd.Timestamp(row["start_time"]).to_pydatetime()
        end = pd.Timestamp(row["end_time"]).to_pydatetime()
        return {
            "period": str(row["period"]), "time": end.strftime(TIME_FORMAT),
            "start_time": start.strftime(TIME_FORMAT), "end_time": end.strftime(TIME_FORMAT),
            "open": cls._number(row["open"]), "high": cls._number(row["high"]), "low": cls._number(row["low"]), "close": cls._number(row["close"]),
            "volume": cls._number(row["volume"]), "turnover": cls._number(row["turnover"]),
            "source_bar_count": int(row["source_bar_count"]), "complete": bool(row["complete"]),
        }

    @staticmethod
    def _number(value):
        if isinstance(value, Decimal):
            return float(value)
        if hasattr(value, "item"):
            return value.item()
        return value

    @staticmethod
    def _volume(bar):
        return {"time": bar["end_time"], "value": bar["volume"], "color": "#ff4d4f" if bar["close"] >= bar["open"] else "#008000"}

ChartWindowResult = CryptoChartWindowResult
ChartWindowService = CryptoChartWindowService
