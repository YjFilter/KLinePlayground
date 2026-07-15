from __future__ import annotations

import gzip
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from backend.crypto.cache import CryptoCacheCorruption, CryptoMonthlyCache
from backend.crypto.models import CryptoInstrument, FundingEvent
from backend.crypto.validator import validate_crypto_frame

UTC = timezone.utc
COLUMNS = ["timestamp", "open", "high", "low", "close", "volume", "turnover"]

def frame(times):
    return pd.DataFrame([
        {"timestamp": value, "open": Decimal("10.0"), "high": Decimal("12.0"), "low": Decimal("9.0"), "close": Decimal("11.0"), "volume": Decimal("2.5"), "turnover": Decimal("27.5")}
        for value in times
    ], columns=COLUMNS)

class CryptoValidationTests(unittest.TestCase):
    def test_reports_required_columns_alignment_order_duplicates_and_ohlc(self):
        invalid = pd.DataFrame([
            {"timestamp": datetime(2024, 1, 1, 0, 7, tzinfo=UTC), "open": 10, "high": 8, "low": 11, "close": float("nan"), "volume": -1},
            {"timestamp": datetime(2024, 1, 1, 0, 7, tzinfo=UTC), "open": 10, "high": 12, "low": 9, "close": 11, "volume": 1},
        ])
        codes = {issue.code for issue in validate_crypto_frame(invalid, kind="trade").issues}
        self.assertTrue({"missing_columns", "misaligned_timestamp", "duplicate_timestamp", "invalid_ohlc", "non_finite", "negative_volume"} <= codes)

    def test_accepts_ordered_five_minute_utc_frame(self):
        valid = frame([datetime(2024, 1, 1, 0, 0, tzinfo=UTC), datetime(2024, 1, 1, 0, 5, tzinfo=UTC)])
        self.assertTrue(validate_crypto_frame(valid, kind="trade").is_valid)

    def test_rejects_non_utc_aware_timestamps(self):
        non_utc = frame([datetime(2024, 1, 1, 8, 0, tzinfo=timezone(timedelta(hours=8)))])
        self.assertIn("non_utc_timestamp", {issue.code for issue in validate_crypto_frame(non_utc, kind="trade").issues})

    def test_validation_does_not_iterate_rows(self):
        valid = frame([datetime(2024, 1, 1, 0, 0, tzinfo=UTC), datetime(2024, 1, 1, 0, 5, tzinfo=UTC)])
        with patch.object(pd.DataFrame, "iterrows", side_effect=AssertionError("row iteration is too slow")):
            self.assertTrue(validate_crypto_frame(valid, kind="trade").is_valid)

class CryptoMonthlyCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.cache = CryptoMonthlyCache(Path(self.temp.name))

    def tearDown(self):
        self.temp.cleanup()

    def test_save_segments_months_compresses_and_writes_metadata(self):
        data = frame([datetime(2024, 1, 31, 23, 55, tzinfo=UTC), datetime(2024, 2, 1, 0, 0, tzinfo=UTC)])
        self.cache.save("binance", "BTCUSDT", "trade", data)
        january = Path(self.temp.name) / "binance" / "BTCUSDT" / "trade" / "2024-01.csv.gz"
        february = january.with_name("2024-02.csv.gz")
        self.assertTrue(january.exists() and february.exists())
        with gzip.open(january, "rt", encoding="utf-8") as handle:
            self.assertIn("2024-01-31T23:55:00+00:00", handle.read())
        metadata = json.loads(january.with_name("2024-01.json").read_text(encoding="utf-8"))
        self.assertEqual(metadata["source"], "binance")
        self.assertEqual(metadata["rows"], 1)
        self.assertFalse(list(january.parent.glob("*.tmp")))

    def test_merge_load_coverage_source_isolation_and_missing_ranges(self):
        first = frame([datetime(2024, 1, 1, 0, 0, tzinfo=UTC), datetime(2024, 1, 1, 0, 5, tzinfo=UTC)])
        newer = frame([datetime(2024, 1, 1, 0, 5, tzinfo=UTC), datetime(2024, 1, 1, 0, 10, tzinfo=UTC)])
        newer.loc[0, "close"] = Decimal("11.5")
        self.cache.save("binance", "BTCUSDT", "trade", first)
        self.cache.save("binance", "BTCUSDT", "trade", newer)
        loaded = self.cache.load("binance", "BTCUSDT", "trade")
        self.assertEqual(len(loaded), 3)
        self.assertEqual(loaded.iloc[1]["close"], Decimal("11.5"))
        self.assertTrue(self.cache.coverage("binance", "BTCUSDT", "trade").covers(datetime(2024, 1, 1, 0, 0, tzinfo=UTC), datetime(2024, 1, 1, 0, 10, tzinfo=UTC)))
        self.assertTrue(self.cache.load("bybit", "BTCUSDT", "trade").empty)
        gaps = self.cache.missing_ranges("binance", "BTCUSDT", "trade", datetime(2023, 12, 31, 23, 55, tzinfo=UTC), datetime(2024, 1, 1, 0, 15, tzinfo=UTC))
        self.assertEqual(gaps, [(datetime(2023, 12, 31, 23, 55, tzinfo=UTC), datetime(2023, 12, 31, 23, 55, tzinfo=UTC)), (datetime(2024, 1, 1, 0, 15, tzinfo=UTC), datetime(2024, 1, 1, 0, 15, tzinfo=UTC))])

    def test_coverage_uses_month_metadata_without_loading_candles(self):
        data = frame([datetime(2024, 1, 1, 0, 0, tzinfo=UTC), datetime(2024, 2, 1, 0, 0, tzinfo=UTC)])
        self.cache.save("binance", "BTCUSDT", "trade", data)
        with patch.object(self.cache, "load", side_effect=AssertionError("coverage must not load candle CSVs")):
            coverage = self.cache.coverage("binance", "BTCUSDT", "trade")
        self.assertEqual(coverage.start, datetime(2024, 1, 1, 0, 0, tzinfo=UTC))
        self.assertEqual(coverage.end, datetime(2024, 2, 1, 0, 0, tzinfo=UTC))

    def test_corrupt_month_raises_actionable_error(self):
        path = Path(self.temp.name) / "binance" / "BTCUSDT" / "trade" / "2024-01.csv.gz"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"not-gzip")
        with self.assertRaisesRegex(CryptoCacheCorruption, "BTCUSDT.*2024-01"):
            self.cache.load("binance", "BTCUSDT", "trade")

    def test_persists_instrument_and_monthly_funding_for_restart(self):
        instrument = CryptoInstrument("BTCUSDT", "binance", "BTC", "USDT", "PERPETUAL", "TRADING", datetime(2020, 1, 1, tzinfo=UTC), Decimal("0.1"), Decimal("0.001"), Decimal("0.001"), Decimal("5"), Decimal("100"))
        events = [
            FundingEvent("binance", "BTCUSDT", datetime(2024, 1, 31, 16, 0, tzinfo=UTC), Decimal("0.001"), Decimal("10")),
            FundingEvent("binance", "BTCUSDT", datetime(2024, 2, 1, 0, 0, tzinfo=UTC), Decimal("-0.002"), Decimal("11")),
        ]
        self.cache.save_instrument(instrument)
        self.cache.save_funding("binance", "BTCUSDT", events, datetime(2024, 1, 31, 0, 0, tzinfo=UTC), datetime(2024, 2, 1, 23, 55, tzinfo=UTC))
        restarted = CryptoMonthlyCache(Path(self.temp.name))
        self.assertEqual(restarted.load_instrument("binance", "BTCUSDT"), instrument)
        self.assertEqual(restarted.load_funding("binance", "BTCUSDT"), events)
        self.assertTrue(restarted.funding_covers("binance", "BTCUSDT", datetime(2024, 1, 31, 0, 0, tzinfo=UTC), datetime(2024, 2, 1, 23, 55, tzinfo=UTC)))
        self.assertTrue((Path(self.temp.name) / "binance" / "BTCUSDT" / "funding" / "2024-01.csv.gz").exists())
        self.assertTrue((Path(self.temp.name) / "binance" / "BTCUSDT" / "funding" / "2024-02.csv.gz").exists())

if __name__ == "__main__":
    unittest.main()
