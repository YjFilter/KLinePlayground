from __future__ import annotations

from collections.abc import Hashable
from datetime import date, datetime

import pandas as pd

from .models import AGGREGATED_COLUMNS, PeriodBoundaryIndex, ReplayPeriod


def aggregate_bars(
    base_bars: pd.DataFrame,
    period: ReplayPeriod | str,
    current_time: datetime,
    *,
    boundary_index: PeriodBoundaryIndex | None = None,
) -> pd.DataFrame:
    """Aggregate revealed 30-minute bars without reading future OHLCV values."""
    replay_period = ReplayPeriod.parse(period)
    revealed = _revealed_bars(base_bars, current_time)
    if revealed.empty:
        return pd.DataFrame(columns=AGGREGATED_COLUMNS)

    if replay_period is ReplayPeriod.MINUTE_30:
        return _map_30m_bars(revealed, replay_period)

    if replay_period in (ReplayPeriod.SESSION_4H, ReplayPeriod.DAILY):
        bucket_keys = revealed["datetime"].dt.date
    else:
        bucket_keys = revealed["datetime"].map(_iso_week_key)

    records = [
        _aggregate_group(group, replay_period, boundary_index=boundary_index)
        for _, group in revealed.groupby(bucket_keys, sort=False)
    ]
    return pd.DataFrame.from_records(records, columns=AGGREGATED_COLUMNS)


def _revealed_bars(base_bars: pd.DataFrame, current_time: datetime) -> pd.DataFrame:
    frame = base_bars.copy()
    frame["datetime"] = pd.to_datetime(frame["datetime"])
    cutoff = pd.Timestamp(current_time)
    return frame.loc[frame["datetime"] <= cutoff].sort_values("datetime").reset_index(drop=True)


def _map_30m_bars(frame: pd.DataFrame, period: ReplayPeriod) -> pd.DataFrame:
    result = pd.DataFrame(
        {
            "period": period.value,
            "start_time": frame["datetime"],
            "end_time": frame["datetime"],
            "open": frame["open"],
            "high": frame["high"],
            "low": frame["low"],
            "close": frame["close"],
            "volume": frame["volume"],
            "amount": frame["amount"],
            "source_bar_count": 1,
            "complete": True,
        }
    )
    return result.loc[:, AGGREGATED_COLUMNS].reset_index(drop=True)


def _aggregate_group(
    group: pd.DataFrame,
    period: ReplayPeriod,
    *,
    boundary_index: PeriodBoundaryIndex | None,
) -> dict[str, object]:
    first = group.iloc[0]
    last = group.iloc[-1]
    end_time = last["datetime"].to_pydatetime()
    session_date = end_time.date()
    return {
        "period": period.value,
        "start_time": first["datetime"],
        "end_time": last["datetime"],
        "open": first["open"],
        "high": group["high"].max(),
        "low": group["low"].min(),
        "close": last["close"],
        "volume": group["volume"].sum(),
        "amount": group["amount"].sum(),
        "source_bar_count": len(group),
        "complete": _is_complete(period, end_time, session_date, boundary_index),
    }


def _is_complete(
    period: ReplayPeriod,
    end_time: datetime,
    session_date: date,
    boundary_index: PeriodBoundaryIndex | None,
) -> bool:
    if boundary_index is None or session_date in boundary_index.incomplete_sessions:
        return False
    if period in (ReplayPeriod.SESSION_4H, ReplayPeriod.DAILY):
        return end_time in boundary_index.session_ends
    return end_time in boundary_index.week_ends and end_time in boundary_index.session_ends


def _iso_week_key(timestamp: pd.Timestamp) -> Hashable:
    iso_calendar = timestamp.isocalendar()
    return iso_calendar.year, iso_calendar.week
