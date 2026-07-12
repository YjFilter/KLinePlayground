import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd


class IntradayCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        from backend.intraday.cache import IntradayCache

        self.cache = IntradayCache(Path(self.temp_dir.name))
        self.frame = pd.DataFrame(
            [
                {"datetime": pd.Timestamp("2025-01-02 10:00"), "open": 10.0, "high": 10.2, "low": 9.9, "close": 10.1, "volume": 1000.0, "amount": 10100.0},
                {"datetime": pd.Timestamp("2025-01-02 10:30"), "open": 10.1, "high": 10.3, "low": 10.0, "close": 10.2, "volume": 1100.0, "amount": 11220.0},
            ]
        )

    def valid_result(self):
        from backend.intraday.models import ValidationResult

        return ValidationResult()

    def test_save_and_load_round_trip(self):
        self.cache.save("600000", self.frame, source="baostock", validation=self.valid_result())
        loaded = self.cache.load("600000")
        pd.testing.assert_frame_equal(loaded, self.frame, check_dtype=False)

    def test_merge_replaces_duplicate_and_sorts(self):
        incoming = self.frame.iloc[[0]].copy()
        incoming.loc[incoming.index[0], "close"] = 99.0
        incoming.loc[incoming.index[0], "datetime"] = pd.Timestamp("2025-01-02 10:00")
        merged = self.cache.merge(self.frame.iloc[::-1], incoming)
        self.assertEqual(list(merged["datetime"]), sorted(merged["datetime"]))
        self.assertEqual(merged.loc[merged["datetime"] == pd.Timestamp("2025-01-02 10:00"), "close"].iloc[0], 99.0)

    def test_coverage_uses_first_and_last_timestamp(self):
        self.cache.save("600000", self.frame, source="baostock", validation=self.valid_result())
        coverage = self.cache.coverage("600000")
        self.assertEqual(coverage.start, pd.Timestamp("2025-01-02 10:00").to_pydatetime())
        self.assertEqual(coverage.end, pd.Timestamp("2025-01-02 10:30").to_pydatetime())

    def test_metadata_records_source_rows_and_issues(self):
        from backend.intraday.models import ValidationIssue, ValidationResult

        result = ValidationResult([ValidationIssue("example", "message")])
        self.cache.save("600000", self.frame, source="baostock", validation=result)
        metadata = self.cache.metadata("600000")
        self.assertEqual(metadata["source"], "baostock")
        self.assertEqual(metadata["rows"], 2)
        self.assertEqual(metadata["validation"]["example"], 1)
        self.assertEqual(metadata["range_start"], "2025-01-02T10:00:00")

    def test_missing_stock_returns_empty_frame(self):
        loaded = self.cache.load("999999")
        self.assertTrue(loaded.empty)
        self.assertIsNone(self.cache.coverage("999999"))
        self.assertIsNone(self.cache.metadata("999999"))


if __name__ == "__main__":
    unittest.main()
