import unittest
from datetime import date
from pathlib import Path

import pandas as pd

from backend.intraday.models import AGGREGATED_COLUMNS, PeriodBoundaryIndex, ReplayPeriod


FIXTURE = Path(__file__).parent / "fixtures" / "intraday" / "600000_30m_sample.csv"


class IntradayAggregatorTests(unittest.TestCase):
    def load_frame(self):
        return pd.read_csv(FIXTURE, parse_dates=["datetime"])

    def boundary_index(self, frame, *, incomplete_sessions=frozenset()):
        timestamps = tuple(frame["datetime"].dt.to_pydatetime())
        session_ends = frozenset(
            group.iloc[-1].to_pydatetime()
            for _, group in frame.groupby(frame["datetime"].dt.date)["datetime"]
        )
        week_ends = frozenset(
            group.iloc[-1].to_pydatetime()
            for _, group in frame.groupby(
                frame["datetime"].map(lambda value: value.isocalendar()[:2])
            )["datetime"]
        )
        return PeriodBoundaryIndex(
            timestamps=timestamps,
            session_ends=session_ends,
            week_ends=week_ends,
            incomplete_sessions=incomplete_sessions,
        )

    def aggregate(self, frame, period, current_time, *, boundary_index=None):
        from backend.intraday.aggregator import aggregate_bars

        return aggregate_bars(
            frame,
            period,
            current_time,
            boundary_index=boundary_index,
        )

    def test_30m_returns_only_revealed_bars_with_contract_columns(self):
        frame = self.load_frame()
        current_time = pd.Timestamp("2025-01-02 11:00:00")

        result = self.aggregate(frame, "30m", current_time)

        self.assertEqual(tuple(result.columns), AGGREGATED_COLUMNS)
        self.assertEqual(len(result), 3)
        self.assertEqual(result["period"].tolist(), [ReplayPeriod.MINUTE_30.value] * 3)
        self.assertEqual(result["source_bar_count"].tolist(), [1, 1, 1])
        self.assertTrue(result["complete"].all())
        self.assertEqual(result.iloc[-1]["end_time"], current_time)

    def test_complete_day_aggregates_ohlcv_and_is_complete(self):
        frame = self.load_frame()
        boundary_index = self.boundary_index(frame)

        result = self.aggregate(
            frame,
            ReplayPeriod.DAILY,
            pd.Timestamp("2025-01-02 15:00:00"),
            boundary_index=boundary_index,
        )

        self.assertEqual(len(result), 1)
        bar = result.iloc[0]
        self.assertEqual(bar["open"], 10.00)
        self.assertEqual(bar["high"], 10.32)
        self.assertEqual(bar["low"], 9.95)
        self.assertEqual(bar["close"], 10.30)
        self.assertEqual(bar["volume"], 8750)
        self.assertEqual(bar["amount"], 88997)
        self.assertEqual(bar["source_bar_count"], 8)
        self.assertTrue(bool(bar["complete"]))

    def test_partial_day_uses_only_revealed_values_and_is_incomplete(self):
        frame = self.load_frame()
        boundary_index = self.boundary_index(frame)

        result = self.aggregate(
            frame,
            "daily",
            pd.Timestamp("2025-01-02 11:30:00"),
            boundary_index=boundary_index,
        )

        bar = result.iloc[0]
        self.assertEqual(bar["close"], 10.12)
        self.assertEqual(bar["high"], 10.30)
        self.assertEqual(bar["low"], 9.95)
        self.assertEqual(bar["volume"], 3800)
        self.assertEqual(bar["source_bar_count"], 4)
        self.assertFalse(bool(bar["complete"]))

    def test_session_4h_and_daily_have_equal_aggregated_values(self):
        frame = self.load_frame()
        boundary_index = self.boundary_index(frame)
        current_time = pd.Timestamp("2025-01-03 11:30:00")

        session = self.aggregate(frame, "4h_session", current_time, boundary_index=boundary_index)
        daily = self.aggregate(frame, "daily", current_time, boundary_index=boundary_index)

        comparable = [column for column in AGGREGATED_COLUMNS if column != "period"]
        pd.testing.assert_frame_equal(
            session[comparable].reset_index(drop=True),
            daily[comparable].reset_index(drop=True),
        )

    def test_weekly_aggregates_multiple_trading_days(self):
        frame = self.load_frame()
        boundary_index = self.boundary_index(frame)

        result = self.aggregate(
            frame,
            "weekly",
            pd.Timestamp("2025-01-03 15:00:00"),
            boundary_index=boundary_index,
        )

        self.assertEqual(len(result), 1)
        bar = result.iloc[0]
        self.assertEqual(bar["open"], 10.00)
        self.assertEqual(bar["high"], 10.45)
        self.assertEqual(bar["low"], 9.95)
        self.assertEqual(bar["close"], 10.35)
        self.assertEqual(bar["source_bar_count"], 16)
        self.assertTrue(bool(bar["complete"]))

    def test_incomplete_session_prevents_daily_and_weekly_completion(self):
        frame = self.load_frame()
        boundary_index = self.boundary_index(
            frame,
            incomplete_sessions=frozenset({date(2025, 1, 3)}),
        )
        current_time = pd.Timestamp("2025-01-03 15:00:00")

        daily = self.aggregate(frame, "daily", current_time, boundary_index=boundary_index)
        weekly = self.aggregate(frame, "weekly", current_time, boundary_index=boundary_index)

        self.assertFalse(bool(daily.iloc[-1]["complete"]))
        self.assertFalse(bool(weekly.iloc[-1]["complete"]))

    def test_future_extremes_do_not_leak_into_partial_aggregation(self):
        frame = self.load_frame()
        boundary_index = self.boundary_index(frame)
        current_time = pd.Timestamp("2025-01-02 11:30:00")
        expected = self.aggregate(frame, "daily", current_time, boundary_index=boundary_index)
        changed = frame.copy()
        future = changed["datetime"] > current_time
        changed.loc[future, "high"] = 999999
        changed.loc[future, "low"] = -999999
        changed.loc[future, "close"] = 777777
        changed.loc[future, "volume"] = 888888
        changed.loc[future, "amount"] = 999999

        actual = self.aggregate(changed, "daily", current_time, boundary_index=boundary_index)

        pd.testing.assert_frame_equal(actual, expected)

    def test_iso_year_is_part_of_week_bucket(self):
        rows = [
            ["2024-01-05 15:00:00", 10, 11, 9, 10.5, 100, 1000],
            ["2024-12-30 15:00:00", 20, 21, 19, 20.5, 200, 2000],
            ["2025-12-29 15:00:00", 30, 31, 29, 30.5, 300, 3000],
        ]
        frame = pd.DataFrame(
            rows,
            columns=["datetime", "open", "high", "low", "close", "volume", "amount"],
        )
        frame["datetime"] = pd.to_datetime(frame["datetime"])
        boundary_index = self.boundary_index(frame)

        result = self.aggregate(
            frame,
            "weekly",
            pd.Timestamp("2025-12-29 15:00:00"),
            boundary_index=boundary_index,
        )

        self.assertEqual(len(result), 3)
        self.assertEqual(result["source_bar_count"].tolist(), [1, 1, 1])
        self.assertEqual(result["open"].tolist(), [10, 20, 30])


if __name__ == "__main__":
    unittest.main()
