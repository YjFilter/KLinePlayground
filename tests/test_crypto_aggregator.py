from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pandas as pd
from pandas.core.groupby.generic import DataFrameGroupBy

import backend.crypto.aggregator as aggregator_module
from backend.crypto.aggregator import AGGREGATED_COLUMNS, aggregate_bars

UTC = timezone.utc

def make_frame(start, count):
    rows = []
    for index in range(count):
        timestamp = start + timedelta(minutes=5 * index)
        rows.append({"timestamp": timestamp, "open": 100 + index, "high": 102 + index, "low": 99 + index, "close": 101 + index, "volume": 1 + index, "turnover": 10 + index})
    return pd.DataFrame(rows)

class CryptoAggregatorTests(unittest.TestCase):
    def test_supports_all_periods_and_revealed_partial_bars(self):
        frame = make_frame(datetime(2024, 1, 1, 0, 0, tzinfo=UTC), 49)
        current = datetime(2024, 1, 1, 1, 5, tzinfo=UTC)
        expected_counts = {"5m": 14, "15m": 5, "30m": 3, "1h": 2, "4h": 1, "daily": 1, "weekly": 1}
        for period, count in expected_counts.items():
            with self.subTest(period=period):
                result = aggregate_bars(frame, period, current)
                self.assertEqual(tuple(result.columns), AGGREGATED_COLUMNS)
                self.assertEqual(len(result), count)
                self.assertLessEqual(result.iloc[-1]["end_time"], current)
        partial = aggregate_bars(frame, "15m", current).iloc[-1]
        self.assertFalse(bool(partial["complete"]))
        self.assertEqual(partial["source_bar_count"], 2)

    def test_uses_utc_day_week_and_year_boundaries(self):
        frame = make_frame(datetime(2023, 12, 31, 23, 50, tzinfo=UTC), 5)
        daily = aggregate_bars(frame, "daily", frame.iloc[-1]["timestamp"])
        weekly = aggregate_bars(frame, "weekly", frame.iloc[-1]["timestamp"])
        self.assertEqual(len(daily), 2)
        self.assertEqual(len(weekly), 2)
        self.assertEqual(daily.iloc[0]["end_time"], datetime(2023, 12, 31, 23, 55, tzinfo=UTC))
        self.assertFalse(bool(daily.iloc[0]["complete"]))
        self.assertEqual(weekly.iloc[0]["period"], "weekly")

    def test_future_values_never_change_revealed_aggregation(self):
        frame = make_frame(datetime(2024, 1, 1, 0, 0, tzinfo=UTC), 30)
        current = datetime(2024, 1, 1, 0, 40, tzinfo=UTC)
        for period in ("5m", "15m", "30m", "1h", "4h", "daily", "weekly"):
            expected = aggregate_bars(frame, period, current)
            changed = frame.copy()
            future = changed["timestamp"] > current
            changed.loc[future, ["open", "high", "low", "close", "volume", "turnover"]] = [1, 999999, -999999, 777777, 888888, 999999]
            pd.testing.assert_frame_equal(aggregate_bars(changed, period, current), expected)

    def test_aggregation_does_not_iterate_thousands_of_groups_in_python(self):
        frame = make_frame(datetime(2024, 1, 1, 0, 0, tzinfo=UTC), 100)
        with patch.object(DataFrameGroupBy, "__iter__", side_effect=AssertionError("group iteration is too slow")):
            result = aggregate_bars(frame, "5m", frame.iloc[-1]["timestamp"])
        self.assertEqual(len(result), 100)

    def test_normalized_base_bars_are_reused_without_reprocessing(self):
        normalize_base_bars = getattr(aggregator_module, "normalize_base_bars", None)
        self.assertIsNotNone(normalize_base_bars)
        frame = make_frame(datetime(2024, 1, 1, 0, 0, tzinfo=UTC), 12)
        frame["timestamp"] = frame["timestamp"].astype(str)
        frame["close"] = frame["close"].astype(str)

        normalized = normalize_base_bars(frame)
        reused = normalize_base_bars(normalized)

        self.assertIs(reused, normalized)
        self.assertIsInstance(normalized["timestamp"].dtype, pd.DatetimeTZDtype)
        self.assertTrue(pd.api.types.is_float_dtype(normalized["close"].dtype))

if __name__ == "__main__":
    unittest.main()
