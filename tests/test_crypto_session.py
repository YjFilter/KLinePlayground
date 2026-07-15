from __future__ import annotations

import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pandas as pd

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

if __name__ == "__main__":
    unittest.main()
