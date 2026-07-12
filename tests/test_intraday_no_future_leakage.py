import unittest
from datetime import datetime

import pandas as pd

from backend.intraday.aggregator import aggregate_bars
from backend.intraday.replay_clock import ReplayClock


SESSION_TIMES = ("10:00", "10:30", "11:00", "11:30", "13:30", "14:00", "14:30", "15:00")


def make_session(day, base_price):
    rows = []
    for index, clock_time in enumerate(SESSION_TIMES):
        open_price = base_price + index * 0.1
        rows.append(
            {
                "datetime": pd.Timestamp(f"{day} {clock_time}:00"),
                "open": open_price,
                "high": open_price + 0.25,
                "low": open_price - 0.2,
                "close": open_price + 0.05,
                "volume": 1000 + index * 10,
                "amount": 10000 + index * 100,
            }
        )
    return rows


class IntradayNoFutureLeakageTests(unittest.TestCase):
    def setUp(self):
        rows = []
        rows.extend(make_session("2025-01-06", 10))
        rows.extend(make_session("2025-01-07", 20))
        rows.extend(make_session("2025-01-08", 30))
        rows.extend(make_session("2025-01-10", 40))
        rows.extend(make_session("2025-01-13", 50))
        self.frame = pd.DataFrame(rows)
        self.timeline = tuple(self.frame["datetime"].dt.to_pydatetime())
        self.clock = ReplayClock(self.timeline)
        self.boundary_index = self.clock.boundary_index

    def aggregate(self, frame, period, current_time):
        return aggregate_bars(
            frame,
            period,
            current_time,
            boundary_index=self.boundary_index,
        )

    def assert_period_unchanged_by_future_mutation(self, period, current_time):
        expected = self.aggregate(self.frame, period, current_time)
        changed = self.frame.copy()
        future = changed["datetime"] > current_time
        changed.loc[future, "high"] = 999999.0
        changed.loc[future, "low"] = -999999.0
        changed.loc[future, "close"] = 777777.0
        changed.loc[future, "volume"] = 888888.0
        changed.loc[future, "amount"] = 999999.0

        actual = self.aggregate(changed, period, current_time)

        pd.testing.assert_frame_equal(actual, expected)

    def test_future_ohlcv_mutations_do_not_change_current_daily_or_weekly(self):
        current_time = datetime(2025, 1, 7, 11, 30)

        for period in ("daily", "weekly"):
            with self.subTest(period=period):
                self.assert_period_unchanged_by_future_mutation(period, current_time)

    def test_removing_future_ohlcv_with_same_boundary_index_does_not_change_results(self):
        current_time = datetime(2025, 1, 7, 11, 30)
        revealed_only = self.frame.loc[self.frame["datetime"] <= current_time].copy()

        for period in ("daily", "weekly"):
            with self.subTest(period=period):
                expected = self.aggregate(self.frame, period, current_time)
                actual = self.aggregate(revealed_only, period, current_time)
                pd.testing.assert_frame_equal(actual, expected)

    def test_period_switching_preserves_current_time_and_current_base_close(self):
        current_time = datetime(2025, 1, 7, 11, 30)
        clock = ReplayClock(self.timeline, initial_time=current_time, active_period="30m")
        expected_close = self.frame.loc[self.frame["datetime"] == current_time, "close"].iloc[0]

        for period in ("daily", "weekly", "30m"):
            clock.set_period(period)
            self.assertEqual(clock.current_time, current_time)
            visible = aggregate_bars(
                self.frame,
                period,
                clock.current_time,
                boundary_index=clock.boundary_index,
            )
            self.assertEqual(visible.iloc[-1]["close"], expected_close)

    def test_plan_next_contains_only_real_timeline_times_in_strict_interval(self):
        current_time = datetime(2025, 1, 7, 11, 30)
        timeline_set = set(self.timeline)

        for period in ("30m", "daily", "weekly"):
            with self.subTest(period=period):
                clock = ReplayClock(self.timeline, initial_time=current_time, active_period=period)
                plan = clock.plan_next()
                self.assertIsNotNone(plan.target_time)
                self.assertIn(plan.target_time, timeline_set)
                self.assertTrue(plan.base_bar_times)
                self.assertEqual(plan.base_bar_times[-1], plan.target_time)
                self.assertTrue(all(value in timeline_set for value in plan.base_bar_times))
                self.assertTrue(all(current_time < value <= plan.target_time for value in plan.base_bar_times))
                expected = tuple(value for value in self.timeline if current_time < value <= plan.target_time)
                self.assertEqual(plan.base_bar_times, expected)

    def test_partial_daily_does_not_read_later_bars_from_same_day(self):
        current_time = datetime(2025, 1, 7, 11, 30)
        result = self.aggregate(self.frame, "daily", current_time)
        current_day = result.iloc[-1]
        revealed = self.frame.loc[
            (self.frame["datetime"].dt.date == current_time.date())
            & (self.frame["datetime"] <= current_time)
        ]

        self.assertEqual(current_day["high"], revealed["high"].max())
        self.assertEqual(current_day["low"], revealed["low"].min())
        self.assertEqual(current_day["close"], revealed.iloc[-1]["close"])
        self.assertEqual(current_day["volume"], revealed["volume"].sum())
        self.assertEqual(current_day["amount"], revealed["amount"].sum())
        self.assertFalse(bool(current_day["complete"]))

    def test_partial_weekly_does_not_read_later_intraday_or_trading_days(self):
        current_time = datetime(2025, 1, 7, 11, 30)
        result = self.aggregate(self.frame, "weekly", current_time)
        current_week = result.iloc[-1]
        revealed = self.frame.loc[self.frame["datetime"] <= current_time]

        self.assertEqual(current_week["high"], revealed["high"].max())
        self.assertEqual(current_week["low"], revealed["low"].min())
        self.assertEqual(current_week["close"], revealed.iloc[-1]["close"])
        self.assertEqual(current_week["volume"], revealed["volume"].sum())
        self.assertEqual(current_week["amount"], revealed["amount"].sum())
        self.assertFalse(bool(current_week["complete"]))


if __name__ == "__main__":
    unittest.main()
