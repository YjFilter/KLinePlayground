from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

import pandas as pd

from backend.crypto.session import CryptoReplaySession

UTC = timezone.utc

class CryptoNoFutureLeakageTests(unittest.TestCase):
    def test_future_ohlcv_mutations_do_not_change_any_period_snapshot(self):
        start = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
        frame = pd.DataFrame([{"timestamp": start + timedelta(minutes=5 * index), "open": 100 + index, "high": 102 + index, "low": 99 + index, "close": 101 + index, "volume": index + 1, "turnover": index + 10} for index in range(40)])
        current = start + timedelta(minutes=40)
        changed = frame.copy()
        future = changed["timestamp"] > current
        changed.loc[future, ["open", "high", "low", "close", "volume", "turnover"]] = [1, 999999, -999999, 777777, 888888, 999999]
        for period in ("5m", "15m", "30m", "1h", "4h", "daily", "weekly"):
            with self.subTest(period=period):
                expected = CryptoReplaySession(frame, initial_time=current, active_period=period).snapshot()
                actual = CryptoReplaySession(changed, initial_time=current, active_period=period).snapshot()
                self.assertEqual(actual["kline_data"], expected["kline_data"])
                self.assertEqual(actual["current_base_bar"], expected["current_base_bar"])

if __name__ == "__main__":
    unittest.main()
