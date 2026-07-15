from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

import pandas as pd

from .aggregator import aggregate_bars
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

    def load(self, *, symbol: str, source: str, period: CryptoPeriod | str, range_start: datetime, range_end: datetime, current_time: datetime, read_only: bool) -> CryptoChartWindowResult:
        replay_period = CryptoPeriod.parse(period)
        range_start = utc_datetime(range_start)
        range_end = utc_datetime(range_end)
        current_time = utc_datetime(current_time)
        effective_end = range_end if read_only else min(range_end, current_time)
        if range_start > effective_end:
            raise ValueError("range_start must not exceed the visible end")
        fetch_start = self._bucket_start(range_start, replay_period)
        bundle = self.data_service.get_bundle(symbol, fetch_start, effective_end, source=source)
        aggregated = aggregate_bars(bundle.trade_bars, replay_period, effective_end)
        visible = aggregated.loc[(pd.to_datetime(aggregated["end_time"], utc=True) >= pd.Timestamp(range_start)) & (pd.to_datetime(aggregated["end_time"], utc=True) <= pd.Timestamp(effective_end))]
        serialized = [self._serialize(row) for _, row in visible.iterrows()]
        coverage = self._coverage(bundle.source, symbol)
        return CryptoChartWindowResult(
            source=bundle.source, symbol=symbol.upper(), period=replay_period.value,
            window_start=range_start, window_end=effective_end,
            kline_data=serialized, volume_data=[self._volume(item) for item in serialized],
            has_earlier=bool(coverage and coverage.start < range_start),
            has_later=bool(read_only and coverage and coverage.end > effective_end), read_only=read_only,
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
        mark = coverage(source, symbol, "mark")
        if trade is None:
            return mark
        if mark is None:
            return trade
        return CryptoRange(max(trade.start, mark.start), min(trade.end, mark.end))

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
