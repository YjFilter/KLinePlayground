from __future__ import annotations

import json
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

import pandas as pd

from backend.crypto.aggregator import aggregate_bars
from backend.crypto.session import CryptoReplaySession

UTC = timezone.utc

def make_frame(start, count):
    return pd.DataFrame([{"timestamp": start + timedelta(minutes=5 * index), "open": 10 + index, "high": 12 + index, "low": 9 + index, "close": 11 + index, "volume": 1 + index, "turnover": 20 + index} for index in range(count)])

class CryptoReplaySessionTests(unittest.TestCase):
    def test_snapshot_and_period_switch_preserve_canonical_time(self):
        frame = make_frame(datetime(2024, 1, 1, 0, 0, tzinfo=UTC), 12)
        session = CryptoReplaySession(frame, initial_time=frame.iloc[2]["timestamp"], symbol="BTCUSDT", source="binance", active_period="5m")
        snapshot = session.snapshot()
        self.assertEqual(snapshot["market_type"], "crypto_perpetual")
        self.assertEqual(snapshot["data_mode"], "crypto_5m")
        self.assertEqual(snapshot["current_time"], "2024-01-01 00:10:00")
        self.assertEqual(len(snapshot["kline_data"]), 3)
        switched = session.set_period("15m")
        self.assertEqual(switched["current_time"], snapshot["current_time"])
        self.assertEqual(switched["current_base_bar"]["close"], snapshot["current_base_bar"]["close"])
        json.dumps(switched)

    def test_advance_processes_hidden_base_bars_then_commits(self):
        frame = make_frame(datetime(2024, 1, 1, 0, 0, tzinfo=UTC), 8)
        completed = []
        session = CryptoReplaySession(frame, active_period="15m", on_bar=lambda timestamp, row: completed.append(timestamp))
        result = session.advance()
        self.assertEqual(completed, [datetime(2024, 1, 1, 0, 5, tzinfo=UTC), datetime(2024, 1, 1, 0, 10, tzinfo=UTC)])
        self.assertEqual(result["current_time"], "2024-01-01 00:10:00")
        self.assertEqual(result["completed_times"], ["2024-01-01 00:05:00", "2024-01-01 00:10:00"])

    def test_advance_delta_returns_only_the_changed_five_minute_bar(self):
        frame = make_frame(datetime(2024, 1, 1, 0, 0, tzinfo=UTC), 8)
        session = CryptoReplaySession(frame, active_period="5m")

        result = session.advance_delta(max_bars=120)

        self.assertNotIn("kline_data", result)
        self.assertEqual(result["new_bar"]["time"], "2024-01-01 00:05:00")
        self.assertEqual(result["new_volume"], {"time": "2024-01-01 00:05:00", "value": 2.0})
        self.assertFalse(result["requires_full_refresh"])
        self.assertEqual(result["completed_times"], ["2024-01-01 00:05:00"])

    def test_advance_delta_does_not_build_a_full_snapshot(self):
        frame = make_frame(datetime(2024, 1, 1, 0, 0, tzinfo=UTC), 1000)
        session = CryptoReplaySession(frame, active_period="5m")

        with patch.object(session, "snapshot", side_effect=AssertionError("full snapshot is too expensive")):
            result = session.advance_delta(max_bars=120)

        self.assertEqual(result["new_bar"]["time"], "2024-01-01 00:05:00")

    def test_callback_failure_does_not_commit_and_reset_restores_state(self):
        frame = make_frame(datetime(2024, 1, 1, 0, 0, tzinfo=UTC), 5)
        session = CryptoReplaySession(frame, on_bar=lambda timestamp, row: (_ for _ in ()).throw(RuntimeError("boom")))
        with self.assertRaisesRegex(RuntimeError, "boom"):
            session.advance()
        self.assertEqual(session.snapshot()["current_time"], "2024-01-01 00:00:00")
        session = CryptoReplaySession(frame, active_period="15m")
        session.advance()
        reset = session.reset()
        self.assertEqual(reset["current_time"], "2024-01-01 00:00:00")
        self.assertEqual(reset["active_period"], "15m")

    def test_max_training_days_uses_utc_calendar_day_cutoff(self):
        frame = make_frame(datetime(2024, 1, 1, 23, 50, tzinfo=UTC), 6)
        session = CryptoReplaySession(frame, active_period="daily", max_training_days=1)
        result = session.advance()
        self.assertEqual(result["current_time"], "2024-01-01 23:55:00")
        self.assertTrue(result["finished"])
        self.assertEqual(len(result["kline_data"]), 1)

    def test_snapshot_does_not_use_dataframe_row_iteration(self):
        frame = make_frame(datetime(2024, 1, 1, 0, 0, tzinfo=UTC), 100)
        session = CryptoReplaySession(frame, initial_time=frame.iloc[-1]["timestamp"])
        with patch.object(pd.DataFrame, "iterrows", side_effect=AssertionError("row iteration is too slow")):
            snapshot = session.snapshot()
        self.assertEqual(len(snapshot["kline_data"]), 100)

    def test_initialization_normalizes_timestamps_and_numeric_values_once(self):
        frame = make_frame(datetime(2024, 1, 1, 0, 0, tzinfo=UTC), 4)
        frame["timestamp"] = frame["timestamp"].astype(str)
        for column in ("open", "high", "low", "close", "volume", "turnover"):
            frame[column] = frame[column].map(lambda value: Decimal(str(value)))

        session = CryptoReplaySession(frame)

        self.assertIsInstance(session.base_bars["timestamp"].dtype, pd.DatetimeTZDtype)
        for column in ("open", "high", "low", "close", "volume", "turnover"):
            self.assertTrue(pd.api.types.is_float_dtype(session.base_bars[column].dtype))
        with patch.object(pd, "to_datetime", side_effect=AssertionError("timestamps must not be normalized again")):
            session.snapshot()
            session.set_period("15m")

    def test_snapshot_and_aggregation_cache_reuse_by_time_and_period(self):
        frame = make_frame(datetime(2024, 1, 1, 0, 0, tzinfo=UTC), 60 * 24 * 12)
        session = CryptoReplaySession(frame)

        with patch("backend.crypto.session.aggregate_bars", wraps=aggregate_bars) as aggregate:
            first = session.snapshot()
            repeated = session.snapshot()
            session.set_period("15m")
            session.set_period("5m")

            self.assertEqual(aggregate.call_count, 2)
            self.assertEqual(repeated, first)
            self.assertIsNot(repeated, first)

            session.advance()
            self.assertEqual(aggregate.call_count, 3)

    def test_period_snapshot_can_limit_visible_bars_without_reaggregating(self):
        frame = make_frame(datetime(2024, 1, 1, 0, 0, tzinfo=UTC), 1000)
        session = CryptoReplaySession(frame, initial_time=frame.iloc[-1]["timestamp"])

        with patch("backend.crypto.session.aggregate_bars", wraps=aggregate_bars) as aggregate:
            full = session.snapshot()
            limited = session.snapshot(max_bars=120)

        self.assertEqual(len(full["kline_data"]), 1000)
        self.assertEqual(len(limited["kline_data"]), 120)
        self.assertEqual(limited["kline_data"][-1], full["kline_data"][-1])
        self.assertEqual(aggregate.call_count, 1)

    def test_period_snapshot_limit_tracks_requested_visible_range(self):
        frame = make_frame(datetime(2024, 1, 1, 0, 0, tzinfo=UTC), 1000)
        session = CryptoReplaySession(frame, initial_time=frame.iloc[-1]["timestamp"])
        visible_start = frame.iloc[200]["timestamp"].to_pydatetime()
        visible_end = frame.iloc[260]["timestamp"].to_pydatetime()

        snapshot = session.snapshot(
            max_bars=120, range_start=visible_start, range_end=visible_end
        )

        times = [item["time"] for item in snapshot["kline_data"]]
        self.assertLessEqual(len(times), 120)
        self.assertIn(visible_start.strftime("%Y-%m-%d %H:%M:%S"), times)
        self.assertIn(visible_end.strftime("%Y-%m-%d %H:%M:%S"), times)

    def test_reset_invalidates_snapshot_cache_even_at_initial_key(self):
        frame = make_frame(datetime(2024, 1, 1, 0, 0, tzinfo=UTC), 4)
        session = CryptoReplaySession(frame)

        with patch("backend.crypto.session.aggregate_bars", wraps=aggregate_bars) as aggregate:
            session.snapshot()
            session.reset()
            self.assertEqual(aggregate.call_count, 2)

if __name__ == "__main__":
    unittest.main()
