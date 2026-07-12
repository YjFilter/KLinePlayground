import unittest
from datetime import datetime

import pandas as pd

from backend.intraday.replay_clock import ReplayClock
from backend.intraday.trading_context import build_previous_close_index


TIMES = ("10:00", "10:30", "11:00", "11:30", "13:30", "14:00", "14:30", "15:00")


def frame_for_days(*days):
    rows = []
    for day_number, day in enumerate(days):
        for index, time_value in enumerate(TIMES):
            price = 10 + day_number + index / 10
            rows.append({
                "datetime": pd.Timestamp(f"{day} {time_value}:00"),
                "open": price,
                "high": price + 0.2,
                "low": price - 0.2,
                "close": price + 0.1,
                "volume": 1000,
                "amount": 10000,
            })
    return pd.DataFrame(rows)


class FakeSimulator:
    def __init__(self):
        self.updates = []
        self.trades = []

    def update_current_price(self, price, bar_id):
        self.updates.append((price, bar_id))

    def buy(self, quantity, price, trade_date, reason="", trade_time="", display_period=""):
        self.trades.append(("buy", quantity, price, trade_date, trade_time, display_period, reason))
        return {"success": True, "message": "ok"}

    def sell(self, quantity, price, trade_date, reason="", trade_time="", display_period=""):
        self.trades.append(("sell", quantity, price, trade_date, trade_time, display_period, reason))
        return {"success": True, "message": "ok"}


class FakeOrderManager:
    def __init__(self):
        self.calls = []

    def process_bar(self, bar, prev_close, stock_code, trade_date, execute_buy, execute_sell):
        self.calls.append((bar["datetime"], prev_close, stock_code, trade_date))
        result = execute_buy(1, bar["close"], {"reason": "test"})
        return [{"time": bar["datetime"], "success": result["success"]}]


class IntradayTradingEngineTests(unittest.TestCase):
    def test_daily_plan_processes_each_hidden_bar_with_previous_day_close_and_metadata(self):
        from backend.intraday.trading_engine import execute_trading_advance

        frame = frame_for_days("2025-01-02", "2025-01-03")
        timeline = tuple(frame["datetime"].dt.to_pydatetime())
        clock = ReplayClock(timeline, initial_time=timeline[8], active_period="daily")
        simulator = FakeSimulator()
        manager = FakeOrderManager()

        result = execute_trading_advance(
            plan=clock.plan_next(),
            clock=clock,
            base_bars=frame,
            previous_closes=build_previous_close_index(frame),
            simulator=simulator,
            order_manager=manager,
            stock_code="600000",
            display_period="daily",
        )

        expected_times = timeline[9:16]
        self.assertTrue(result.success)
        self.assertEqual(result.completed_times, expected_times)
        self.assertEqual(clock.current_time, timeline[15])
        self.assertEqual([call[0].to_pydatetime() for call in manager.calls], list(expected_times))
        self.assertTrue(all(abs(call[1] - 10.8) < 1e-9 for call in manager.calls))
        self.assertEqual([trade[4] for trade in simulator.trades], [value.isoformat(sep=" ") for value in expected_times])
        self.assertEqual({trade[5] for trade in simulator.trades}, {"daily"})

    def test_first_trading_day_passes_none_previous_close(self):
        from backend.intraday.trading_engine import execute_trading_advance

        frame = frame_for_days("2025-01-02")
        timeline = tuple(frame["datetime"].dt.to_pydatetime())
        clock = ReplayClock(timeline, initial_time=timeline[0], active_period="30m")
        manager = FakeOrderManager()

        execute_trading_advance(
            plan=clock.plan_next(),
            clock=clock,
            base_bars=frame,
            previous_closes=build_previous_close_index(frame),
            simulator=FakeSimulator(),
            order_manager=manager,
            stock_code="600000",
            display_period="30m",
        )

        self.assertIsNone(manager.calls[0][1])


if __name__ == "__main__":
    unittest.main()
