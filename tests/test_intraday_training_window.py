from dataclasses import FrozenInstanceError
from datetime import date, datetime
import unittest

import pandas as pd

from backend.intraday.training_window import TrainingWindow, build_training_window


STANDARD_TIMES = (
    "10:00",
    "10:30",
    "11:00",
    "11:30",
    "13:30",
    "14:00",
    "14:30",
    "15:00",
)


def make_bars(days: list[str], times: tuple[str, ...] = STANDARD_TIMES) -> pd.DataFrame:
    rows = []
    for day in days:
        for time_text in times:
            rows.append(
                {
                    "datetime": pd.Timestamp(f"{day} {time_text}"),
                    "open": 10.0,
                    "high": 10.2,
                    "low": 9.8,
                    "close": 10.1,
                    "volume": 1000,
                    "amount": 10000,
                }
            )
    return pd.DataFrame(rows)


class TrainingWindowTests(unittest.TestCase):
    def test_limit_counts_distinct_trading_dates(self):
        days = pd.bdate_range("2025-01-02", periods=151).strftime("%Y-%m-%d").tolist()

        result = build_training_window(
            make_bars(days),
            datetime.fromisoformat(f"{days[0]} 10:00:00"),
            max_training_days=150,
        )

        self.assertIsInstance(result, TrainingWindow)
        self.assertEqual(len(result.trading_dates), 150)
        self.assertEqual(result.trading_dates[0], date.fromisoformat(days[0]))
        self.assertEqual(result.trading_dates[-1], date.fromisoformat(days[149]))
        self.assertEqual(
            result.cutoff_time,
            datetime.fromisoformat(f"{days[149]} 15:00:00"),
        )
        self.assertEqual(len(result.replay_bars), 150 * len(STANDARD_TIMES))

    def test_zero_limit_uses_all_remaining_trading_dates(self):
        frame = make_bars(["2025-01-02", "2025-01-03", "2025-01-06"])

        result = build_training_window(frame, datetime(2025, 1, 3, 10), 0)

        self.assertEqual(
            result.trading_dates,
            (date(2025, 1, 3), date(2025, 1, 6)),
        )
        self.assertEqual(result.cutoff_time, datetime(2025, 1, 6, 15))
        self.assertEqual(
            result.replay_bars.iloc[0]["datetime"],
            pd.Timestamp("2025-01-03 10:00"),
        )
        self.assertEqual(
            result.replay_bars.iloc[-1]["datetime"],
            pd.Timestamp("2025-01-06 15:00"),
        )

    def test_actual_data_dates_handle_gaps_and_suspensions(self):
        complete_first_day = make_bars(["2025-01-02"])
        suspended_day = make_bars(
            ["2025-01-08"],
            times=("10:00", "10:30", "11:00", "14:00"),
        )
        later_day = make_bars(["2025-01-20"])
        frame = pd.concat(
            [complete_first_day, suspended_day, later_day],
            ignore_index=True,
        )

        result = build_training_window(frame, datetime(2025, 1, 2, 10), 2)

        self.assertEqual(
            result.trading_dates,
            (date(2025, 1, 2), date(2025, 1, 8)),
        )
        self.assertEqual(result.cutoff_time, datetime(2025, 1, 8, 14))
        self.assertNotIn(date(2025, 1, 20), result.trading_dates)

    def test_single_day_limit_keeps_all_30_minute_bars_from_start_time(self):
        frame = make_bars(["2025-01-02", "2025-01-03"])
        start_time = datetime(2025, 1, 2, 11)

        result = build_training_window(frame, start_time, 1)

        self.assertEqual(result.trading_dates, (date(2025, 1, 2),))
        self.assertEqual(len(result.replay_bars), 6)
        self.assertEqual(result.replay_bars.iloc[0]["datetime"], pd.Timestamp(start_time))
        self.assertEqual(
            result.replay_bars.iloc[-1]["datetime"],
            pd.Timestamp("2025-01-02 15:00"),
        )

    def test_cutoff_is_last_timestamp_of_final_selected_trading_date(self):
        first_day = make_bars(["2025-01-02"], times=("10:00", "10:30"))
        final_day = make_bars(["2025-01-03"], times=("10:00", "13:30", "14:30"))
        excluded_day = make_bars(["2025-01-06"], times=("10:00",))
        frame = pd.concat([first_day, final_day, excluded_day], ignore_index=True)

        result = build_training_window(frame, datetime(2025, 1, 2, 10), 2)

        self.assertEqual(result.cutoff_time, datetime(2025, 1, 3, 14, 30))
        self.assertTrue(
            (
                result.replay_bars["datetime"]
                <= pd.Timestamp(result.cutoff_time)
            ).all()
        )
        self.assertEqual(
            result.replay_bars.iloc[-1]["datetime"],
            pd.Timestamp(result.cutoff_time),
        )

    def test_limit_larger_than_remaining_data_uses_available_dates(self):
        frame = make_bars(["2025-01-02", "2025-01-03"])

        result = build_training_window(frame, datetime(2025, 1, 2, 10), 150)

        self.assertEqual(
            result.trading_dates,
            (date(2025, 1, 2), date(2025, 1, 3)),
        )
        self.assertEqual(result.cutoff_time, datetime(2025, 1, 3, 15))

    def test_missing_start_time_raises_value_error(self):
        frame = make_bars(["2025-01-02"])

        with self.assertRaisesRegex(ValueError, "start_time"):
            build_training_window(frame, datetime(2025, 1, 2, 10, 15), 1)

    def test_negative_limit_raises_value_error(self):
        frame = make_bars(["2025-01-02"])

        with self.assertRaisesRegex(ValueError, "non-negative"):
            build_training_window(frame, datetime(2025, 1, 2, 10), -1)

    def test_duplicate_timestamps_raise_value_error(self):
        frame = make_bars(["2025-01-02"])
        frame = pd.concat([frame, frame.iloc[[0]]], ignore_index=True).sort_values(
            "datetime",
            kind="stable",
            ignore_index=True,
        )

        with self.assertRaisesRegex(ValueError, "unique and increasing"):
            build_training_window(frame, datetime(2025, 1, 2, 10), 1)

    def test_unsorted_timestamps_raise_value_error(self):
        frame = make_bars(["2025-01-02"]).iloc[
            [1, 0, 2, 3, 4, 5, 6, 7]
        ].reset_index(drop=True)

        with self.assertRaisesRegex(ValueError, "unique and increasing"):
            build_training_window(frame, datetime(2025, 1, 2, 10), 1)

    def test_input_dataframe_is_not_modified(self):
        frame = make_bars(["2025-01-02", "2025-01-03"])
        frame["datetime"] = frame["datetime"].dt.strftime("%Y-%m-%d %H:%M:%S")
        original = frame.copy(deep=True)

        result = build_training_window(frame, datetime(2025, 1, 2, 10), 1)

        pd.testing.assert_frame_equal(frame, original)
        self.assertTrue(pd.api.types.is_datetime64_any_dtype(result.replay_bars["datetime"]))

    def test_result_fields_are_frozen(self):
        result = build_training_window(
            make_bars(["2025-01-02"]),
            datetime(2025, 1, 2, 10),
            1,
        )

        with self.assertRaises(FrozenInstanceError):
            result.cutoff_time = datetime(2025, 1, 2, 10, 30)


if __name__ == "__main__":
    unittest.main()
