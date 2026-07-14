from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import pandas as pd

from .aggregator import aggregate_bars
from .models import IntradayRange, ReplayPeriod


_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def _format_timestamp(value: object) -> str:
    return pd.Timestamp(value).strftime(_TIME_FORMAT)


def _serialize_aggregated_bar(row: pd.Series) -> dict[str, object]:
    return {
        "period": str(row["period"]),
        "start_time": _format_timestamp(row["start_time"]),
        "end_time": _format_timestamp(row["end_time"]),
        "open": float(row["open"]),
        "high": float(row["high"]),
        "low": float(row["low"]),
        "close": float(row["close"]),
        "volume": int(row["volume"]),
        "amount": float(row["amount"]),
        "source_bar_count": int(row["source_bar_count"]),
        "complete": bool(row["complete"]),
    }


def _volume_point(bar: dict[str, object]) -> dict[str, object]:
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

    def to_dict(self) -> dict[str, Any]:
        return {
            "period": self.period,
            "window_start": self.window_start.strftime(_TIME_FORMAT),
            "window_end": self.window_end.strftime(_TIME_FORMAT),
            "kline_data": self.kline_data,
            "volume_data": self.volume_data,
            "has_earlier": self.has_earlier,
            "has_later": self.has_later,
            "read_only": self.read_only,
        }


class ChartWindowService:
    def __init__(self, data_service: object):
        self.data_service = data_service

    def load(
        self,
        *,
        stock_code: str,
        period: ReplayPeriod | str,
        range_start: datetime,
        range_end: datetime,
        current_time: datetime,
        read_only: bool,
    ) -> ChartWindowResult:
        replay_period = ReplayPeriod.parse(period)
        effective_end = range_end if read_only else min(range_end, current_time)
        if range_start > effective_end:
            raise ValueError("range_start must not exceed the visible end")

        frame = self.data_service.get_30m(stock_code, range_start, effective_end)
        aggregated = aggregate_bars(frame, replay_period, effective_end)
        visible = aggregated.loc[
            (aggregated["end_time"] >= pd.Timestamp(range_start))
            & (aggregated["end_time"] <= pd.Timestamp(effective_end))
        ]
        serialized = [_serialize_aggregated_bar(row) for _, row in visible.iterrows()]
        coverage = self._coverage(stock_code)

        return ChartWindowResult(
            period=replay_period.value,
            window_start=range_start,
            window_end=effective_end,
            kline_data=serialized,
            volume_data=[_volume_point(bar) for bar in serialized],
            has_earlier=bool(coverage and coverage.start < range_start),
            has_later=bool(read_only and coverage and coverage.end > effective_end),
            read_only=read_only,
        )

    def _coverage(self, stock_code: str) -> IntradayRange | None:
        cache = getattr(self.data_service, "cache", None)
        coverage = getattr(cache, "coverage", None)
        if not callable(coverage):
            return None
        return coverage(stock_code)
