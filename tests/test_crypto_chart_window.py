from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pandas as pd

from backend.crypto.chart_window import CryptoChartWindowService
from backend.crypto.models import CryptoRange

UTC = timezone.utc
START = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)

def frame(count=12):
    return pd.DataFrame([{"timestamp": START + timedelta(minutes=5 * index), "open": 10 + index, "high": 12 + index, "low": 9 + index, "close": 11 + index, "volume": index + 1, "turnover": index + 10, "source": "binance", "symbol": "BTCUSDT", "kind": "trade"} for index in range(count)])

class Cache:
    def coverage(self, source, symbol, kind):
        return CryptoRange(START - timedelta(days=1), START + timedelta(days=1))

class Service:
    def __init__(self):
        self.cache = Cache()
        self.calls = []
    def get_bundle(self, symbol, start, end, *, source=None):
        self.calls.append((symbol, start, end, source))
        visible = frame().loc[(frame()["timestamp"] >= pd.Timestamp(start)) & (frame()["timestamp"] <= pd.Timestamp(end))].reset_index(drop=True)
        return SimpleNamespace(source=source or "binance", trade_bars=visible)

class CryptoChartWindowTests(unittest.TestCase):
    def test_non_aligned_ranges_fetch_from_containing_period_bucket(self):
        cases = {
            "15m": START,
            "30m": START,
            "1h": START,
            "4h": START,
            "daily": START,
            "weekly": START,
        }
        requested = START + timedelta(minutes=7)
        for period, expected_start in cases.items():
            with self.subTest(period=period):
                service = Service()
                result = CryptoChartWindowService(service).load(symbol="BTCUSDT", source="binance", period=period, range_start=requested, range_end=START + timedelta(minutes=40), current_time=START + timedelta(minutes=40), read_only=False)
                self.assertEqual(service.calls[0][1], expected_start)
                self.assertTrue(all(item["end_time"] >= "2024-01-01 00:07:00" for item in result.kline_data))

    def test_active_window_caps_at_current_time_and_pins_source(self):
        service = Service()
        result = CryptoChartWindowService(service).load(symbol="BTCUSDT", source="binance", period="15m", range_start=START, range_end=START + timedelta(minutes=55), current_time=START + timedelta(minutes=20), read_only=False)
        self.assertEqual(result.window_end, START + timedelta(minutes=20))
        self.assertEqual(service.calls[0][-1], "binance")
        self.assertTrue(all(item["end_time"] <= "2024-01-01 00:20:00" for item in result.kline_data))
        self.assertFalse(result.has_later)
        self.assertEqual(result.volume_data[-1]["time"], result.kline_data[-1]["end_time"])

    def test_completed_window_can_read_later_history_and_reports_coverage(self):
        service = Service()
        result = CryptoChartWindowService(service).load(symbol="BTCUSDT", source="binance", period="5m", range_start=START, range_end=START + timedelta(minutes=40), current_time=START + timedelta(minutes=20), read_only=True)
        payload = result.to_dict()
        self.assertEqual(result.window_end, START + timedelta(minutes=40))
        self.assertTrue(result.has_earlier)
        self.assertTrue(result.has_later)
        self.assertTrue(result.read_only)
        self.assertEqual(payload["source"], "binance")
        self.assertEqual(len(payload["kline_data"]), 9)

if __name__ == "__main__":
    unittest.main()
