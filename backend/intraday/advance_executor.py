"""Sequential base-bar advance executor.

This module provides a framework-independent executor that consumes a
``ReplayAdvance`` plan and invokes dependency-injected callbacks exactly once
per hidden base timestamp, in strict chronological order.

The executor deliberately does NOT import Flask, ``trade_simulator_enhanced``,
``order_manager``, ``app_enhanced``, or any frontend module. It also does NOT
implement order trigger rules, price-limit (涨跌停) rules, transaction costs, or
T+1 settlement. All trading semantics are delegated to the injected callbacks.

See ``docs/superpowers/specs/2026-07-12-multi-timeframe-intraday-replay-design.md``
section 9.2 for the intended per-bar execution order.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import TYPE_CHECKING, Any, Optional, Protocol

from backend.intraday.models import ReplayAdvance

if TYPE_CHECKING:  # pragma: no cover - import only for static type checkers
    from backend.intraday.replay_clock import ReplayClock


class AdvanceCallbacks(Protocol):
    """Dependency-injected callbacks invoked once per base bar.

    Implementations may wrap a ``PendingOrderManager``, a trade simulator, a
    previous-close index, or any other collaborator. The executor treats them
    as opaque and calls them in a fixed order.
    """

    def fetch_base_bar(self, timestamp: datetime) -> dict[str, Any]:
        """Return the underlying 30-minute bar revealed at ``timestamp``."""

    def update_price_and_state(self, timestamp: datetime, bar: dict[str, Any]) -> None:
        """Update the current price and any downstream state after revealing a bar."""

    def get_previous_close(self, trade_date: date) -> float | None:
        """Return the previous trading day close for the given trade date.

        ``trade_date`` is derived from the base bar timestamp's ``date()`` so
        that every base bar inside the same trading day resolves to the same
        previous close, never to the previous 30-minute bar's close.
        """

    def process_pending_orders(
        self,
        timestamp: datetime,
        bar: dict[str, Any],
        prev_close: float | None,
    ) -> list[dict[str, Any]]:
        """Process pending orders against the revealed bar and return events.

        The executor does not interpret the returned events; it only preserves
        their order alongside the producing base bar.
        """


@dataclass(frozen=True)
class AdvanceExecutionResult:
    """Outcome of executing a ``ReplayAdvance`` plan.

    All collection fields are tuples so the result is immutable and safe to
    return from a pure executor.
    """

    success: bool
    finished: bool
    completed_times: tuple[datetime, ...]
    events: tuple[dict[str, Any], ...]
    failed_time: datetime | None
    error: str | None


def execute_advance(
    plan: ReplayAdvance,
    callbacks: AdvanceCallbacks,
    *,
    clock: Optional["ReplayClock"] = None,
) -> AdvanceExecutionResult:
    """Execute ``plan`` by processing each base bar in chronological order.

    The plan's ``base_bar_times`` are processed in the exact order supplied by
    the plan (the replay clock guarantees they are strictly increasing). For
    every base bar the executor invokes the four callbacks in this fixed
    order:

    1. ``fetch_base_bar(timestamp)`` -> ``bar``
    2. ``update_price_and_state(timestamp, bar)``
    3. ``get_previous_close(timestamp.date())`` -> ``prev_close``
    4. ``process_pending_orders(timestamp, bar, prev_close)`` -> ``events``

    Events returned by step 4 are collected in the same order the base bars
    are processed. The replay clock is committed (via ``clock.advance(plan)``)
    only after every base bar in the plan succeeds. On any callback failure the
    clock is left untouched and the result reports the failed timestamp
    together with the completed timestamps and the partial events collected so
    far.

    A finished plan (``plan.finished`` is ``True``) performs no work and returns
    an explicit finished result, so callers cannot accidentally enter a loop.

    The executor never re-sorts or de-duplicates ``base_bar_times``; it trusts
    the plan's order, which is the contract established by ``ReplayClock``.
    """
    if plan.finished:
        return AdvanceExecutionResult(
            success=True,
            finished=True,
            completed_times=(),
            events=(),
            failed_time=None,
            error=None,
        )

    completed: list[datetime] = []
    events: list[dict[str, Any]] = []

    for timestamp in plan.base_bar_times:
        try:
            bar = callbacks.fetch_base_bar(timestamp)
            callbacks.update_price_and_state(timestamp, bar)
            prev_close = callbacks.get_previous_close(timestamp.date())
            bar_events = callbacks.process_pending_orders(timestamp, bar, prev_close)
        except Exception as error:  # noqa: BLE001 - executor must capture any callback failure
            # Do NOT commit the replay clock. Preserve completed timestamps and
            # the partial events collected before the failure so callers can
            # report, retry, or roll back side effects inside their callbacks.
            message = str(error)
            return AdvanceExecutionResult(
                success=False,
                finished=False,
                completed_times=tuple(completed),
                events=tuple(events),
                failed_time=timestamp,
                error=f"{type(error).__name__}: {message}" if message else type(error).__name__,
            )

        completed.append(timestamp)
        if bar_events:
            events.extend(bar_events)

    # Every base bar succeeded, so it is now safe to commit the replay clock.
    if clock is not None:
        clock.advance(plan)

    return AdvanceExecutionResult(
        success=True,
        finished=False,
        completed_times=tuple(completed),
        events=tuple(events),
        failed_time=None,
        error=None,
    )


__all__ = [
    "AdvanceCallbacks",
    "AdvanceExecutionResult",
    "execute_advance",
]
