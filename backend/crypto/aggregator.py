from __future__ import annotations

from datetime import datetime, timedelta
from typing import Final

import pandas as pd

from .models import BASE_INTERVAL_MINUTES, CryptoPeriod, utc_datetime

AGGREGATED_COLUMNS: Final[tuple[str, ...]] = (
    "period", "start_time", "end_time", "open", "high", "low", "close",
    "volume", "turnover", "source_bar_count", "complete",
)

_PERIOD_MINUTES = {
    CryptoPeriod.MINUTE_1: 1,
    CryptoPeriod.MINUTE_3: 3,
    CryptoPeriod.MINUTE_5: 5,
    CryptoPeriod.MINUTE_15: 15,
    CryptoPeriod.MINUTE_30: 30,
    CryptoPeriod.HOUR_1: 60,
    CryptoPeriod.HOUR_2: 120,
    CryptoPeriod.HOUR_3: 180,
    CryptoPeriod.HOUR_4: 240,
    CryptoPeriod.HOUR_6: 360,
    CryptoPeriod.HOUR_8: 480,
    CryptoPeriod.HOUR_12: 720,
    CryptoPeriod.DAILY: 1440,
    CryptoPeriod.DAY_2: 2880,
    CryptoPeriod.DAY_3: 4320,
    CryptoPeriod.WEEKLY: 10080,
}

_NUMERIC_COLUMNS = ("open", "high", "low", "close", "volume", "turnover")
_NORMALIZED_ATTR = "crypto_base_bars_normalized"


def normalize_base_bars(base_bars: pd.DataFrame) -> pd.DataFrame:
    if base_bars.attrs.get(_NORMALIZED_ATTR):
        return base_bars
    frame = base_bars.copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    frame = frame.sort_values("timestamp").drop_duplicates("timestamp", keep="last").reset_index(drop=True)
    for column in _NUMERIC_COLUMNS:
        if column not in frame.columns:
            frame[column] = 0.0
        else:
            frame[column] = pd.to_numeric(frame[column], errors="coerce").astype(float)
    frame.attrs[_NORMALIZED_ATTR] = True
    return frame

def aggregate_bars(base_bars: pd.DataFrame, period: CryptoPeriod | str, current_time: datetime, *, base_interval_minutes: int = BASE_INTERVAL_MINUTES) -> pd.DataFrame:
    replay_period = CryptoPeriod.parse(period)
    if base_bars.empty:
        return pd.DataFrame(columns=AGGREGATED_COLUMNS)
    frame = normalize_base_bars(base_bars)
    current = pd.Timestamp(utc_datetime(current_time))
    revealed_count = int(frame["timestamp"].searchsorted(current, side="right"))
    revealed = frame.iloc[:revealed_count]
    if revealed.empty:
        return pd.DataFrame(columns=AGGREGATED_COLUMNS)
    minutes = _PERIOD_MINUTES[replay_period]
    if replay_period == CryptoPeriod.MINUTE_1 and base_interval_minutes == 1:
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
    # 用 assign 避免复制 7 列 × 100 万行的 DataFrame（仅创建 bucket 列）
    if replay_period == CryptoPeriod.WEEKLY:
        day_start = revealed["timestamp"].dt.normalize()
        bucket = day_start - pd.to_timedelta(revealed["timestamp"].dt.weekday, unit="D")
    elif replay_period == CryptoPeriod.DAILY:
        bucket = revealed["timestamp"].dt.normalize()
    elif replay_period == CryptoPeriod.DAY_2:
        bucket = revealed["timestamp"].dt.floor("2D")
    elif replay_period == CryptoPeriod.DAY_3:
        bucket = revealed["timestamp"].dt.floor("3D")
    else:
        bucket = revealed["timestamp"].dt.floor(f"{minutes}min")
    revealed = revealed.assign(bucket=bucket)
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
    bucket_end = bucket + pd.Timedelta(minutes=minutes - base_interval_minutes)
    aggregated["complete"] = (
        (aggregated["source_bar_count"] == minutes // base_interval_minutes)
        & (aggregated["start_time"] == bucket)
        & (aggregated["end_time"] == bucket_end)
    )
    aggregated.insert(0, "period", replay_period.value)
    return aggregated.reset_index(drop=True).loc[:, AGGREGATED_COLUMNS]

def _bucket_start(timestamp: pd.Timestamp, period: CryptoPeriod) -> pd.Timestamp:
    timestamp = pd.Timestamp(timestamp)
    if period == CryptoPeriod.WEEKLY:
        day_start = timestamp.normalize()
        return day_start - pd.Timedelta(days=timestamp.weekday())
    if period == CryptoPeriod.DAILY:
        return timestamp.normalize()
    if period == CryptoPeriod.DAY_2:
        return timestamp.floor("2D")
    if period == CryptoPeriod.DAY_3:
        return timestamp.floor("3D")
    minutes = _PERIOD_MINUTES[period]
    total_minutes = timestamp.hour * 60 + timestamp.minute
    bucket_minutes = total_minutes - total_minutes % minutes
    return timestamp.normalize() + pd.Timedelta(minutes=bucket_minutes)


def _bucket_start_series(timestamps: pd.DatetimeIndex, period: CryptoPeriod) -> pd.DatetimeIndex:
    """向量化版本的 _bucket_start，供回放时钟预计算周期边界时批量调用。"""
    if period == CryptoPeriod.WEEKLY:
        day_start = timestamps.normalize()
        return day_start - pd.to_timedelta(timestamps.weekday, unit="D")
    if period == CryptoPeriod.DAILY:
        return timestamps.normalize()
    if period == CryptoPeriod.DAY_2:
        return timestamps.floor("2D")
    if period == CryptoPeriod.DAY_3:
        return timestamps.floor("3D")
    minutes = _PERIOD_MINUTES[period]
    total_minutes = timestamps.hour * 60 + timestamps.minute
    bucket_minutes = total_minutes - total_minutes % minutes
    return timestamps.normalize() + pd.to_timedelta(bucket_minutes, unit="m")
