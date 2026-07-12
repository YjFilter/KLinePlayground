"""Focused tests for ``backend.intraday.trading_context``.

These tests are deterministic and offline. They verify that
``build_previous_close_index`` builds an immutable lookup mapping each
trading date present in normalized 30-minute data to the previous
data-bearing trading date's final 30-minute close.

Covered acceptance criteria:
  * First trading date returns ``None`` for every intraday bar.
  * Every 30-minute bar on the same trading date returns the same
    previous close (per-day consistency).
  * Previous close is the LAST bar's close of the previous data-bearing
    trading date, not the previous 30-minute bar's close.
  * Weekends, holidays, suspensions, and non-consecutive calendar dates
    use actual data order (no calendar-driven lookup).
  * Short / incomplete sessions use their actual last bar close for the
    next trading day.
  * Input DataFrame is not mutated.
  * The index is immutable (frozen dataclass + read-only mapping).
  * Duplicate or unsorted timestamps raise ``ValueError`` instead of
    silently selecting a close.
  * Empty input returns an empty index.
  * Query ergonomics: ``datetime``, ``date``, and ``pandas.Timestamp``
    inputs all work; unknown trading dates raise.
  * Fixture-based integration with the existing 600000 sample.
"""

import unittest
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from backend.intraday.trading_context import (
    PreviousCloseIndex,
    build_previous_close_index,
)


FIXTURE = Path(__file__).parent / "fixtures" / "intraday" / "600000_30m_sample.csv"

# The eight legal 30-minute bar timestamps for a full A-share session.
STANDARD_TIMES = (
    "10:00", "10:30", "11:00", "11:30",
    "13:30", "14:00", "14:30", "15:00",
)


def _bar(day_str, time_str, close, *, open_=None, high=None, low=None,
         volume=1000, amount=10000):
    if open_ is None:
        open_ = close
    if high is None:
        high = close + 0.05
    if low is None:
        low = close - 0.05
    return {
        "datetime": f"{day_str} {time_str}:00",
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
        "amount": amount,
    }


def _day_bars(day_str, closes, times=STANDARD_TIMES):
    """Build ``len(times)`` 30-minute bars for a single trading date."""
    assert len(closes) == len(times), f"{len(closes)} closes vs {len(times)} times"
    return [_bar(day_str, t, c) for t, c in zip(times, closes)]


def _frame(rows):
    frame = pd.DataFrame(rows)
    frame["datetime"] = pd.to_datetime(frame["datetime"])
    return frame


class PreviousCloseIndexTests(unittest.TestCase):
    # ------------------------------------------------------------------
    # Fixture builders
    # ------------------------------------------------------------------
    def two_day_frame(self):
        """Fri 2025-01-03 + Mon 2025-01-06 (weekend gap).

        Day 1 final close = 10.35, day 2 final close = 10.40.
        """
        rows = _day_bars("2025-01-03", [10.10, 10.20, 10.15, 10.12, 10.05, 10.13, 10.24, 10.35]) \
             + _day_bars("2025-01-06", [10.40, 10.45, 10.42, 10.38, 10.30, 10.35, 10.32, 10.40])
        return _frame(rows)

    def three_day_frame(self):
        """2025-01-02, 2025-01-03, 2025-01-06.

        Final closes: 10.30, 10.35, 10.40.
        """
        rows = _day_bars("2025-01-02", [10.10, 10.20, 10.15, 10.12, 10.05, 10.13, 10.24, 10.30]) \
             + _day_bars("2025-01-03", [10.35, 10.38, 10.40, 10.36, 10.30, 10.25, 10.29, 10.35]) \
             + _day_bars("2025-01-06", [10.40, 10.45, 10.42, 10.38, 10.30, 10.35, 10.32, 10.40])
        return _frame(rows)

    def short_session_frame(self):
        """Day 2 has only 4 bars (incomplete session ending at 11:30).

        Day 1 final close = 10.30, day 2 final close = 10.20 (its 11:30 bar),
        day 3 final close = 10.40.
        """
        rows = _day_bars("2025-01-02", [10.10, 10.20, 10.15, 10.12, 10.05, 10.13, 10.24, 10.30]) \
             + _day_bars("2025-01-03", [10.35, 10.38, 10.40, 10.20], times=STANDARD_TIMES[:4]) \
             + _day_bars("2025-01-06", [10.40, 10.45, 10.42, 10.38, 10.30, 10.35, 10.32, 10.40])
        return _frame(rows)

    # ------------------------------------------------------------------
    # Acceptance: first trading date returns None
    # ------------------------------------------------------------------
    def test_first_trading_date_returns_none_for_every_bar(self):
        index = build_previous_close_index(self.two_day_frame())

        for time_str in STANDARD_TIMES:
            timestamp = datetime.fromisoformat(f"2025-01-03T{time_str}:00")
            self.assertIsNone(index.previous_close(timestamp))

    def test_first_trading_date_returns_none_via_date_query(self):
        index = build_previous_close_index(self.two_day_frame())
        self.assertIsNone(index.previous_close_for_date(date(2025, 1, 3)))

    # ------------------------------------------------------------------
    # Acceptance: per-day consistency
    # ------------------------------------------------------------------
    def test_every_bar_on_same_date_returns_same_previous_close(self):
        index = build_previous_close_index(self.two_day_frame())

        closes = {
            index.previous_close(datetime.fromisoformat(f"2025-01-06T{t}:00"))
            for t in STANDARD_TIMES
        }
        self.assertEqual(closes, {10.35})

    def test_previous_close_is_last_bar_close_of_previous_data_bearing_date(self):
        index = build_previous_close_index(self.two_day_frame())
        # 2025-01-03's final 30m bar close is 10.35.
        self.assertEqual(index.previous_close_for_date(date(2025, 1, 6)), 10.35)

    def test_previous_close_is_not_previous_30m_bar_close(self):
        """Within 2025-01-06, prev_close must be 2025-01-03's LAST bar close
        (10.35), NOT the previous 30-minute bar's close. At 10:30 the previous
        30m bar close would be 10.40 (the 10:00 bar); at 11:00 it would be
        10.45 (the 10:30 bar). The correct answer for every bar is 10.35."""
        index = build_previous_close_index(self.two_day_frame())

        self.assertEqual(index.previous_close(datetime(2025, 1, 6, 10, 0)), 10.35)
        self.assertEqual(index.previous_close(datetime(2025, 1, 6, 10, 30)), 10.35)
        self.assertEqual(index.previous_close(datetime(2025, 1, 6, 11, 0)), 10.35)
        self.assertEqual(index.previous_close(datetime(2025, 1, 6, 15, 0)), 10.35)

    # ------------------------------------------------------------------
    # Acceptance: multi-day chaining
    # ------------------------------------------------------------------
    def test_three_trading_days_chain_correctly(self):
        index = build_previous_close_index(self.three_day_frame())

        self.assertIsNone(index.previous_close_for_date(date(2025, 1, 2)))
        self.assertEqual(index.previous_close_for_date(date(2025, 1, 3)), 10.30)
        self.assertEqual(index.previous_close_for_date(date(2025, 1, 6)), 10.35)

    def test_trading_dates_preserved_in_data_order(self):
        index = build_previous_close_index(self.three_day_frame())
        self.assertEqual(
            index.trading_dates,
            (date(2025, 1, 2), date(2025, 1, 3), date(2025, 1, 6)),
        )

    # ------------------------------------------------------------------
    # Acceptance: weekends, holidays, suspensions, non-consecutive dates
    # ------------------------------------------------------------------
    def test_weekend_gap_uses_actual_data_order(self):
        """Fri 2025-01-03 -> Mon 2025-01-06: Monday's prev_close is Friday's
        last close, derived from actual data order rather than a calendar
        lookup that assumes a fixed weekend."""
        index = build_previous_close_index(self.two_day_frame())
        self.assertEqual(index.previous_close_for_date(date(2025, 1, 6)), 10.35)

    def test_holiday_gap_uses_actual_data_order(self):
        """2025-01-02 -> 2025-01-06 (as if Jan 3 was a holiday): the second
        trading date's prev_close is the first date's last close, even though
        the calendar gap spans multiple days."""
        rows = _day_bars("2025-01-02", [10.10, 10.20, 10.15, 10.12, 10.05, 10.13, 10.24, 10.30]) \
             + _day_bars("2025-01-06", [10.40, 10.45, 10.42, 10.38, 10.30, 10.35, 10.32, 10.40])
        index = build_previous_close_index(_frame(rows))
        self.assertIsNone(index.previous_close_for_date(date(2025, 1, 2)))
        self.assertEqual(index.previous_close_for_date(date(2025, 1, 6)), 10.30)

    def test_suspension_day_is_skipped_via_actual_data_order(self):
        """A suspended date has no rows in the frame; the next trading date's
        prev_close is the last data-bearing date's close. Same data shape as
        the holiday test, framed explicitly as a suspension."""
        rows = _day_bars("2025-01-02", [10.10, 10.20, 10.15, 10.12, 10.05, 10.13, 10.24, 10.30]) \
             + _day_bars("2025-01-06", [10.40, 10.45, 10.42, 10.38, 10.30, 10.35, 10.32, 10.40])
        index = build_previous_close_index(_frame(rows))
        self.assertNotIn(date(2025, 1, 3), index)
        self.assertEqual(index.previous_close_for_date(date(2025, 1, 6)), 10.30)

    # ------------------------------------------------------------------
    # Acceptance: short / incomplete sessions
    # ------------------------------------------------------------------
    def test_short_session_uses_actual_last_bar_close_for_next_day(self):
        """Day 2 has only 4 bars ending at 11:30 with close 10.20; day 3's
        prev_close must be 10.20 (the actual last bar), not day 2's first bar
        or any filled value."""
        index = build_previous_close_index(self.short_session_frame())

        self.assertEqual(index.previous_close_for_date(date(2025, 1, 3)), 10.30)
        self.assertEqual(index.previous_close_for_date(date(2025, 1, 6)), 10.20)

    def test_short_session_bars_all_return_same_previous_close(self):
        index = build_previous_close_index(self.short_session_frame())

        short_day_times = ("10:00", "10:30", "11:00", "11:30")
        closes = {
            index.previous_close(datetime.fromisoformat(f"2025-01-03T{t}:00"))
            for t in short_day_times
        }
        self.assertEqual(closes, {10.30})

    # ------------------------------------------------------------------
    # Acceptance: input is not mutated
    # ------------------------------------------------------------------
    def test_input_dataframe_not_mutated(self):
        frame = self.three_day_frame()
        original = frame.copy(deep=True)
        build_previous_close_index(frame)
        pd.testing.assert_frame_equal(frame, original)

    def test_input_with_string_datetimes_not_mutated(self):
        rows = _day_bars("2025-01-02", [10.0] * 8) + _day_bars("2025-01-03", [11.0] * 8)
        frame = pd.DataFrame(rows)  # datetime column is plain strings here
        original = frame.copy(deep=True)
        build_previous_close_index(frame)
        pd.testing.assert_frame_equal(frame, original)

    # ------------------------------------------------------------------
    # Acceptance: immutable lookup
    # ------------------------------------------------------------------
    def test_index_is_frozen_dataclass(self):
        index = build_previous_close_index(self.two_day_frame())
        with self.assertRaises(Exception):
            index.trading_dates = (date(2025, 1, 3),)
        with self.assertRaises(Exception):
            index._closes_by_date = {}

    def test_internal_mapping_is_read_only(self):
        index = build_previous_close_index(self.two_day_frame())
        mapping = index._closes_by_date
        with self.assertRaises(TypeError):
            mapping[date(2025, 1, 3)] = 999.0

    def test_repeated_queries_are_pure_and_consistent(self):
        index = build_previous_close_index(self.two_day_frame())
        first = index.previous_close(datetime(2025, 1, 6, 14, 30))
        second = index.previous_close(datetime(2025, 1, 6, 14, 30))
        self.assertEqual(first, second)
        self.assertEqual(first, 10.35)

    # ------------------------------------------------------------------
    # Acceptance: duplicate / unsorted timestamps fail clearly
    # ------------------------------------------------------------------
    def test_duplicate_timestamps_raise_value_error(self):
        rows = _day_bars("2025-01-02", [10.0] * 8)
        rows.append(_bar("2025-01-02", "10:00", 99.0))  # duplicate of first bar
        frame = _frame(rows)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            build_previous_close_index(frame)

    def test_unsorted_timestamps_raise_value_error(self):
        rows = _day_bars("2025-01-02", [10.0] * 8)
        rows[0], rows[1] = rows[1], rows[0]  # swap 10:00 and 10:30
        frame = _frame(rows)
        with self.assertRaisesRegex(ValueError, "sort|increasing|unsorted"):
            build_previous_close_index(frame)

    def test_unsorted_across_days_raises(self):
        rows = _day_bars("2025-01-02", [10.0] * 8) \
             + _day_bars("2025-01-03", [11.0] * 8)
        # Move the entire second day before the first day.
        rows = rows[8:] + rows[:8]
        frame = _frame(rows)
        with self.assertRaisesRegex(ValueError, "sort|increasing|unsorted"):
            build_previous_close_index(frame)

    def test_missing_required_columns_raise_value_error(self):
        frame = self.two_day_frame().drop(columns=["close"])
        with self.assertRaisesRegex(ValueError, "missing required columns"):
            build_previous_close_index(frame)

    def test_unparseable_datetime_raises_value_error(self):
        frame = self.two_day_frame()
        # Cast to object first so inserting a non-timestamp string does not
        # trip pandas' incompatible-dtype FutureWarning; the point of the
        # test is that ``build_previous_close_index`` rejects bad values, not
        # how pandas serializes the malformed cell.
        frame["datetime"] = frame["datetime"].astype(object)
        frame.loc[0, "datetime"] = "not-a-timestamp"
        with self.assertRaisesRegex(ValueError, "invalid datetime"):
            build_previous_close_index(frame)

    # ------------------------------------------------------------------
    # Acceptance: empty input
    # ------------------------------------------------------------------
    def test_empty_frame_returns_empty_index(self):
        frame = pd.DataFrame(
            columns=["datetime", "open", "high", "low", "close", "volume", "amount"]
        )
        index = build_previous_close_index(frame)
        self.assertEqual(index.trading_dates, ())
        self.assertNotIn(date(2025, 1, 2), index)
        with self.assertRaises(ValueError):
            index.previous_close_for_date(date(2025, 1, 2))

    # ------------------------------------------------------------------
    # Query ergonomics
    # ------------------------------------------------------------------
    def test_query_by_datetime_and_by_date_agree(self):
        index = build_previous_close_index(self.two_day_frame())
        by_dt = index.previous_close(datetime(2025, 1, 6, 14, 30))
        by_date = index.previous_close_for_date(date(2025, 1, 6))
        self.assertEqual(by_dt, by_date)

    def test_query_accepts_pandas_timestamp(self):
        index = build_previous_close_index(self.two_day_frame())
        self.assertEqual(index.previous_close(pd.Timestamp("2025-01-06 14:30:00")), 10.35)

    def test_query_accepts_pandas_timestamp_for_date(self):
        index = build_previous_close_index(self.two_day_frame())
        self.assertEqual(
            index.previous_close_for_date(pd.Timestamp("2025-01-06 14:30:00")),
            10.35,
        )

    def test_unknown_trading_date_raises(self):
        index = build_previous_close_index(self.two_day_frame())
        with self.assertRaisesRegex(ValueError, "unknown trading date"):
            index.previous_close_for_date(date(2025, 1, 2))  # not in two-day frame

    def test_contains_supports_date_and_timestamp(self):
        index = build_previous_close_index(self.two_day_frame())
        self.assertIn(date(2025, 1, 3), index)
        self.assertIn(date(2025, 1, 6), index)
        self.assertNotIn(date(2025, 1, 2), index)
        self.assertIn(pd.Timestamp("2025-01-06 10:00:00"), index)

    def test_previous_close_returns_public_type(self):
        index = build_previous_close_index(self.two_day_frame())
        self.assertIsInstance(index, PreviousCloseIndex)

    # ------------------------------------------------------------------
    # Fixture-based integration (offline, deterministic)
    # ------------------------------------------------------------------
    def test_fixture_first_day_returns_none_second_day_returns_prior_close(self):
        frame = pd.read_csv(FIXTURE, parse_dates=["datetime"])
        index = build_previous_close_index(frame)

        # Fixture: 2025-01-02 (last close 10.30) and 2025-01-03 (last close 10.35).
        self.assertIsNone(index.previous_close_for_date(date(2025, 1, 2)))
        self.assertEqual(index.previous_close_for_date(date(2025, 1, 3)), 10.30)

    def test_fixture_every_bar_on_day_two_returns_day_one_last_close(self):
        frame = pd.read_csv(FIXTURE, parse_dates=["datetime"])
        index = build_previous_close_index(frame)

        day_two_bars = frame[frame["datetime"].dt.date == date(2025, 1, 3)]
        closes = {index.previous_close(ts) for ts in day_two_bars["datetime"]}
        self.assertEqual(closes, {10.30})

    def test_fixture_input_not_mutated(self):
        frame = pd.read_csv(FIXTURE, parse_dates=["datetime"])
        original = frame.copy(deep=True)
        build_previous_close_index(frame)
        pd.testing.assert_frame_equal(frame, original)


if __name__ == "__main__":
    unittest.main()
