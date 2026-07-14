"""Immutable trading-day replay window calculation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

import pandas as pd


@dataclass(frozen=True)
class TrainingWindow:
    """A replay frame bounded by distinct data-bearing trading dates."""

    start_time: datetime
    cutoff_time: datetime
    trading_dates: tuple[date, ...]
    replay_bars: pd.DataFrame


def build_training_window(
    base_bars: pd.DataFrame,
    start_time: datetime,
    max_training_days: int,
) -> TrainingWindow:
    """Build a replay window beginning exactly at ``start_time``.

    ``max_training_days`` counts distinct dates present in the normalized base
    data. Zero selects every remaining data-bearing date.
    """
    if max_training_days < 0:
        raise ValueError("max_training_days must be non-negative")
    if "datetime" not in base_bars.columns:
        raise ValueError("base_bars must contain a datetime column")

    frame = base_bars.copy(deep=True)
    frame["datetime"] = pd.to_datetime(
        frame["datetime"],
        errors="coerce",
        format="mixed",
    )
    if frame["datetime"].isna().any():
        raise ValueError("base_bars contains invalid datetime values")
    has_duplicate_timestamps = frame["datetime"].duplicated().any()
    has_unsorted_timestamps = not frame["datetime"].is_monotonic_increasing
    if has_duplicate_timestamps or has_unsorted_timestamps:
        raise ValueError("base_bars timestamps must be unique and increasing")

    normalized_start = pd.Timestamp(start_time)
    if not frame["datetime"].eq(normalized_start).any():
        raise ValueError("start_time must exist in base_bars")

    remaining = frame.loc[frame["datetime"] >= normalized_start].copy()
    available_dates = tuple(remaining["datetime"].dt.date.drop_duplicates().tolist())
    selected_dates = (
        available_dates
        if max_training_days == 0
        else available_dates[:max_training_days]
    )
    if not selected_dates:
        raise ValueError("no trading dates available from start_time")

    final_date = selected_dates[-1]
    cutoff_timestamp = remaining.loc[
        remaining["datetime"].dt.date == final_date,
        "datetime",
    ].iloc[-1]
    replay_bars = remaining.loc[
        (remaining["datetime"] >= normalized_start)
        & (remaining["datetime"] <= cutoff_timestamp)
    ].reset_index(drop=True)

    return TrainingWindow(
        start_time=normalized_start.to_pydatetime(),
        cutoff_time=cutoff_timestamp.to_pydatetime(),
        trading_dates=selected_dates,
        replay_bars=replay_bars,
    )


__all__ = ["TrainingWindow", "build_training_window"]
