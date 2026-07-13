"""Flask-independent intraday replay session controller.

This module provides ``IntradayReplaySession``, a framework-free orchestrator
that owns one canonical replay clock, the active display period, the revealed
aggregation, the next-boundary state, and period-aware trading advancement.

The session does NOT import Flask, ``app_enhanced``, frontend modules, or any
HTTP layer. It delegates trading execution to ``execute_trading_advance`` and
treats the simulator and order manager as opaque collaborators passed in at
construction time. The same collaborator objects are retained for the lifetime
of the session; ``reset()`` does not replace them.

Design notes
------------
* Construction validates that ``initial_time`` exists in the normalized
  30-minute timeline by delegating to ``ReplayClock``.
* ``snapshot()`` is a pure read: it never advances the replay clock or
  triggers trading side effects.
* ``set_period()`` only changes the active display period. It does not
  alter ``current_time``, account state, positions, pending orders, or
  trade history.
* ``advance()`` plans the next boundary via ``ReplayClock.plan_next()``,
  executes every hidden base bar through ``execute_trading_advance``,
  and returns the new snapshot together with ordered order events and
  completed base-bar timestamps.
* ``reset()`` restores the initial time and period without replacing the
  simulator, order manager, or any account/order state.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import pandas as pd

from .aggregator import aggregate_bars
from .models import BASE_INTERVAL, ReplayPeriod
from .replay_clock import ReplayClock
from .trading_context import PreviousCloseIndex, build_previous_close_index
from .trading_engine import execute_trading_advance

_AVAILABLE_PERIODS: tuple[str, ...] = (
    ReplayPeriod.MINUTE_30.value,
    ReplayPeriod.SESSION_4H.value,
    ReplayPeriod.DAILY.value,
    ReplayPeriod.WEEKLY.value,
)

_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"


class IntradayReplaySession:
    """Owns the canonical replay clock, active period, and trading advancement.

    Parameters
    ----------
    base_bars
        Normalized 30-minute DataFrame with columns: ``datetime``, ``open``,
        ``high``, ``low``, ``close``, ``volume``, ``amount``. Timestamps must
        be strictly increasing without duplicates.
    initial_time
        The starting replay position. Must exist in ``base_bars["datetime"]``.
    stock_code
        The stock code used for trading operations.
    simulator
        The trade simulator instance. Retained by reference; never copied or
        replaced.
    order_manager
        The pending order manager instance. Retained by reference; never
        copied or replaced.
    initial_period
        The initial display period. One of ``"30m"``, ``"4h_session"``,
        ``"daily"``, ``"weekly"``. Defaults to ``"daily"``.
    """

    def __init__(
        self,
        base_bars: pd.DataFrame,
        initial_time: datetime,
        stock_code: str,
        simulator: Any,
        order_manager: Any,
        initial_period: str = "daily",
    ) -> None:
        # Normalize base_bars into an internal copy so the caller's frame is
        # never mutated. The datetime column is coerced to pandas Timestamp
        # for consistent comparison throughout the session lifecycle.
        frame = base_bars.copy()
        frame["datetime"] = pd.to_datetime(
            frame["datetime"], errors="coerce", format="mixed"
        )
        if frame["datetime"].isna().any():
            raise ValueError("base_bars contains invalid datetime values")
        self._base_bars = frame

        # Extract the timestamp tuple for ReplayClock. Using to_pydatetime()
        # ensures the clock works with native datetime objects.
        timestamps = tuple(
            ts.to_pydatetime() for ts in frame["datetime"]
        )

        # ReplayClock validates that initial_time exists in the timeline and
        # that timestamps are strictly increasing without duplicates.
        self._clock = ReplayClock(
            timestamps,
            initial_time=initial_time,
            active_period=initial_period,
        )

        # PreviousCloseIndex maps each trading date to the previous
        # data-bearing trading date's final 30-minute close. This is used
        # by execute_trading_advance for limit-up/limit-down calculations.
        self._previous_closes: PreviousCloseIndex = build_previous_close_index(
            frame
        )

        # Retain collaborators by reference. Never copy or replace.
        self._simulator = simulator
        self._order_manager = order_manager
        self._stock_code = stock_code

        # Record initial state for reset().
        self._initial_time: datetime = self._clock.current_time
        self._initial_period: ReplayPeriod = self._clock.active_period

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        """Return the current replay state without advancing.

        The returned dictionary contains:

        - ``current_time``: ``YYYY-MM-DD HH:MM:SS`` string.
        - ``active_period``: one of ``30m``, ``4h_session``, ``daily``,
          ``weekly``.
        - ``base_interval``: always ``"30m"``.
        - ``available_periods``: the four periods in stable order.
        - ``current_bar_complete``: whether the current aggregated bar is
          complete.
        - ``next_boundary``: the next period boundary as a formatted string,
          or ``None`` if finished.
        - ``kline_data``: JSON-serializable list of aggregated bar dicts.
        - ``current_base_bar``: the 30-minute bar at ``current_time``, or
          ``None`` if not found.
        - ``finished``: ``True`` if there is no next boundary.
        """
        current_time = self._clock.current_time
        active_period = self._clock.active_period

        # Aggregate revealed bars only (no future data).
        aggregated = aggregate_bars(
            self._base_bars,
            active_period,
            current_time,
            boundary_index=self._clock.boundary_index,
        )

        # Determine next boundary and finished state without advancing.
        plan = self._clock.plan_next()
        next_boundary = plan.target_time
        finished = plan.finished

        # Current bar complete: the last aggregated bar's complete flag.
        if aggregated.empty:
            current_bar_complete = False
        else:
            current_bar_complete = bool(aggregated.iloc[-1]["complete"])

        # Current base bar: the 30-minute bar at current_time.
        current_base_bar = self._get_base_bar(current_time)

        # Serialize kline_data to JSON-compatible dicts.
        kline_data = self._serialize_kline(aggregated)

        return {
            "current_time": current_time.strftime(_TIME_FORMAT),
            "active_period": active_period.value,
            "base_interval": BASE_INTERVAL.value,
            "available_periods": list(_AVAILABLE_PERIODS),
            "current_bar_complete": current_bar_complete,
            "next_boundary": (
                next_boundary.strftime(_TIME_FORMAT)
                if next_boundary is not None
                else None
            ),
            "kline_data": kline_data,
            "current_base_bar": current_base_bar,
            "finished": finished,
        }

    def set_period(self, period: str) -> dict[str, Any]:
        """Switch the active display period and return a snapshot.

        This does NOT change ``current_time``, account state, positions,
        pending orders, or trade history.

        Parameters
        ----------
        period
            One of ``"30m"``, ``"4h_session"``, ``"daily"``, ``"weekly"``.

        Raises
        ------
        ValueError
            If ``period`` is not a valid :class:`ReplayPeriod`.
        """
        self._clock.set_period(period)
        return self.snapshot()

    def advance(self) -> dict[str, Any]:
        """Plan and execute the next active-period boundary.

        This calls ``ReplayClock.plan_next()`` to determine the target
        boundary and all hidden base bar timestamps, then delegates to
        ``execute_trading_advance`` to process every hidden bar in
        chronological order.

        Returns
        -------
        dict
            The new snapshot with two additional fields:

            - ``order_events``: list of order event dicts in processing order.
            - ``completed_times``: list of processed base-bar timestamps as
              ``YYYY-MM-DD HH:MM:SS`` strings.

        If the plan is finished (no next boundary), the snapshot is returned
        with empty ``order_events`` and ``completed_times``.
        """
        plan = self._clock.plan_next()

        if plan.finished:
            snap = self.snapshot()
            snap["order_events"] = []
            snap["completed_times"] = []
            return snap

        result = execute_trading_advance(
            plan=plan,
            clock=self._clock,
            base_bars=self._base_bars,
            previous_closes=self._previous_closes,
            simulator=self._simulator,
            order_manager=self._order_manager,
            stock_code=self._stock_code,
            display_period=self._clock.active_period,
        )

        if not result.success:
            raise RuntimeError(
                f"trading advance failed at {result.failed_time}: "
                f"{result.error}"
            )

        snap = self.snapshot()
        snap["order_events"] = [
            self._make_serializable(event) for event in result.events
        ]
        snap["completed_times"] = [
            ts.strftime(_TIME_FORMAT) for ts in result.completed_times
        ]
        return snap

    def reset(self) -> dict[str, Any]:
        """Restore the initial time and period without replacing collaborators.

        This does NOT create a new simulator or order manager, and does NOT
        clear account, position, pending order, or trade history state.
        """
        self._clock.reset()
        return self.snapshot()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_base_bar(self, timestamp: datetime) -> dict[str, Any] | None:
        """Return the 30-minute bar at ``timestamp`` as a serializable dict."""
        mask = self._base_bars["datetime"] == pd.Timestamp(timestamp)
        matching = self._base_bars.loc[mask]
        if matching.empty:
            return None
        row = matching.iloc[0]
        return {
            "datetime": timestamp.strftime(_TIME_FORMAT),
            "open": _to_float(row["open"]),
            "high": _to_float(row["high"]),
            "low": _to_float(row["low"]),
            "close": _to_float(row["close"]),
            "volume": _to_int(row["volume"]),
            "amount": _to_float(row["amount"]),
        }

    @staticmethod
    def _serialize_kline(df: pd.DataFrame) -> list[dict[str, Any]]:
        """Convert an aggregated DataFrame to JSON-serializable dicts."""
        if df.empty:
            return []
        records: list[dict[str, Any]] = []
        for _, row in df.iterrows():
            records.append(
                {
                    "period": str(row["period"]),
                    "start_time": _format_timestamp(row["start_time"]),
                    "end_time": _format_timestamp(row["end_time"]),
                    "open": _to_float(row["open"]),
                    "high": _to_float(row["high"]),
                    "low": _to_float(row["low"]),
                    "close": _to_float(row["close"]),
                    "volume": _to_int(row["volume"]),
                    "amount": _to_float(row["amount"]),
                    "source_bar_count": _to_int(row["source_bar_count"]),
                    "complete": bool(row["complete"]),
                }
            )
        return records

    @staticmethod
    def _make_serializable(obj: Any) -> Any:
        """Recursively convert an object to JSON-serializable Python types."""
        if isinstance(obj, dict):
            return {
                key: IntradayReplaySession._make_serializable(value)
                for key, value in obj.items()
            }
        if isinstance(obj, (list, tuple)):
            return [
                IntradayReplaySession._make_serializable(item) for item in obj
            ]
        if isinstance(obj, datetime):
            return obj.strftime(_TIME_FORMAT)
        if isinstance(obj, date):
            return obj.isoformat()
        if isinstance(obj, pd.Timestamp):
            return obj.strftime(_TIME_FORMAT)
        if hasattr(obj, "item"):
            # numpy scalar
            return obj.item()
        if isinstance(obj, (str, int, float, bool, type(None))):
            return obj
        # Fallback: stringify anything else.
        return str(obj)


def _to_float(value: Any) -> float:
    """Convert a value to a plain Python float."""
    if pd.isna(value):
        return 0.0
    return float(value)


def _to_int(value: Any) -> int:
    """Convert a value to a plain Python int."""
    if pd.isna(value):
        return 0
    return int(value)


def _format_timestamp(value: Any) -> str | None:
    """Format a timestamp as ``YYYY-MM-DD HH:MM:SS`` or return None."""
    if value is None or pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.strftime(_TIME_FORMAT)
    if isinstance(value, datetime):
        return value.strftime(_TIME_FORMAT)
    return str(value)


__all__ = ["IntradayReplaySession"]
