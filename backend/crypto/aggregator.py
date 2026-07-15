from __future__ import annotations

from datetime import datetime, timedelta
from typing import Final

import pandas as pd

from .models import CryptoPeriod, utc_datetime

AGGREGATED_COLUMNS: Final[tuple[str, ...]] = (
    "period", "start_time", "end_time", "open", "high", "low", "close",
    "volume", "turnover", "source_bar_count", "complete",
)

_PERIOD_MINUTES = {
    CryptoPeriod.MINUTE_5: 5,
    CryptoPeriod.MINUTE_15: 15,
    CryptoPeriod.MINUTE_30: 30,
    CryptoPeriod.HOUR_1: 60,
    CryptoPeriod.HOUR_4: 240,
    CryptoPeriod.DAILY: 1440,
    CryptoPeriod.WEEKLY: 10080,
}

def aggregate_bars(base_bars: pd.DataFrame, period: CryptoPeriod | str, current_time: datetime) -> pd.DataFrame:
    replay_period = CryptoPeriod.parse(period)
    if base_bars.empty:
        return pd.DataFrame(columns=AGGREGATED_COLUMNS)
    frame = base_bars.copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    current = pd.Timestamp(utc_datetime(current_time))
    revealed = frame.loc[frame["timestamp"] <= current].sort_values("timestamp").drop_duplicates("timestamp", keep="last")
    if revealed.empty:
        return pd.DataFrame(columns=AGGREGATED_COLUMNS)
    minutes = _PERIOD_MINUTES[replay_period]
    if replay_period == CryptoPeriod.MINUTE_5:
        result = pd.DataFrame({
            "period": replay_period.value,
            "start_time": revealed["timestamp"],
            "end_time": revealed["timestamp"],
            "open": revealed["open"],
            "high": revealed["high"],
            "low": revealed["low"],
            "close": revealed["close"],
            "volume": revealed["volume"] if "volume" in revealed else 0,
            "turnover": revealed["turnover"] if "turnover" in revealed else 0,
            "source_bar_count": 1,
            "complete": True,
        })
        return result.reset_index(drop=True).loc[:, AGGREGATED_COLUMNS]
    for column in ("open", "high", "low", "close", "volume", "turnover"):
        if column not in revealed.columns:
            revealed[column] = 0.0
        else:
            revealed[column] = pd.to_numeric(revealed[column], errors="coerce").astype(float)
    if replay_period == CryptoPeriod.WEEKLY:
        day_start = revealed["timestamp"].dt.normalize()
        revealed["bucket"] = day_start - pd.to_timedelta(revealed["timestamp"].dt.weekday, unit="D")
    elif replay_period == CryptoPeriod.DAILY:
        revealed["bucket"] = revealed["timestamp"].dt.normalize()
    else:
        revealed["bucket"] = revealed["timestamp"].dt.floor(f"{minutes}min")
    aggregated = revealed.groupby("bucket", sort=True).agg(
        start_time=("timestamp", "first"),
        end_time=("timestamp", "last"),
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
        turnover=("turnover", "sum"),
        source_bar_count=("timestamp", "size"),
    )
    bucket = aggregated.index.to_series(index=aggregated.index)
    bucket_end = bucket + pd.Timedelta(minutes=minutes - 5)
    aggregated["complete"] = (
        (aggregated["source_bar_count"] == minutes // 5)
        & (aggregated["start_time"] == bucket)
        & (aggregated["end_time"] == bucket_end)
    )
    aggregated.insert(0, "period", replay_period.value)
    return aggregated.reset_index(drop=True).loc[:, AGGREGATED_COLUMNS]

def _bucket_start(timestamp: pd.Timestamp, period: CryptoPeriod) -> pd.Timestamp:
    if period == CryptoPeriod.WEEKLY:
        day_start = timestamp.normalize()
        return day_start - pd.Timedelta(days=timestamp.weekday())
    if period == CryptoPeriod.DAILY:
        return timestamp.normalize()
    minutes = _PERIOD_MINUTES[period]
    total_minutes = timestamp.hour * 60 + timestamp.minute
    bucket_minutes = total_minutes - total_minutes % minutes
    return timestamp.normalize() + pd.Timedelta(minutes=bucket_minutes)
