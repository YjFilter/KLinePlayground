"""Previous-trading-day close index for the 30-minute intraday engine.

This module provides a pure, immutable lookup that maps every trading date
present in normalized 30-minute data to the previous data-bearing trading
date's final 30-minute close. It is consumed by the trading engine to compute
limit-up / limit-down prices (which must use the previous trading day close,
not the previous 30-minute bar close, per the multi-timeframe intraday replay
design section 9.3).

Design notes
------------
* ``build_previous_close_index`` is a pure function: same input always yields
  an equal ``PreviousCloseIndex``, and the input ``DataFrame`` is never
  mutated.
* ``PreviousCloseIndex`` is a frozen dataclass wrapping a
  ``MappingProxyType`` so callers cannot mutate the lookup after construction.
* "Previous trading day" means the previous *data-bearing* trading date —
  i.e. the previous date that actually has at least one 30-minute bar in the
  source frame. Weekends, holidays, and suspensions are handled implicitly by
  following the actual data order. No calendar assumption is made.
* "Final close" of a trading date is the close of the last 30-minute bar of
  that date in data order. Incomplete / short sessions use their actual last
  bar, not a filled or synthesized value.
* Duplicate or unsorted timestamps raise ``ValueError``. The builder never
  silently sorts the input, because sorting would mask upstream data bugs.
* The first trading date present in the data maps to ``None``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from types import MappingProxyType
from typing import Mapping

import pandas as pd


@dataclass(frozen=True)
class PreviousCloseIndex:
    """Immutable lookup mapping each trading date to the previous
    data-bearing trading date's final 30-minute close.

    The first trading date present in the source data maps to ``None``.
    Queries for trading dates that are not present in the source data raise
    ``ValueError`` — the index never silently returns ``None`` for an unknown
    date, because that would mask programming errors in the caller.
    """

    _closes_by_date: Mapping[date, float | None]
    trading_dates: tuple[date, ...]

    def previous_close_for_date(self, trading_date: date) -> float | None:
        """Return the previous trading day's final close for ``trading_date``.

        Accepts ``datetime.date``, ``datetime.datetime``, or
        ``pandas.Timestamp``. Raises ``ValueError`` if ``trading_date`` is not
        a trading date present in the source data.
        """
        normalized = _to_date(trading_date)
        if normalized not in self._closes_by_date:
            raise ValueError(f"unknown trading date: {normalized}")
        return self._closes_by_date[normalized]

    def previous_close(self, timestamp: datetime) -> float | None:
        """Return the previous trading day's final close for the trading date
        containing ``timestamp``.

        Accepts ``datetime.datetime`` or ``pandas.Timestamp``. Raises
        ``ValueError`` if the trading date is not present in the source data.
        """
        normalized = _to_datetime(timestamp)
        return self.previous_close_for_date(normalized.date())

    def __contains__(self, trading_date: object) -> bool:
        try:
            normalized = _to_date(trading_date)
        except TypeError:
            return False
        return normalized in self._closes_by_date


def build_previous_close_index(base_bars: pd.DataFrame) -> PreviousCloseIndex:
    """Build an immutable previous-trading-day close index from normalized
    30-minute bars.

    Args:
        base_bars: A DataFrame with at least ``datetime`` and ``close``
            columns. Timestamps must be strictly increasing without
            duplicates. The frame is not modified.

    Returns:
        A ``PreviousCloseIndex``. The first trading date present in the data
        maps to ``None``; every subsequent trading date maps to the previous
        data-bearing trading date's final 30-minute bar close.

    Raises:
        ValueError: If required columns are missing, if datetime values
            cannot be parsed, if timestamps are duplicated, or if timestamps
            are not in strictly increasing order.
    """
    required = {"datetime", "close"}
    missing = sorted(required.difference(base_bars.columns))
    if missing:
        raise ValueError(f"missing required columns: {', '.join(missing)}")

    # Work on a copy so the caller's frame is never mutated. The copy is
    # cheap relative to the lookup cost amortized across a replay session.
    working = base_bars.copy()
    working["datetime"] = pd.to_datetime(working["datetime"], errors="coerce", format="mixed")

    if working["datetime"].isna().any():
        bad_count = int(working["datetime"].isna().sum())
        raise ValueError(
            f"invalid datetime values: {bad_count} row(s) could not be parsed"
        )

    if working["datetime"].duplicated().any():
        duplicates = (
            working.loc[
                working["datetime"].duplicated(keep=False), "datetime"
            ]
            .drop_duplicates()
            .tolist()
        )
        raise ValueError(f"duplicate timestamps: {duplicates}")

    # Reject unsorted input explicitly. We must NOT silently sort, because
    # sorting would hide upstream data-quality bugs and could cause the wrong
    # bar to be treated as a date's "final close".
    timestamps = working["datetime"].to_numpy()
    if len(timestamps) > 1 and not (timestamps[1:] > timestamps[:-1]).all():
        raise ValueError(
            "timestamps must be strictly increasing; unsorted input is rejected"
        )

    if working.empty:
        return PreviousCloseIndex(
            _closes_by_date=MappingProxyType({}),
            trading_dates=(),
        )

    # Group by trading date in data order. Because the input is strictly
    # increasing, dates appear in ascending order, so sort=False preserves the
    # real session sequence without re-sorting.
    own_close_by_date: dict[date, float] = {}
    trading_dates: list[date] = []
    trading_date_series = working["datetime"].dt.date
    for trading_date, group in working.groupby(trading_date_series, sort=False):
        # The last row in data order is the final 30-minute bar of this date.
        own_close_by_date[trading_date] = float(group.iloc[-1]["close"])
        trading_dates.append(trading_date)

    prev_close_by_date: dict[date, float | None] = {}
    for index, trading_date in enumerate(trading_dates):
        if index == 0:
            prev_close_by_date[trading_date] = None
        else:
            prev_close_by_date[trading_date] = own_close_by_date[
                trading_dates[index - 1]
            ]

    return PreviousCloseIndex(
        _closes_by_date=MappingProxyType(prev_close_by_date),
        trading_dates=tuple(trading_dates),
    )


def _to_date(value: object) -> date:
    """Coerce ``datetime``, ``date``, or ``pandas.Timestamp`` to ``date``."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    converted = getattr(value, "date", None)
    if callable(converted):
        result = converted()
        if isinstance(result, datetime):
            return result.date()
        if isinstance(result, date):
            return result
    raise TypeError(f"cannot coerce {value!r} to date")


def _to_datetime(value: object) -> datetime:
    """Coerce ``datetime``, ``pandas.Timestamp``, or ISO string to
    ``datetime``."""
    if isinstance(value, datetime):
        return value
    if hasattr(value, "to_pydatetime"):
        converted = value.to_pydatetime()
        if isinstance(converted, datetime):
            return converted
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError as error:
            raise ValueError(f"invalid timestamp: {value!r}") from error
    raise TypeError(f"cannot coerce {value!r} to datetime")
