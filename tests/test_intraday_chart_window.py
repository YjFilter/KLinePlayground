from __future__ import annotations

from datetime import datetime
import json
import unittest

import pandas as pd
from pandas.testing import assert_frame_equal

from backend.intraday.chart_window import ChartWindowService
from backend.intraday.models import IntradayRange


TIMES = ("10:00", "10:30", "11:00", "11:30", "13:30", "14:00", "14:30", "15:00")


def make_frame() -> pd.DataFrame:
    rows = []
    for day_number, day in enumerate(pd.bdate_range("2025-01-02", "2025-01-10"), start=1):
        for bar_number, time_text in enumerate(TIMES, start=1):
            price = float(day_number * 100 + bar_number)
            rows.append({
                "datetime": pd.Timestamp(f"{day.date()} {time_text}"),
                "open": price,
                "high": price + 2.0,
                "low": price - 2.0,
                "close": price + 1.0,
                "volume": day_number * 1000 + bar_number,
                "amount": float(day_number * 10000 + bar_number),
            })
    return pd.DataFrame(rows)


class FakeCache:
    def __init__(self, frame: pd.DataFrame):
        self.frame = frame

    def coverage(self, stock_code: str) -> IntradayRange:
        del stock_code
        return IntradayRange(
            self.frame["datetime"].min().to_pydatetime(),
            self.frame["datetime"].max().to_pydatetime(),
        )


class FakeDataService:
    def __init__(self, frame: pd.DataFrame):
        self.frame = frame
        self.cache = FakeCache(frame)
        self.requests: list[tuple[str, datetime, datetime]] = []
        self.return_full_frame = False

    def get_30m(self, stock_code: str, start: datetime, end: datetime) -> pd.DataFrame:
        self.requests.append((stock_code, start, end))
        if self.return_full_frame:
            return self.frame
        mask = (self.frame["datetime"] >= pd.Timestamp(start)) & (
            self.frame["datetime"] <= pd.Timestamp(end)
        )
        return self.frame.loc[mask].reset_index(drop=True)


class ChartWindowServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.frame = make_frame()
        self.loader = FakeDataService(self.frame)
        self.service = ChartWindowService(self.loader)

    def load(self, **overrides):
        arguments = {
            "stock_code": "600000",
            "period": "30m",
            "range_start": datetime(2025, 1, 2, 10, 0),
            "range_end": datetime(2025, 1, 10, 15, 0),
            "current_time": datetime(2025, 1, 10, 15, 0),
            "read_only": True,
        }
        arguments.update(overrides)
        return self.service.load(**arguments)

    def test_aggregates_all_supported_periods_with_existing_semantics(self):
        expected = {
            "30m": (56, 1),
            "4h_session": (7, 8),
            "daily": (7, 8),
            "weekly": (2, 16),
        }
        for period, (bar_count, first_source_count) in expected.items():
            with self.subTest(period=period):
                result = self.load(period=period)
                self.assertEqual(result.period, period)
                self.assertEqual(len(result.kline_data), bar_count)
                self.assertEqual(result.kline_data[0]["source_bar_count"], first_source_count)
                self.assertEqual(len(result.volume_data), bar_count)
                self.assertEqual(result.volume_data[0]["value"], result.kline_data[0]["volume"])

        daily = self.load(period="daily").kline_data[0]
        first_day = self.frame[self.frame["datetime"].dt.date == datetime(2025, 1, 2).date()]
        self.assertEqual(daily["open"], float(first_day.iloc[0]["open"]))
        self.assertEqual(daily["high"], float(first_day["high"].max()))
        self.assertEqual(daily["low"], float(first_day["low"].min()))
        self.assertEqual(daily["close"], float(first_day.iloc[-1]["close"]))
        self.assertEqual(daily["volume"], int(first_day["volume"].sum()))

    def test_active_window_caps_requested_future_end_and_has_no_later_page(self):
        current_time = datetime(2025, 1, 6, 11, 0)
        result = self.load(
            period="daily",
            range_end=datetime(2026, 1, 1, 15, 0),
            current_time=current_time,
            read_only=False,
        )
        self.assertEqual(result.window_end, current_time)
        self.assertEqual(self.loader.requests[-1][2], current_time)
        self.assertFalse(result.has_later)
        self.assertTrue(
            all(bar["end_time"] <= "2025-01-06 11:00:00" for bar in result.kline_data)
        )

    def test_completed_window_can_load_after_training_end(self):
        training_end = datetime(2025, 1, 6, 15, 0)
        requested_end = datetime(2025, 1, 9, 15, 0)
        result = self.load(
            period="daily",
            range_end=requested_end,
            current_time=training_end,
            read_only=True,
        )
        self.assertEqual(result.window_end, requested_end)
        self.assertGreater(result.window_end, training_end)
        self.assertGreater(result.kline_data[-1]["end_time"], "2025-01-06 15:00:00")
        self.assertTrue(result.has_later)

    def test_active_window_never_leaks_future_ohlcv_extremes(self):
        current_time = datetime(2025, 1, 6, 11, 0)
        future_mask = self.frame["datetime"] > pd.Timestamp(current_time)
        self.frame.loc[future_mask, "high"] = 9_999_999.0
        self.frame.loc[future_mask, "low"] = -9_999_999.0
        self.frame.loc[future_mask, "close"] = 8_888_888.0
        self.frame.loc[future_mask, "volume"] = 7_777_777
        self.loader.return_full_frame = True

        result = self.load(
            period="weekly",
            range_end=datetime(2025, 1, 10, 15, 0),
            current_time=current_time,
            read_only=False,
        )
        self.assertTrue(result.kline_data)
        self.assertLess(max(bar["high"] for bar in result.kline_data), 9_999_999.0)
        self.assertGreater(min(bar["low"] for bar in result.kline_data), -9_999_999.0)
        self.assertLess(max(bar["close"] for bar in result.kline_data), 8_888_888.0)
        self.assertLess(max(bar["volume"] for bar in result.kline_data), 7_777_777)

    def test_window_payload_is_deterministic_and_json_serializable(self):
        first = self.load(period="4h_session")
        second = self.load(period="4h_session")
        self.assertEqual(first.to_dict(), second.to_dict())
        encoded = json.dumps(first.to_dict(), ensure_ascii=False)
        decoded = json.loads(encoded)
        self.assertEqual(decoded["window_start"], "2025-01-02 10:00:00")
        self.assertEqual(decoded["window_end"], "2025-01-10 15:00:00")
        self.assertTrue(decoded["read_only"])

    def test_availability_flags_follow_coverage_boundaries(self):
        coverage_start = self.frame["datetime"].min().to_pydatetime()
        coverage_end = self.frame["datetime"].max().to_pydatetime()
        full = self.load(range_start=coverage_start, range_end=coverage_end)
        self.assertFalse(full.has_earlier)
        self.assertFalse(full.has_later)

        middle = self.load(
            range_start=datetime(2025, 1, 3, 10, 0),
            range_end=datetime(2025, 1, 9, 15, 0),
        )
        self.assertTrue(middle.has_earlier)
        self.assertTrue(middle.has_later)

        active = self.load(
            range_start=datetime(2025, 1, 3, 10, 0),
            range_end=datetime(2025, 1, 9, 15, 0),
            current_time=datetime(2025, 1, 9, 15, 0),
            read_only=False,
        )
        self.assertTrue(active.has_earlier)
        self.assertFalse(active.has_later)

    def test_rejects_a_start_after_the_visible_end(self):
        with self.assertRaisesRegex(ValueError, "range_start must not exceed the visible end"):
            self.load(
                range_start=datetime(2025, 1, 7, 10, 0),
                range_end=datetime(2025, 1, 10, 15, 0),
                current_time=datetime(2025, 1, 6, 15, 0),
                read_only=False,
            )

    def test_loading_does_not_modify_input_data(self):
        original = self.frame.copy(deep=True)
        self.loader.return_full_frame = True
        self.load(period="weekly", read_only=False)
        assert_frame_equal(self.frame, original)


if __name__ == "__main__":
    unittest.main()
