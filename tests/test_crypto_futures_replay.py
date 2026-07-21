from __future__ import annotations

import json
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pandas as pd

from backend.crypto.futures_engine import FuturesEngine
from backend.crypto.futures_orders import FuturesOrderBook
from backend.crypto.futures_simulator import FuturesSimulator
from backend.crypto.models import FundingEvent
from backend.crypto.replay_clock import CryptoReplayClock
from backend.crypto.trading import FuturesReplayExecutor


UTC = timezone.utc


def make_frames(start, count):
    trade_rows = []
    mark_rows = []
    for index in range(count):
        timestamp = start + timedelta(minutes=5 * index)
        close = Decimal("100") + Decimal(index % 7) / Decimal("10")
        trade_rows.append({"timestamp": timestamp, "open": close, "high": close + 1, "low": close - 1, "close": close})
        mark_rows.append({"timestamp": timestamp, "open": close, "high": close + Decimal("0.8"), "low": close - Decimal("0.8"), "close": close})
    return pd.DataFrame(trade_rows), pd.DataFrame(mark_rows)


def make_executor(period, start, count):
    trade, mark = make_frames(start, count)
    simulator = FuturesSimulator(initial_balance="10000", quantity_step="0.001", min_quantity="0.001", min_notional="5", leverage=5)
    orders = FuturesOrderBook(simulator)
    engine = FuturesEngine(simulator, orders)
    funding = [FundingEvent(source="binance", symbol="BTCUSDT", timestamp=start + timedelta(minutes=10), rate=Decimal("0.0001"), mark_price=Decimal("100.2"))]
    clock = CryptoReplayClock(trade["timestamp"], initial_time=start, active_period=period)
    executor = FuturesReplayExecutor(clock=clock, trade_bars=trade, mark_bars=mark, engine=engine, funding_events=funding, symbol="BTCUSDT", source="binance")
    executor.submit_order(action="open_long", order_type="market", margin="1000", leverage=5)
    return executor


class FuturesReplayExecutorTests(unittest.TestCase):
    def test_funding_before_replay_start_is_not_charged_to_a_new_position(self):
        start = datetime(2024, 1, 1, 5, 10, tzinfo=UTC)
        trade, mark = make_frames(start, 3)
        simulator = FuturesSimulator(initial_balance="10000", quantity_step="0.001", min_quantity="0.001", min_notional="5", leverage=5)
        engine = FuturesEngine(simulator, FuturesOrderBook(simulator))
        clock = CryptoReplayClock(trade["timestamp"], initial_time=start, active_period="5m")
        past = FundingEvent(source="binance", symbol="BTCUSDT", timestamp=start - timedelta(hours=8), rate=Decimal("0.01"), mark_price=Decimal("100"))
        current = FundingEvent(source="binance", symbol="BTCUSDT", timestamp=start + timedelta(minutes=5), rate=Decimal("0.001"), mark_price=Decimal("100"))
        executor = FuturesReplayExecutor(
            clock=clock, trade_bars=trade, mark_bars=mark, engine=engine,
            funding_events=(past, current), symbol="BTCUSDT", source="binance",
        )
        executor.submit_order(action="open_long", order_type="market", margin="1000", leverage=5)

        result = executor.advance()

        self.assertEqual([event["timestamp"] for event in result["funding_events"]], [current.timestamp.isoformat()])
        self.assertEqual(simulator.account.funding_paid, Decimal("5.000"))

    def test_large_periods_equal_repeated_five_minute_advances(self):
        cases = {
            "1h": (datetime(2024, 1, 7, 0, 0, tzinfo=UTC), 13),
            "4h": (datetime(2024, 1, 7, 0, 0, tzinfo=UTC), 49),
            "daily": (datetime(2024, 1, 7, 0, 0, tzinfo=UTC), 288),
            "weekly": (datetime(2024, 1, 7, 0, 0, tzinfo=UTC), 288),
        }
        for period, (start, count) in cases.items():
            with self.subTest(period=period):
                large = make_executor(period, start, count)
                small = make_executor("5m", start, count)
                large_result = large.advance()
                while small.clock.current_time < large.clock.current_time:
                    small.advance()
                self.assertEqual(large_result["completed_times"][-1], large.clock.current_time.isoformat())
                self.assertEqual(large.state_signature(), small.state_signature())

    def test_snapshot_contains_trading_state_events_and_markers(self):
        start = datetime(2024, 1, 1, tzinfo=UTC)
        executor = make_executor("15m", start, 6)
        result = executor.advance()
        self.assertEqual(result["market_type"], "crypto_perpetual")
        self.assertIn("account", result)
        self.assertIn("position", result)
        self.assertIn("orders", result)
        self.assertEqual(len(result["funding_events"]), 1)
        self.assertEqual(result["trade_markers"][0]["type"], "L")
        json.dumps(result)

    def test_missing_inputs_do_not_commit_the_clock(self):
        start = datetime(2024, 1, 1, tzinfo=UTC)
        trade, mark = make_frames(start, 4)
        mark = mark.iloc[:1]
        simulator = FuturesSimulator(initial_balance="1000", quantity_step="0.001", min_quantity="0.001", min_notional="5")
        engine = FuturesEngine(simulator, FuturesOrderBook(simulator))
        clock = CryptoReplayClock(trade["timestamp"], active_period="15m")
        executor = FuturesReplayExecutor(clock=clock, trade_bars=trade, mark_bars=mark, engine=engine)
        with self.assertRaisesRegex(ValueError, "mark bar"):
            executor.advance()
        self.assertEqual(clock.current_time, start)
        self.assertEqual(engine.equity_snapshots, [])

    def test_stale_reduce_only_does_not_abort_replay_clock_commit(self):
        start = datetime(2024, 1, 1, tzinfo=UTC)
        trade, mark = make_frames(start, 3)
        trade.loc[1, "high"] = Decimal("110")
        simulator = FuturesSimulator(initial_balance="1000", quantity_step="0.001", min_quantity="0.001", min_notional="5")
        orders = FuturesOrderBook(simulator)
        engine = FuturesEngine(simulator, orders)
        clock = CryptoReplayClock(trade["timestamp"], active_period="5m")
        executor = FuturesReplayExecutor(clock=clock, trade_bars=trade, mark_bars=mark, engine=engine)
        executor.submit_order(action="open_long", order_type="market", margin="100", leverage=5)
        first = executor.submit_order(action="close", order_type="limit", limit_price="105")
        second = executor.submit_order(action="close", order_type="limit", limit_price="105")
        result = executor.advance()
        self.assertEqual(clock.current_time, start + timedelta(minutes=5))
        self.assertEqual(first.status, "filled")
        self.assertEqual(second.status, "cancelled")
        self.assertEqual(second.cancel_reason, "position_flat")
        self.assertEqual(result["orders"][1]["status"], "filled")

    def test_reversal_markers_emit_close_then_new_direction(self):
        start = datetime(2024, 1, 1, tzinfo=UTC)
        executor = make_executor("5m", start, 3)
        executor.submit_order(action="open_short", order_type="market", margin="2000", leverage=5)
        self.assertEqual([marker["type"] for marker in executor.snapshot()["trade_markers"][-2:]], ["X", "S"])


if __name__ == "__main__":
    unittest.main()
