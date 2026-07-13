"""TASK-010: IntradayReplaySession controller tests.

Black-box tests for the Flask-independent IntradayReplaySession that owns
one canonical replay clock, active display period, revealed aggregation,
next-boundary state, and period-aware trading advancement.

All tests use fake simulator and fake order manager. No real user database
is read or written. Only this test file and backend/intraday/session.py
are created.
"""

from __future__ import annotations

import json
import os
import sys
import unittest
from datetime import date, datetime
from typing import Any

import pandas as pd

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.intraday.models import ReplayPeriod
from backend.intraday.replay_clock import ReplayClock
from backend.intraday.trading_context import build_previous_close_index


# ---------------------------------------------------------------------------
# Deterministic offline 30-minute bar data
# ---------------------------------------------------------------------------

TIMES = ("10:00", "10:30", "11:00", "11:30", "13:30", "14:00", "14:30", "15:00")
STOCK_CODE = "600000"


def _bar(day: str, time_value: str, price: float = 10.0) -> dict[str, Any]:
    return {
        "datetime": pd.Timestamp(f"{day} {time_value}:00"),
        "open": price,
        "high": price + 0.2,
        "low": price - 0.2,
        "close": price + 0.1,
        "volume": 1000,
        "amount": 10000.0,
    }


def _flat_day(day: str, price: float = 10.0) -> list[dict[str, Any]]:
    return [_bar(day, t, price) for t in TIMES]


def _frame(*rows: dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def _four_day_frame() -> pd.DataFrame:
    """Four trading days spanning two ISO weeks.

    Week 1: 2025-01-02 (Thu), 2025-01-03 (Fri)
    Week 2: 2025-01-06 (Mon), 2025-01-07 (Tue)
    """
    return _frame(
        *(_flat_day("2025-01-02", 10.0)
          + _flat_day("2025-01-03", 11.0)
          + _flat_day("2025-01-06", 12.0)
          + _flat_day("2025-01-07", 13.0))
    )


def _timeline(frame: pd.DataFrame) -> tuple[datetime, ...]:
    return tuple(frame["datetime"].dt.to_pydatetime())


# ---------------------------------------------------------------------------
# Fake collaborators
# ---------------------------------------------------------------------------


class FakeSimulator:
    """Minimal simulator spy compatible with IntradayTradingCallbacks."""

    def __init__(self) -> None:
        self.updates: list[tuple[float, int]] = []
        self.trades: list[tuple] = []

    def update_current_price(self, price: float, bar_id: int) -> None:
        self.updates.append((price, bar_id))

    def buy(self, quantity: int, price: float, trade_date: str,
            reason: str = "", trade_time: str = "",
            display_period: str = "") -> dict[str, Any]:
        self.trades.append(("buy", quantity, price, trade_date, trade_time,
                            display_period, reason))
        return {"success": True, "message": "ok"}

    def sell(self, quantity: int, price: float, trade_date: str,
             reason: str = "", trade_time: str = "",
             display_period: str = "") -> dict[str, Any]:
        self.trades.append(("sell", quantity, price, trade_date, trade_time,
                            display_period, reason))
        return {"success": True, "message": "ok"}


class FakeOrderManager:
    """Minimal order manager spy compatible with IntradayTradingCallbacks."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def process_bar(self, bar: dict, prev_close: float | None,
                    stock_code: str, trade_date: str,
                    execute_buy, execute_sell) -> list[dict[str, Any]]:
        self.calls.append((bar["datetime"], prev_close, stock_code, trade_date))
        result = execute_buy(1, float(bar["close"]), {"reason": "test"})
        return [{"time": bar["datetime"], "success": result["success"]}]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session(
    frame: pd.DataFrame | None = None,
    initial_time: datetime | None = None,
    initial_period: str = "30m",
) -> tuple[Any, FakeSimulator, FakeOrderManager]:
    """Build a session with fake collaborators for testing."""
    from backend.intraday.session import IntradayReplaySession

    if frame is None:
        frame = _four_day_frame()
    if initial_time is None:
        initial_time = _timeline(frame)[8]  # 2025-01-03 10:00
    sim = FakeSimulator()
    om = FakeOrderManager()
    session = IntradayReplaySession(
        base_bars=frame,
        initial_time=initial_time,
        stock_code=STOCK_CODE,
        simulator=sim,
        order_manager=om,
        initial_period=initial_period,
    )
    return session, sim, om


# ---------------------------------------------------------------------------
# Initial snapshot tests
# ---------------------------------------------------------------------------


class InitialSnapshotTests(unittest.TestCase):
    """Construction and initial snapshot() correctness."""

    def test_initial_snapshot_contains_all_required_fields(self):
        session, _, _ = _make_session(initial_period="daily")
        snap = session.snapshot()

        required = {
            "current_time", "active_period", "base_interval",
            "available_periods", "current_bar_complete", "next_boundary",
            "kline_data", "current_base_bar", "finished",
        }
        self.assertEqual(set(snap.keys()), required)

    def test_initial_snapshot_current_time_matches_initial(self):
        frame = _four_day_frame()
        tl = _timeline(frame)
        session, _, _ = _make_session(
            frame=frame, initial_time=tl[8], initial_period="30m",
        )
        snap = session.snapshot()
        self.assertEqual(snap["current_time"], "2025-01-03 10:00:00")

    def test_initial_snapshot_active_period(self):
        session, _, _ = _make_session(initial_period="daily")
        snap = session.snapshot()
        self.assertEqual(snap["active_period"], "daily")

    def test_base_interval_is_30m(self):
        session, _, _ = _make_session()
        snap = session.snapshot()
        self.assertEqual(snap["base_interval"], "30m")

    def test_available_periods_has_stable_order(self):
        session, _, _ = _make_session()
        snap = session.snapshot()
        self.assertEqual(
            snap["available_periods"],
            ["30m", "4h_session", "daily", "weekly"],
        )

    def test_kline_data_is_json_serializable(self):
        session, _, _ = _make_session(initial_period="daily")
        snap = session.snapshot()
        # Must not raise.
        json.dumps(snap["kline_data"])

    def test_current_base_bar_has_ohlcv(self):
        frame = _four_day_frame()
        tl = _timeline(frame)
        session, _, _ = _make_session(
            frame=frame, initial_time=tl[8], initial_period="30m",
        )
        snap = session.snapshot()
        bar = snap["current_base_bar"]
        self.assertIsNotNone(bar)
        self.assertEqual(bar["datetime"], "2025-01-03 10:00:00")
        self.assertAlmostEqual(bar["open"], 11.0)
        self.assertAlmostEqual(bar["high"], 11.2)
        self.assertAlmostEqual(bar["low"], 10.8)
        self.assertAlmostEqual(bar["close"], 11.1)
        self.assertEqual(bar["volume"], 1000)
        self.assertAlmostEqual(bar["amount"], 10000.0)

    def test_snapshot_does_not_advance_time(self):
        session, _, _ = _make_session(initial_period="30m")
        snap1 = session.snapshot()
        snap2 = session.snapshot()
        self.assertEqual(snap1["current_time"], snap2["current_time"])

    def test_next_boundary_for_30m(self):
        frame = _four_day_frame()
        tl = _timeline(frame)
        session, _, _ = _make_session(
            frame=frame, initial_time=tl[8], initial_period="30m",
        )
        snap = session.snapshot()
        self.assertEqual(snap["next_boundary"], "2025-01-03 10:30:00")
        self.assertFalse(snap["finished"])


# ---------------------------------------------------------------------------
# Period switching tests
# ---------------------------------------------------------------------------


class PeriodSwitchingTests(unittest.TestCase):
    """set_period switches period without side effects."""

    def test_switch_to_each_of_four_periods(self):
        session, _, _ = _make_session(initial_period="30m")
        for period in ("30m", "4h_session", "daily", "weekly"):
            snap = session.set_period(period)
            self.assertEqual(snap["active_period"], period)

    def test_switching_period_does_not_change_current_time(self):
        session, _, _ = _make_session(initial_period="30m")
        snap_before = session.snapshot()
        original_time = snap_before["current_time"]

        for period in ("4h_session", "daily", "weekly", "30m"):
            snap = session.set_period(period)
            self.assertEqual(snap["current_time"], original_time)

    def test_switching_period_does_not_change_account_or_orders(self):
        session, sim, om = _make_session(initial_period="30m")
        # Advance once to create some state.
        session.advance()
        sim_updates_before = len(sim.updates)
        om_calls_before = len(om.calls)

        session.set_period("daily")
        session.set_period("weekly")
        session.set_period("30m")

        # State should be unchanged.
        self.assertEqual(len(sim.updates), sim_updates_before)
        self.assertEqual(len(om.calls), om_calls_before)

    def test_invalid_period_raises_error(self):
        session, _, _ = _make_session()
        with self.assertRaises(ValueError):
            session.set_period("1h")

    def test_set_period_returns_snapshot(self):
        session, _, _ = _make_session()
        snap = session.set_period("daily")
        self.assertIn("current_time", snap)
        self.assertIn("kline_data", snap)


# ---------------------------------------------------------------------------
# Advance tests
# ---------------------------------------------------------------------------


class AdvanceTests(unittest.TestCase):
    """advance() processes hidden bars and returns events."""

    def test_advance_30m_one_bar(self):
        frame = _four_day_frame()
        tl = _timeline(frame)
        session, sim, om = _make_session(
            frame=frame, initial_time=tl[8], initial_period="30m",
        )
        snap = session.advance()

        self.assertEqual(snap["current_time"], "2025-01-03 10:30:00")
        self.assertEqual(snap["completed_times"], ["2025-01-03 10:30:00"])
        self.assertEqual(len(snap["order_events"]), 1)
        self.assertEqual(len(sim.updates), 1)
        self.assertEqual(len(om.calls), 1)

    def test_advance_daily_from_intraday_to_close(self):
        frame = _four_day_frame()
        tl = _timeline(frame)
        # Start at 2025-01-03 10:30 (index 9), daily period.
        session, sim, om = _make_session(
            frame=frame, initial_time=tl[9], initial_period="daily",
        )
        snap = session.advance()

        # Should advance to 2025-01-03 15:00 (session end).
        self.assertEqual(snap["current_time"], "2025-01-03 15:00:00")

        # Should have processed 6 hidden bars: 11:00 through 15:00.
        expected_times = [
            "2025-01-03 11:00:00",
            "2025-01-03 11:30:00",
            "2025-01-03 13:30:00",
            "2025-01-03 14:00:00",
            "2025-01-03 14:30:00",
            "2025-01-03 15:00:00",
        ]
        self.assertEqual(snap["completed_times"], expected_times)
        self.assertEqual(len(sim.updates), 6)
        self.assertEqual(len(om.calls), 6)

    def test_advance_weekly_to_last_bar_of_trading_week(self):
        frame = _four_day_frame()
        tl = _timeline(frame)
        # Start at 2025-01-02 10:00 (Thursday, index 0), weekly period.
        # Week 1: 2025-01-02 (Thu) + 2025-01-03 (Fri).
        # Week end = 2025-01-03 15:00 (index 15).
        session, _, _ = _make_session(
            frame=frame, initial_time=tl[0], initial_period="weekly",
        )
        snap = session.snapshot()
        self.assertEqual(snap["next_boundary"], "2025-01-03 15:00:00")

        snap = session.advance()
        self.assertEqual(snap["current_time"], "2025-01-03 15:00:00")
        # All 15 bars after index 0: indices 1-15.
        self.assertEqual(len(snap["completed_times"]), 15)

    def test_advance_returns_all_underlying_completed_times(self):
        frame = _four_day_frame()
        tl = _timeline(frame)
        # Start at 2025-01-02 10:00 (index 0), daily period.
        session, _, _ = _make_session(
            frame=frame, initial_time=tl[0], initial_period="daily",
        )
        snap = session.advance()

        # Daily advance from 10:00 to 15:00 processes 7 hidden bars.
        expected = [
            "2025-01-02 10:30:00",
            "2025-01-02 11:00:00",
            "2025-01-02 11:30:00",
            "2025-01-02 13:30:00",
            "2025-01-02 14:00:00",
            "2025-01-02 14:30:00",
            "2025-01-02 15:00:00",
        ]
        self.assertEqual(snap["completed_times"], expected)

    def test_advance_preserves_event_order(self):
        frame = _four_day_frame()
        tl = _timeline(frame)
        session, _, om = _make_session(
            frame=frame, initial_time=tl[0], initial_period="daily",
        )
        snap = session.advance()

        # Each hidden bar produces exactly one event from FakeOrderManager.
        events = snap["order_events"]
        self.assertEqual(len(events), 7)
        # Events should be in the same order as completed_times.
        for i, event in enumerate(events):
            expected_time = tl[i + 1]  # indices 1 through 7
            self.assertEqual(
                event["time"], expected_time.strftime("%Y-%m-%d %H:%M:%S")
            )

    def test_advance_finished_plan_returns_finished_state(self):
        frame = _four_day_frame()
        tl = _timeline(frame)
        # Start at the very last bar, weekly period.
        session, _, _ = _make_session(
            frame=frame, initial_time=tl[-1], initial_period="weekly",
        )
        snap = session.snapshot()
        self.assertTrue(snap["finished"])
        self.assertIsNone(snap["next_boundary"])

        # Advancing a finished plan should not loop or crash.
        result = session.advance()
        self.assertTrue(result["finished"])
        self.assertEqual(result["completed_times"], [])
        self.assertEqual(result["order_events"], [])

    def test_advance_does_not_deadlock_on_finished(self):
        frame = _four_day_frame()
        tl = _timeline(frame)
        session, _, _ = _make_session(
            frame=frame, initial_time=tl[-1], initial_period="weekly",
        )
        # Call advance multiple times on a finished session.
        for _ in range(3):
            result = session.advance()
            self.assertTrue(result["finished"])

    def test_advance_uses_display_period_from_active_period(self):
        frame = _four_day_frame()
        tl = _timeline(frame)
        session, sim, _ = _make_session(
            frame=frame, initial_time=tl[0], initial_period="daily",
        )
        session.advance()
        # All trades should carry display_period="daily".
        for trade in sim.trades:
            self.assertEqual(trade[5], "daily")


# ---------------------------------------------------------------------------
# Future leakage tests
# ---------------------------------------------------------------------------


class FutureLeakageTests(unittest.TestCase):
    """snapshot() must not reveal any OHLCV data after current_time."""

    def test_snapshot_does_not_read_future_ohlcv_daily(self):
        frame = _four_day_frame()
        tl = _timeline(frame)
        # Start at 2025-01-02 10:30 (index 1), daily period.
        session, _, _ = _make_session(
            frame=frame, initial_time=tl[1], initial_period="daily",
        )
        snap = session.snapshot()

        # Only one daily bar (2025-01-02) should be visible.
        self.assertEqual(len(snap["kline_data"]), 1)
        daily_bar = snap["kline_data"][0]

        # The daily bar's close must be the 10:30 bar's close (10.1),
        # not any future bar's close. Day 1 price=10.0, close=10.1.
        self.assertAlmostEqual(daily_bar["close"], 10.1)

        # High must be max of bars 10:00 and 10:30 only (10.2).
        self.assertAlmostEqual(daily_bar["high"], 10.2)

        # Low must be min of bars 10:00 and 10:30 only (9.8).
        self.assertAlmostEqual(daily_bar["low"], 9.8)

        # Volume must be sum of bars 10:00 and 10:30 only.
        self.assertEqual(daily_bar["volume"], 2000)

        # Must not be complete (we're only at 10:30, not 15:00).
        self.assertFalse(daily_bar["complete"])

    def test_snapshot_does_not_read_future_when_switching_periods(self):
        frame = _four_day_frame()
        tl = _timeline(frame)
        # Start at 2025-01-02 10:30 (index 1).
        session, _, _ = _make_session(
            frame=frame, initial_time=tl[1], initial_period="30m",
        )
        snap_30m = session.snapshot()
        snap_daily = session.set_period("daily")
        snap_weekly = session.set_period("weekly")

        # 30m: only 2 bars visible (10:00, 10:30).
        self.assertEqual(len(snap_30m["kline_data"]), 2)

        # Daily: only 1 bar (2025-01-02), close = 10:30 bar close (10.1).
        self.assertEqual(len(snap_daily["kline_data"]), 1)
        self.assertAlmostEqual(snap_daily["kline_data"][0]["close"], 10.1)

        # Weekly: only 1 bar, close = 10:30 bar close (10.1).
        self.assertEqual(len(snap_weekly["kline_data"]), 1)
        self.assertAlmostEqual(snap_weekly["kline_data"][0]["close"], 10.1)

    def test_kline_data_only_contains_bars_up_to_current_time(self):
        frame = _four_day_frame()
        tl = _timeline(frame)
        # Start at 2025-01-03 11:00 (index 10), 30m period.
        session, _, _ = _make_session(
            frame=frame, initial_time=tl[10], initial_period="30m",
        )
        snap = session.snapshot()

        # Should have bars from 2025-01-02 10:00 through 2025-01-03 11:00.
        # That's 8 (day 1) + 3 (day 2: 10:00, 10:30, 11:00) = 11 bars.
        self.assertEqual(len(snap["kline_data"]), 11)

        last_bar = snap["kline_data"][-1]
        self.assertEqual(last_bar["end_time"], "2025-01-03 11:00:00")

        # No bar after 11:00 should be present.
        for bar in snap["kline_data"]:
            self.assertLessEqual(bar["end_time"], "2025-01-03 11:00:00")


# ---------------------------------------------------------------------------
# Completion state tests
# ---------------------------------------------------------------------------


class CompletionStateTests(unittest.TestCase):
    """current_bar_complete reflects partial vs. finished aggregation."""

    def test_incomplete_daily_bar_complete_false(self):
        frame = _four_day_frame()
        tl = _timeline(frame)
        # Start at 2025-01-02 10:30 (mid-day), daily period.
        session, _, _ = _make_session(
            frame=frame, initial_time=tl[1], initial_period="daily",
        )
        snap = session.snapshot()
        self.assertFalse(snap["current_bar_complete"])

    def test_completed_daily_bar_complete_true(self):
        frame = _four_day_frame()
        tl = _timeline(frame)
        # Start at 2025-01-02 15:00 (session end), daily period.
        session, _, _ = _make_session(
            frame=frame, initial_time=tl[7], initial_period="daily",
        )
        snap = session.snapshot()
        self.assertTrue(snap["current_bar_complete"])

    def test_30m_bar_always_complete(self):
        frame = _four_day_frame()
        tl = _timeline(frame)
        session, _, _ = _make_session(
            frame=frame, initial_time=tl[1], initial_period="30m",
        )
        snap = session.snapshot()
        self.assertTrue(snap["current_bar_complete"])

    def test_incomplete_weekly_bar_complete_false(self):
        frame = _four_day_frame()
        tl = _timeline(frame)
        # Start at 2025-01-02 15:00 (Thursday close), weekly period.
        # Week 1 includes 01-02 and 01-03, so 01-02 15:00 is NOT the week end.
        session, _, _ = _make_session(
            frame=frame, initial_time=tl[7], initial_period="weekly",
        )
        snap = session.snapshot()
        self.assertFalse(snap["current_bar_complete"])

    def test_completed_weekly_bar_complete_true(self):
        frame = _four_day_frame()
        tl = _timeline(frame)
        # Start at 2025-01-03 15:00 (Friday close = week 1 end), weekly period.
        session, _, _ = _make_session(
            frame=frame, initial_time=tl[15], initial_period="weekly",
        )
        snap = session.snapshot()
        self.assertTrue(snap["current_bar_complete"])


# ---------------------------------------------------------------------------
# Finished state tests
# ---------------------------------------------------------------------------


class FinishedStateTests(unittest.TestCase):
    """finished is True when there is no next boundary."""

    def test_finished_when_at_last_bar_30m(self):
        frame = _four_day_frame()
        tl = _timeline(frame)
        session, _, _ = _make_session(
            frame=frame, initial_time=tl[-1], initial_period="30m",
        )
        snap = session.snapshot()
        self.assertTrue(snap["finished"])
        self.assertIsNone(snap["next_boundary"])

    def test_finished_when_at_last_bar_weekly(self):
        frame = _four_day_frame()
        tl = _timeline(frame)
        session, _, _ = _make_session(
            frame=frame, initial_time=tl[-1], initial_period="weekly",
        )
        snap = session.snapshot()
        self.assertTrue(snap["finished"])
        self.assertIsNone(snap["next_boundary"])

    def test_not_finished_when_more_bars_exist(self):
        frame = _four_day_frame()
        tl = _timeline(frame)
        session, _, _ = _make_session(
            frame=frame, initial_time=tl[0], initial_period="30m",
        )
        snap = session.snapshot()
        self.assertFalse(snap["finished"])
        self.assertIsNotNone(snap["next_boundary"])


# ---------------------------------------------------------------------------
# Reset tests
# ---------------------------------------------------------------------------


class ResetTests(unittest.TestCase):
    """reset() restores initial time and period without replacing collaborators."""

    def test_reset_restores_initial_time_and_period(self):
        frame = _four_day_frame()
        tl = _timeline(frame)
        session, _, _ = _make_session(
            frame=frame, initial_time=tl[8], initial_period="30m",
        )
        # Change state.
        session.set_period("daily")
        session.advance()
        # Reset.
        snap = session.reset()

        self.assertEqual(snap["current_time"], "2025-01-03 10:00:00")
        self.assertEqual(snap["active_period"], "30m")

    def test_reset_does_not_replace_simulator(self):
        frame = _four_day_frame()
        tl = _timeline(frame)
        session, sim, _ = _make_session(
            frame=frame, initial_time=tl[8], initial_period="30m",
        )
        # Advance to create simulator state.
        session.advance()
        updates_before = len(sim.updates)

        session.reset()

        # Same simulator object, state preserved.
        self.assertIs(session._simulator, sim)
        self.assertEqual(len(sim.updates), updates_before)

    def test_reset_does_not_replace_order_manager(self):
        frame = _four_day_frame()
        tl = _timeline(frame)
        session, _, om = _make_session(
            frame=frame, initial_time=tl[8], initial_period="30m",
        )
        session.advance()
        calls_before = len(om.calls)

        session.reset()

        self.assertIs(session._order_manager, om)
        self.assertEqual(len(om.calls), calls_before)

    def test_reset_does_not_clear_trade_history(self):
        frame = _four_day_frame()
        tl = _timeline(frame)
        session, sim, _ = _make_session(
            frame=frame, initial_time=tl[8], initial_period="30m",
        )
        session.advance()
        trades_before = len(sim.trades)

        session.reset()

        # Trades should still be there.
        self.assertEqual(len(sim.trades), trades_before)

    def test_reset_returns_snapshot(self):
        session, _, _ = _make_session()
        snap = session.reset()
        self.assertIn("current_time", snap)
        self.assertIn("kline_data", snap)


# ---------------------------------------------------------------------------
# Error handling tests
# ---------------------------------------------------------------------------


class ErrorHandlingTests(unittest.TestCase):
    """Construction and period validation errors."""

    def test_nonexistent_initial_time_raises_error(self):
        from backend.intraday.session import IntradayReplaySession

        frame = _four_day_frame()
        bad_time = datetime(2025, 1, 1, 9, 30, 0)  # Not in timeline
        with self.assertRaises(ValueError):
            IntradayReplaySession(
                base_bars=frame,
                initial_time=bad_time,
                stock_code=STOCK_CODE,
                simulator=FakeSimulator(),
                order_manager=FakeOrderManager(),
                initial_period="30m",
            )

    def test_invalid_initial_period_raises_error(self):
        from backend.intraday.session import IntradayReplaySession

        frame = _four_day_frame()
        tl = _timeline(frame)
        with self.assertRaises(ValueError):
            IntradayReplaySession(
                base_bars=frame,
                initial_time=tl[0],
                stock_code=STOCK_CODE,
                simulator=FakeSimulator(),
                order_manager=FakeOrderManager(),
                initial_period="1h",
            )

    def test_invalid_set_period_raises_error(self):
        session, _, _ = _make_session()
        with self.assertRaises(ValueError):
            session.set_period("invalid_period")


# ---------------------------------------------------------------------------
# JSON serialization tests
# ---------------------------------------------------------------------------


class JsonSerializationTests(unittest.TestCase):
    """Entire snapshot must be JSON-serializable."""

    def test_snapshot_is_json_serializable(self):
        session, _, _ = _make_session(initial_period="daily")
        snap = session.snapshot()
        json.dumps(snap)

    def test_advance_result_is_json_serializable(self):
        frame = _four_day_frame()
        tl = _timeline(frame)
        session, _, _ = _make_session(
            frame=frame, initial_time=tl[0], initial_period="daily",
        )
        result = session.advance()
        json.dumps(result)

    def test_kline_data_has_no_pandas_or_numpy_types(self):
        import numpy as np

        frame = _four_day_frame()
        tl = _timeline(frame)
        session, _, _ = _make_session(
            frame=frame, initial_time=tl[10], initial_period="daily",
        )
        snap = session.snapshot()

        for bar in snap["kline_data"]:
            for key, value in bar.items():
                self.assertNotIsInstance(
                    value, (pd.Timestamp, np.generic, pd.Timestamp),
                    f"field '{key}' has non-serializable type {type(value)}",
                )

    def test_current_base_bar_is_json_serializable(self):
        session, _, _ = _make_session()
        snap = session.snapshot()
        if snap["current_base_bar"] is not None:
            json.dumps(snap["current_base_bar"])


# ---------------------------------------------------------------------------
# Previous close integration tests
# ---------------------------------------------------------------------------


class PreviousCloseIntegrationTests(unittest.TestCase):
    """advance() uses PreviousCloseIndex for prev_close, not last 30m close."""

    def test_advance_passes_previous_trading_day_close(self):
        frame = _four_day_frame()
        tl = _timeline(frame)
        # Start at 2025-01-03 10:00 (day 2), daily period.
        session, _, om = _make_session(
            frame=frame, initial_time=tl[8], initial_period="daily",
        )
        session.advance()

        # All calls should have prev_close = day 1's last close (10.1).
        for call in om.calls:
            prev_close = call[1]
            self.assertAlmostEqual(prev_close, 10.1)

    def test_first_trading_day_passes_none_previous_close(self):
        frame = _four_day_frame()
        tl = _timeline(frame)
        # Start at 2025-01-02 10:00 (day 1, first trading day), 30m period.
        session, _, om = _make_session(
            frame=frame, initial_time=tl[0], initial_period="30m",
        )
        session.advance()

        # First trading day has no previous close.
        self.assertIsNone(om.calls[0][1])


# ---------------------------------------------------------------------------
# Multi-advance sequence tests
# ---------------------------------------------------------------------------


class MultiAdvanceSequenceTests(unittest.TestCase):
    """Multiple sequential advances work correctly."""

    def test_repeated_30m_advances_reach_daily_close(self):
        frame = _four_day_frame()
        tl = _timeline(frame)
        # Start at 2025-01-03 10:00 (index 8), 30m period.
        session, sim, om = _make_session(
            frame=frame, initial_time=tl[8], initial_period="30m",
        )

        all_completed = []
        all_events = []
        for _ in range(7):
            result = session.advance()
            all_completed.extend(result["completed_times"])
            all_events.extend(result["order_events"])

        self.assertEqual(session.snapshot()["current_time"], "2025-01-03 15:00:00")
        self.assertEqual(len(all_completed), 7)
        self.assertEqual(len(all_events), 7)
        self.assertEqual(len(sim.updates), 7)
        self.assertEqual(len(om.calls), 7)

    def test_daily_then_weekly_advance(self):
        frame = _four_day_frame()
        tl = _timeline(frame)
        # Start at 2025-01-02 10:00 (Thursday, index 0).
        session, _, _ = _make_session(
            frame=frame, initial_time=tl[0], initial_period="daily",
        )

        # Daily advance: 2025-01-02 10:00 -> 2025-01-02 15:00.
        snap1 = session.advance()
        self.assertEqual(snap1["current_time"], "2025-01-02 15:00:00")

        # Switch to weekly and advance: 2025-01-02 15:00 -> 2025-01-03 15:00.
        snap2 = session.set_period("weekly")
        self.assertEqual(snap2["current_time"], "2025-01-02 15:00:00")

        snap3 = session.advance()
        self.assertEqual(snap3["current_time"], "2025-01-03 15:00:00")
        # 8 hidden bars (all of 2025-01-03).
        self.assertEqual(len(snap3["completed_times"]), 8)


if __name__ == "__main__":
    unittest.main()
