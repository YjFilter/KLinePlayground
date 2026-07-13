"""TASK-009: Intraday trading large-step vs repeated 30m equivalence tests.

Independent black-box verification that daily large-step advancement is
behaviorally equivalent to repeated 30-minute advancement, using real
production components (ReplayClock, execute_trading_advance,
PreviousCloseIndex/build_previous_close_index, PendingOrderManager,
TradeSimulatorEnhanced).

Verified properties:
1. Large-step (daily) and repeated 30m advancement produce equal ordered
   events, trade history, capital, shares, position lots, and current price.
2. Hidden base bars are processed one-by-one; an order triggered on an
   intermediate bar records that bar's timestamp, not the target close time.
3. All bars within one trading day use the previous trading day's final close
   for limit checks (not the previous 30-minute bar's close).
4. T+1 is enforced by trade_date: same-day sells are blocked; the next
   trading day's first eligible bar can sell.
5. Trade records carry trade_date (YYYY-MM-DD), trade_time (full datetime),
   and the selected display_period; same-day different-time trades remain
   independent.

All TradeSimulatorEnhanced instances use temporary databases. No real user
data is read or written. Only this test file is created/modified.
"""

import os
import shutil
import sys
import tempfile
import unittest
from datetime import date
from unittest.mock import patch

import pandas as pd

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.intraday.replay_clock import ReplayClock
from backend.intraday.trading_context import build_previous_close_index
from backend.intraday.trading_engine import execute_trading_advance
from backend.order_manager import PendingOrderManager
from backend.trade_simulator_enhanced import TradeSimulatorEnhanced


# ---------------------------------------------------------------------------
# Deterministic offline 30-minute bar data
# ---------------------------------------------------------------------------

TIMES = ("10:00", "10:30", "11:00", "11:30", "13:30", "14:00", "14:30", "15:00")
STOCK_CODE = "600000"
INITIAL_CAPITAL = 100_000.0


def _bar(day, time_value, o, h, l, c, vol=1000, amt=10000):
    return {
        "datetime": pd.Timestamp(f"{day} {time_value}:00"),
        "open": o,
        "high": h,
        "low": l,
        "close": c,
        "volume": vol,
        "amount": amt,
    }


def _flat_day(day, price=10.0):
    """Eight bars at *price*; last close == price."""
    return [_bar(day, t, price, price + 0.05, price - 0.05, price) for t in TIMES]


def _frame(*rows):
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Simulator with temporary database
# ---------------------------------------------------------------------------

def _make_simulator(temp_dir, initial_capital=INITIAL_CAPITAL, stock_code=STOCK_CODE):
    """Create a TradeSimulatorEnhanced backed by a temp database file.

    The default constructor writes to ``../users/{user}/trade_records.db``
    which would pollute real user data. We patch ``_init_database`` to a
    no-op during ``__init__``, then point ``db_path`` at a temp file and run
    the real migration. This mirrors the accepted TASK-008 test pattern.
    """
    db_path = os.path.join(temp_dir, "trade_records.db")
    with patch.object(TradeSimulatorEnhanced, "_init_database", lambda self: None):
        sim = TradeSimulatorEnhanced("task009_user", initial_capital, stock_code)
    sim.db_path = db_path
    sim._init_database()
    return sim


# ---------------------------------------------------------------------------
# Comparison helpers
# ---------------------------------------------------------------------------

def _trade_core_key(trade):
    """Core trade fields for cross-scenario comparison.

    display_period is intentionally excluded: daily and 30m scenarios may
    legitimately differ on that field while all trading-semantic fields
    must match.
    """
    return (
        trade["action"],
        trade["quantity"],
        round(float(trade["price"]), 4),
        trade["trade_date"],
        trade.get("trade_time", ""),
    )


def _lot_key(lot):
    return (
        lot["stock_code"],
        lot["quantity"],
        round(float(lot["cost_price"]), 4),
        lot["buy_date"],
        lot["buy_bar_id"],
        lot["available_date"],
        lot["status"],
    )


def _event_key(event):
    """Event fields that must match across scenarios."""
    return (
        event["order_id"],
        event["side"],
        event["order_type"],
        event["quantity"],
        event["price"],
        event["status"],
        event["date"],
    )


# ---------------------------------------------------------------------------
# Equivalence: daily large-step vs repeated 30m
# ---------------------------------------------------------------------------

class LargeStepEquivalenceTests(unittest.TestCase):
    """Daily one-step advancement must equal eight 30m advancements."""

    def setUp(self):
        self.temp_dir_daily = tempfile.mkdtemp(prefix="task009_eq_daily_")
        self.temp_dir_30m = tempfile.mkdtemp(prefix="task009_eq_30m_")

    def tearDown(self):
        shutil.rmtree(self.temp_dir_daily, ignore_errors=True)
        shutil.rmtree(self.temp_dir_30m, ignore_errors=True)

    def _build_scenario(self, temp_dir, display_period):
        """Build a fresh, identical scenario for the given display period.

        Day 1 (2025-01-02): flat at 10.00, last close = 10.00 (prev_close for day 2).
        Day 2 (2025-01-03): rising bars from 10.15 to 10.90.

        Pre-fill: buy 2 lots @ 10.00 on day 1 (available 2025-01-03).
        Pending orders:
        - take_profit exit @ 10.50 (for the pre-fill position; fills at 11:30).
        - breakout buy @ 10.20 with take_profit @ 10.60 and stop_loss @ 9.50
          (fills at 10:00; its take_profit triggers from 13:30 onward but
          is T+1-blocked on day 2).
        """
        day1 = _flat_day("2025-01-02", price=10.0)
        day2 = [
            _bar("2025-01-03", "10:00", 10.10, 10.20, 10.05, 10.15),
            _bar("2025-01-03", "10:30", 10.15, 10.30, 10.10, 10.25),
            _bar("2025-01-03", "11:00", 10.25, 10.40, 10.20, 10.35),
            _bar("2025-01-03", "11:30", 10.35, 10.55, 10.30, 10.50),
            _bar("2025-01-03", "13:30", 10.50, 10.65, 10.45, 10.60),
            _bar("2025-01-03", "14:00", 10.60, 10.75, 10.55, 10.70),
            _bar("2025-01-03", "14:30", 10.70, 10.85, 10.65, 10.80),
            _bar("2025-01-03", "15:00", 10.80, 10.95, 10.75, 10.90),
        ]
        frame = _frame(*(day1 + day2))
        timeline = tuple(frame["datetime"].dt.to_pydatetime())
        prev_closes = build_previous_close_index(frame)

        sim = _make_simulator(temp_dir)
        sim.update_current_price(10.0, bar_id=8)
        sim.buy(
            quantity=2, price=10.0, trade_date="2025-01-02",
            reason="prefill", trade_time="2025-01-02 15:00:00",
            display_period="30m",
        )

        om = PendingOrderManager()
        om.add_exit_order("take_profit", quantity=2, trigger_price=10.50,
                          reason="prefill tp")
        om.add_buy_order("breakout", quantity=1, trigger_price=10.20,
                         take_profit_price=10.60, stop_loss_price=9.50,
                         reason="breakout")

        clock = ReplayClock(timeline, initial_time=timeline[7],
                            active_period=display_period)
        return frame, timeline, prev_closes, sim, om, clock

    def test_daily_large_step_equals_repeated_30m(self):
        # --- Scenario A: one daily advance to day-2 close ---
        frame_a, timeline_a, prev_a, sim_a, om_a, clock_a = self._build_scenario(
            self.temp_dir_daily, "daily")
        plan_a = clock_a.plan_next()
        self.assertEqual(len(plan_a.base_bar_times), 8)
        result_a = execute_trading_advance(
            plan=plan_a, clock=clock_a, base_bars=frame_a,
            previous_closes=prev_a, simulator=sim_a, order_manager=om_a,
            stock_code=STOCK_CODE, display_period="daily",
        )
        self.assertTrue(result_a.success, result_a.error)
        events_a = list(result_a.events)
        completed_a = list(result_a.completed_times)

        # --- Scenario B: eight 30m advances to the same day-2 close ---
        frame_b, timeline_b, prev_b, sim_b, om_b, clock_b = self._build_scenario(
            self.temp_dir_30m, "30m")
        events_b = []
        completed_b = []
        advance_count = 0
        while clock_b.has_next():
            plan = clock_b.plan_next()
            self.assertEqual(len(plan.base_bar_times), 1)
            r = execute_trading_advance(
                plan=plan, clock=clock_b, base_bars=frame_b,
                previous_closes=prev_b, simulator=sim_b, order_manager=om_b,
                stock_code=STOCK_CODE, display_period="30m",
            )
            self.assertTrue(r.success, r.error)
            events_b.extend(r.events)
            completed_b.extend(r.completed_times)
            advance_count += 1
        self.assertEqual(advance_count, 8)

        # --- Compare clock final position ---
        self.assertEqual(clock_a.current_time, timeline_a[15])
        self.assertEqual(clock_b.current_time, timeline_b[15])
        self.assertEqual(clock_a.current_time, clock_b.current_time)

        # --- Compare completed base-bar times ---
        self.assertEqual(completed_a, completed_b)
        self.assertEqual(completed_a, list(timeline_a[8:16]))

        # --- Compare ordered events ---
        self.assertEqual(len(events_a), len(events_b))
        for idx, (ea, eb) in enumerate(zip(events_a, events_b)):
            self.assertEqual(_event_key(ea), _event_key(eb),
                             f"event #{idx} mismatch:\n  A={ea}\n  B={eb}")

        # --- Compare trade history (core fields, excluding display_period) ---
        hist_a = sim_a.get_trade_history_with_bar_id()
        hist_b = sim_b.get_trade_history_with_bar_id()
        self.assertEqual(len(hist_a), len(hist_b))
        for idx, (ta, tb) in enumerate(zip(hist_a, hist_b)):
            self.assertEqual(_trade_core_key(ta), _trade_core_key(tb),
                             f"trade #{idx} mismatch:\n  A={ta}\n  B={tb}")

        # --- Compare account state ---
        self.assertAlmostEqual(sim_a.current_capital, sim_b.current_capital,
                               places=2)
        self.assertEqual(sim_a.total_shares, sim_b.total_shares)
        self.assertEqual(sim_a.average_cost, sim_b.average_cost)
        self.assertEqual(sim_a.current_price, sim_b.current_price)
        self.assertEqual(sim_a.available_shares, sim_b.available_shares)

        # --- Compare available_shares via public account API ---
        acct_a = sim_a.get_account_info("2025-01-03")
        acct_b = sim_b.get_account_info("2025-01-03")
        self.assertEqual(
            acct_a["position_summary"]["available_shares"],
            acct_b["position_summary"]["available_shares"],
        )

        # --- Compare position lots ---
        self.assertEqual(len(sim_a.position_lots), len(sim_b.position_lots))
        for la, lb in zip(sim_a.position_lots, sim_b.position_lots):
            self.assertEqual(_lot_key(la), _lot_key(lb))

        # --- Verify display_period differs as expected ---
        self.assertEqual(hist_a[0]["display_period"], "30m")
        self.assertEqual(hist_b[0]["display_period"], "30m")
        for t in hist_a[1:]:
            self.assertEqual(t["display_period"], "daily")
        for t in hist_b[1:]:
            self.assertEqual(t["display_period"], "30m")

    def test_intermediate_bar_fill_time_not_target_close(self):
        """An order triggered on an intermediate hidden bar must record
        that bar's timestamp, not the daily target close time."""
        temp_dir = tempfile.mkdtemp(prefix="task009_hidden_")
        try:
            day1 = _flat_day("2025-01-02", price=10.0)
            day2 = [
                _bar("2025-01-03", "10:00", 10.10, 10.20, 10.05, 10.15),
                _bar("2025-01-03", "10:30", 10.15, 10.30, 10.10, 10.25),
                _bar("2025-01-03", "11:00", 10.25, 10.40, 10.20, 10.35),
                _bar("2025-01-03", "11:30", 10.50, 10.60, 10.45, 10.55),
                _bar("2025-01-03", "13:30", 10.55, 10.65, 10.50, 10.60),
                _bar("2025-01-03", "14:00", 10.60, 10.75, 10.55, 10.70),
                _bar("2025-01-03", "14:30", 10.70, 10.85, 10.65, 10.80),
                _bar("2025-01-03", "15:00", 10.80, 10.95, 10.75, 10.90),
            ]
            frame = _frame(*(day1 + day2))
            timeline = tuple(frame["datetime"].dt.to_pydatetime())
            prev_closes = build_previous_close_index(frame)

            sim = _make_simulator(temp_dir)
            om = PendingOrderManager()
            # Breakout at 10.50: first triggers at 11:30 (high 10.60 >= 10.50).
            om.add_buy_order("breakout", quantity=1, trigger_price=10.50,
                             reason="midday breakout")

            clock = ReplayClock(timeline, initial_time=timeline[7],
                                active_period="daily")
            r = execute_trading_advance(
                plan=clock.plan_next(), clock=clock, base_bars=frame,
                previous_closes=prev_closes, simulator=sim, order_manager=om,
                stock_code=STOCK_CODE, display_period="daily",
            )
            self.assertTrue(r.success, r.error)

            hist = sim.get_trade_history_with_bar_id()
            self.assertEqual(len(hist), 1)
            trade = hist[0]
            self.assertEqual(trade["trade_date"], "2025-01-03")
            self.assertEqual(trade["trade_time"], "2025-01-03 11:30:00")
            self.assertNotEqual(trade["trade_time"], "2025-01-03 15:00:00")
            self.assertEqual(clock.current_time, timeline[15])
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Previous close and limit-up / limit-down
# ---------------------------------------------------------------------------

class PreviousCloseTests(unittest.TestCase):
    """All bars in one day use the previous trading day's final close."""

    def test_index_returns_prior_trading_day_final_close(self):
        day1 = _flat_day("2025-01-02", price=10.0)
        day2 = _flat_day("2025-01-03", price=11.0)
        frame = _frame(*(day1 + day2))

        idx = build_previous_close_index(frame)
        self.assertIsNone(idx.previous_close_for_date(date(2025, 1, 2)))
        self.assertEqual(idx.previous_close_for_date(date(2025, 1, 3)), 10.0)

    def test_limit_up_blocks_buy_using_previous_trading_day_close(self):
        """A buy at limit-up (based on prior day close 10.00 -> 11.00) must be
        blocked. If the engine wrongly used the previous 30m bar close (10.80),
        limit-up would be 11.88 and the buy would fill."""
        temp_dir = tempfile.mkdtemp(prefix="task009_lu_")
        try:
            day1 = _flat_day("2025-01-02", price=10.0)
            day2 = [
                _bar("2025-01-03", "10:00", 10.20, 10.40, 10.15, 10.30),
                _bar("2025-01-03", "10:30", 10.30, 10.80, 10.25, 10.80),
                _bar("2025-01-03", "11:00", 11.00, 11.00, 10.95, 11.00),
                _bar("2025-01-03", "11:30", 11.00, 11.00, 10.95, 11.00),
                _bar("2025-01-03", "13:30", 11.00, 11.00, 10.95, 11.00),
                _bar("2025-01-03", "14:00", 11.00, 11.00, 10.95, 11.00),
                _bar("2025-01-03", "14:30", 11.00, 11.00, 10.95, 11.00),
                _bar("2025-01-03", "15:00", 11.00, 11.00, 10.95, 11.00),
            ]
            frame = _frame(*(day1 + day2))
            timeline = tuple(frame["datetime"].dt.to_pydatetime())
            prev_closes = build_previous_close_index(frame)

            # All day-2 bars resolve to the same previous close (10.00).
            for ts in timeline[8:]:
                self.assertEqual(prev_closes.previous_close(ts), 10.0)

            sim = _make_simulator(temp_dir)
            om = PendingOrderManager()
            om.add_buy_order("breakout", quantity=1, trigger_price=11.00,
                             reason="limit up test")

            clock = ReplayClock(timeline, initial_time=timeline[7],
                                active_period="daily")
            r = execute_trading_advance(
                plan=clock.plan_next(), clock=clock, base_bars=frame,
                previous_closes=prev_closes, simulator=sim, order_manager=om,
                stock_code=STOCK_CODE, display_period="daily",
            )
            self.assertTrue(r.success, r.error)

            blocked = [e for e in r.events if e["status"] == "blocked"]
            self.assertGreater(len(blocked), 0,
                               "expected limit-up to block the buy")
            filled = [e for e in r.events if e["status"] == "filled"]
            self.assertEqual(len(filled), 0,
                             "buy should not fill at limit-up price")
            self.assertEqual(len(sim.get_trade_history_with_bar_id()), 0)
            self.assertEqual(len(om.active_buy_orders), 1)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_limit_down_blocks_sell_using_previous_close(self):
        """A sell at limit-down (based on prior day close 10.00 -> 9.00) must
        be blocked, distinguishing prev_close from prev 30m close."""
        temp_dir = tempfile.mkdtemp(prefix="task009_ld_")
        try:
            day1 = _flat_day("2025-01-02", price=10.0)
            day2 = [
                _bar("2025-01-03", "10:00", 9.00, 9.00, 9.00, 9.00),
                _bar("2025-01-03", "10:30", 9.00, 9.10, 8.95, 9.05),
                _bar("2025-01-03", "11:00", 9.05, 9.15, 9.00, 9.10),
                _bar("2025-01-03", "11:30", 9.10, 9.20, 9.05, 9.15),
                _bar("2025-01-03", "13:30", 9.15, 9.25, 9.10, 9.20),
                _bar("2025-01-03", "14:00", 9.20, 9.30, 9.15, 9.25),
                _bar("2025-01-03", "14:30", 9.25, 9.35, 9.20, 9.30),
                _bar("2025-01-03", "15:00", 9.30, 9.40, 9.25, 9.35),
            ]
            frame = _frame(*(day1 + day2))
            timeline = tuple(frame["datetime"].dt.to_pydatetime())
            prev_closes = build_previous_close_index(frame)

            sim = _make_simulator(temp_dir)
            sim.update_current_price(10.0, bar_id=8)
            sim.buy(quantity=1, price=10.0, trade_date="2025-01-02",
                    reason="prefill", trade_time="2025-01-02 15:00:00",
                    display_period="30m")

            om = PendingOrderManager()
            om.add_exit_order("stop_loss", quantity=1, trigger_price=9.00,
                              reason="stop loss test")

            clock = ReplayClock(timeline, initial_time=timeline[7],
                                active_period="daily")
            r = execute_trading_advance(
                plan=clock.plan_next(), clock=clock, base_bars=frame,
                previous_closes=prev_closes, simulator=sim, order_manager=om,
                stock_code=STOCK_CODE, display_period="daily",
            )
            self.assertTrue(r.success, r.error)

            blocked = [e for e in r.events if e["status"] == "blocked"]
            self.assertGreater(len(blocked), 0,
                               "expected limit-down to block the sell")
            sells = [t for t in sim.get_trade_history_with_bar_id()
                     if t["action"] == "sell"]
            self.assertEqual(len(sells), 0)
            self.assertEqual(sim.total_shares, 100)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# T+1 settlement
# ---------------------------------------------------------------------------

class TPlusOneSettlementTests(unittest.TestCase):
    """T+1 is enforced by trade_date, not trade_time."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="task009_t1_")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_same_day_sell_blocked_next_trading_day_allowed(self):
        """Buy on day 2, take-profit triggers same day but T+1 blocks.
        Next trading day (day 3, after weekend) first eligible bar sells."""
        day1 = _flat_day("2025-01-02", price=10.0)
        day2 = [
            _bar("2025-01-03", "10:00", 10.10, 10.20, 10.05, 10.15),
            _bar("2025-01-03", "10:30", 10.15, 10.30, 10.10, 10.25),
            _bar("2025-01-03", "11:00", 10.25, 10.40, 10.20, 10.35),
            _bar("2025-01-03", "11:30", 10.35, 10.55, 10.30, 10.50),
            _bar("2025-01-03", "13:30", 10.50, 10.65, 10.45, 10.60),
            _bar("2025-01-03", "14:00", 10.60, 10.75, 10.55, 10.70),
            _bar("2025-01-03", "14:30", 10.70, 10.85, 10.65, 10.80),
            _bar("2025-01-03", "15:00", 10.80, 10.95, 10.75, 10.90),
        ]
        day3 = [
            _bar("2025-01-06", "10:00", 10.60, 10.70, 10.55, 10.65),
            _bar("2025-01-06", "10:30", 10.65, 10.75, 10.60, 10.70),
            _bar("2025-01-06", "11:00", 10.70, 10.80, 10.65, 10.75),
            _bar("2025-01-06", "11:30", 10.75, 10.85, 10.70, 10.80),
            _bar("2025-01-06", "13:30", 10.80, 10.90, 10.75, 10.85),
            _bar("2025-01-06", "14:00", 10.85, 10.95, 10.80, 10.90),
            _bar("2025-01-06", "14:30", 10.90, 11.00, 10.85, 10.95),
            _bar("2025-01-06", "15:00", 10.95, 11.05, 10.90, 11.00),
        ]
        frame = _frame(*(day1 + day2 + day3))
        timeline = tuple(frame["datetime"].dt.to_pydatetime())
        prev_closes = build_previous_close_index(frame)

        sim = _make_simulator(self.temp_dir)
        om = PendingOrderManager()
        om.add_buy_order("breakout", quantity=1, trigger_price=10.20,
                         take_profit_price=10.60, stop_loss_price=9.50,
                         reason="t1 test")

        clock = ReplayClock(timeline, initial_time=timeline[7],
                            active_period="daily")

        # --- Advance day 2 (2025-01-03) ---
        r1 = execute_trading_advance(
            plan=clock.plan_next(), clock=clock, base_bars=frame,
            previous_closes=prev_closes, simulator=sim, order_manager=om,
            stock_code=STOCK_CODE, display_period="daily",
        )
        self.assertTrue(r1.success, r1.error)

        hist = sim.get_trade_history_with_bar_id()
        buys = [t for t in hist if t["action"] == "buy"]
        sells = [t for t in hist if t["action"] == "sell"]
        self.assertEqual(len(buys), 1)
        self.assertEqual(buys[0]["trade_date"], "2025-01-03")
        self.assertEqual(buys[0]["trade_time"], "2025-01-03 10:00:00")
        self.assertEqual(len(sells), 0)

        rejected = [e for e in r1.events if e["status"] == "rejected"]
        self.assertGreater(len(rejected), 0,
                           "take-profit should trigger but be T+1 rejected")
        # Every rejection is on 2025-01-03, even at 15:00.
        for e in rejected:
            self.assertEqual(e["date"], "2025-01-03")

        active_lots = [l for l in sim.position_lots if l["status"] == "active"]
        self.assertEqual(len(active_lots), 1)
        self.assertEqual(active_lots[0]["available_date"], "2025-01-04")

        # --- Advance day 3 (2025-01-06, next trading day after weekend) ---
        r2 = execute_trading_advance(
            plan=clock.plan_next(), clock=clock, base_bars=frame,
            previous_closes=prev_closes, simulator=sim, order_manager=om,
            stock_code=STOCK_CODE, display_period="daily",
        )
        self.assertTrue(r2.success, r2.error)

        hist = sim.get_trade_history_with_bar_id()
        sells = [t for t in hist if t["action"] == "sell"]
        self.assertEqual(len(sells), 1)
        self.assertEqual(sells[0]["trade_date"], "2025-01-06")
        self.assertEqual(sells[0]["trade_time"], "2025-01-06 10:00:00")

        filled_sells = [e for e in r2.events
                        if e["status"] == "filled" and e["side"] == "sell"]
        self.assertGreater(len(filled_sells), 0)
        self.assertEqual(sim.total_shares, 0)

    def test_t1_judged_by_date_not_time(self):
        """A sell at 15:00 on the buy date is blocked, while a sell at 10:00
        on the next trading day succeeds - proving T+1 uses trade_date."""
        sim = _make_simulator(self.temp_dir)
        sim.update_current_price(10.0, bar_id=1)
        buy = sim.buy(quantity=1, price=10.0, trade_date="2025-01-03",
                      reason="t1 time test",
                      trade_time="2025-01-03 10:00:00", display_period="30m")
        self.assertTrue(buy["success"])

        sell_same_day = sim.sell(quantity=1, price=10.5, trade_date="2025-01-03",
                                 reason="late exit",
                                 trade_time="2025-01-03 15:00:00",
                                 display_period="30m")
        self.assertFalse(sell_same_day["success"])

        sell_next_day = sim.sell(quantity=1, price=10.5,
                                 trade_date="2025-01-06",
                                 reason="next day exit",
                                 trade_time="2025-01-06 10:00:00",
                                 display_period="30m")
        self.assertTrue(sell_next_day["success"], sell_next_day.get("message"))


# ---------------------------------------------------------------------------
# Trade metadata
# ---------------------------------------------------------------------------

class TradeMetadataTests(unittest.TestCase):
    """Trade records carry trade_date, trade_time, display_period."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="task009_meta_")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_metadata_format_and_same_day_independence(self):
        """Two buys on the same day at different times stay as separate
        records with correct trade_date, trade_time, and display_period."""
        day1 = _flat_day("2025-01-02", price=10.0)
        day2 = [
            _bar("2025-01-03", "10:00", 10.10, 10.20, 10.05, 10.15),
            _bar("2025-01-03", "10:30", 10.15, 10.30, 10.10, 10.25),
            _bar("2025-01-03", "11:00", 10.25, 10.40, 10.20, 10.35),
            _bar("2025-01-03", "11:30", 10.35, 10.55, 10.30, 10.50),
            _bar("2025-01-03", "13:30", 10.50, 10.65, 10.45, 10.60),
            _bar("2025-01-03", "14:00", 10.60, 10.75, 10.55, 10.70),
            _bar("2025-01-03", "14:30", 10.70, 10.85, 10.65, 10.80),
            _bar("2025-01-03", "15:00", 10.80, 10.95, 10.75, 10.90),
        ]
        frame = _frame(*(day1 + day2))
        timeline = tuple(frame["datetime"].dt.to_pydatetime())
        prev_closes = build_previous_close_index(frame)

        sim = _make_simulator(self.temp_dir)
        om = PendingOrderManager()
        # Breakout A at 10.20: fills at 10:00.
        om.add_buy_order("breakout", quantity=1, trigger_price=10.20,
                         reason="morning buy")
        # Breakout B at 10.40: fills at 11:00 (first bar with high >= 10.40).
        om.add_buy_order("breakout", quantity=2, trigger_price=10.40,
                         reason="midday buy")

        clock = ReplayClock(timeline, initial_time=timeline[7],
                            active_period="30m")
        while clock.has_next():
            r = execute_trading_advance(
                plan=clock.plan_next(), clock=clock, base_bars=frame,
                previous_closes=prev_closes, simulator=sim, order_manager=om,
                stock_code=STOCK_CODE, display_period="30m",
            )
            self.assertTrue(r.success, r.error)

        hist = sim.get_trade_history_with_bar_id()
        buys = [t for t in hist if t["action"] == "buy"]
        self.assertEqual(len(buys), 2)

        self.assertEqual(buys[0]["trade_date"], "2025-01-03")
        self.assertEqual(buys[1]["trade_date"], "2025-01-03")
        self.assertRegex(buys[0]["trade_date"], r"^\d{4}-\d{2}-\d{2}$")
        self.assertEqual(buys[0]["trade_time"], "2025-01-03 10:00:00")
        self.assertEqual(buys[1]["trade_time"], "2025-01-03 11:00:00")
        self.assertRegex(buys[0]["trade_time"],
                         r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")
        self.assertEqual(buys[0]["display_period"], "30m")
        self.assertEqual(buys[1]["display_period"], "30m")
        self.assertEqual(buys[0]["quantity"], 1)
        self.assertEqual(buys[1]["quantity"], 2)

    def test_display_period_reflects_selected_period(self):
        """daily advance records display_period='daily'."""
        day1 = _flat_day("2025-01-02", price=10.0)
        day2 = [
            _bar("2025-01-03", "10:00", 10.10, 10.20, 10.05, 10.15),
            _bar("2025-01-03", "10:30", 10.15, 10.30, 10.10, 10.25),
            _bar("2025-01-03", "11:00", 10.25, 10.40, 10.20, 10.35),
            _bar("2025-01-03", "11:30", 10.35, 10.55, 10.30, 10.50),
            _bar("2025-01-03", "13:30", 10.50, 10.65, 10.45, 10.60),
            _bar("2025-01-03", "14:00", 10.60, 10.75, 10.55, 10.70),
            _bar("2025-01-03", "14:30", 10.70, 10.85, 10.65, 10.80),
            _bar("2025-01-03", "15:00", 10.80, 10.95, 10.75, 10.90),
        ]
        frame = _frame(*(day1 + day2))
        timeline = tuple(frame["datetime"].dt.to_pydatetime())
        prev_closes = build_previous_close_index(frame)

        sim = _make_simulator(self.temp_dir)
        om = PendingOrderManager()
        om.add_buy_order("breakout", quantity=1, trigger_price=10.20,
                         reason="display period test")

        clock = ReplayClock(timeline, initial_time=timeline[7],
                            active_period="daily")
        r = execute_trading_advance(
            plan=clock.plan_next(), clock=clock, base_bars=frame,
            previous_closes=prev_closes, simulator=sim, order_manager=om,
            stock_code=STOCK_CODE, display_period="daily",
        )
        self.assertTrue(r.success, r.error)

        hist = sim.get_trade_history_with_bar_id()
        self.assertEqual(len(hist), 1)
        self.assertEqual(hist[0]["display_period"], "daily")
        self.assertEqual(hist[0]["trade_date"], "2025-01-03")
        self.assertEqual(hist[0]["trade_time"], "2025-01-03 10:00:00")


if __name__ == "__main__":
    unittest.main()
