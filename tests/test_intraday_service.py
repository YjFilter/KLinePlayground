import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import pandas as pd


TIMES = ["10:00", "10:30", "11:00", "11:30", "13:30", "14:00", "14:30", "15:00"]


def make_day(date_text, base=10.0):
    rows = []
    for index, time_text in enumerate(TIMES):
        price = base + index * 0.01
        rows.append({
            "datetime": pd.Timestamp(f"{date_text} {time_text}"),
            "open": price,
            "high": price + 0.10,
            "low": price - 0.10,
            "close": price + 0.02,
            "volume": 1000.0 + index,
            "amount": 10000.0 + index,
        })
    return pd.DataFrame(rows)


class FakeSource:
    def __init__(self, frame=None, error=None):
        self.frame = frame
        self.error = error
        self.calls = []

    def fetch_30m(self, stock_code, start, end):
        self.calls.append((stock_code, start, end))
        if self.error:
            raise self.error
        return self.frame.copy()


class IntradayDataServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        from backend.intraday.cache import IntradayCache

        self.cache = IntradayCache(Path(self.temp_dir.name))

    def save(self, frame):
        from backend.intraday.models import ValidationResult

        self.cache.save("600000", frame, source="fixture", validation=ValidationResult())

    def service(self, source):
        from backend.intraday.service import IntradayDataService

        return IntradayDataService(source, self.cache)

    def test_covered_cache_avoids_network(self):
        self.save(make_day("2025-01-02"))
        source = FakeSource(error=RuntimeError("network should not be used"))

        frame = self.service(source).get_30m("600000", datetime(2025, 1, 2, 10), datetime(2025, 1, 2, 15))

        self.assertEqual(len(frame), 8)
        self.assertEqual(source.calls, [])

    def test_missing_cache_downloads_validates_saves_and_returns_slice(self):
        source = FakeSource(frame=make_day("2025-01-02"))

        frame = self.service(source).get_30m("600000", datetime(2025, 1, 2, 10), datetime(2025, 1, 2, 15))

        self.assertEqual(len(frame), 8)
        self.assertEqual(len(source.calls), 1)
        self.assertEqual(len(self.cache.load("600000")), 8)

    def test_partial_cache_fetches_only_missing_leading_range(self):
        self.save(make_day("2025-01-03", base=11.0))
        source = FakeSource(frame=make_day("2025-01-02"))

        frame = self.service(source).get_30m("600000", datetime(2025, 1, 2, 10), datetime(2025, 1, 3, 15))

        self.assertEqual(len(frame), 16)
        self.assertEqual(source.calls[0][1], datetime(2025, 1, 2, 10))
        self.assertEqual(source.calls[0][2], datetime(2025, 1, 3, 9, 30))

    def test_same_day_midnight_request_uses_cache_starting_at_first_bar(self):
        self.save(make_day("2025-01-02"))
        source = FakeSource(error=RuntimeError("network should not be used"))

        frame = self.service(source).get_30m(
            "600000",
            datetime(2025, 1, 2),
            datetime(2025, 1, 2, 15),
        )

        self.assertEqual(len(frame), 8)
        self.assertEqual(source.calls, [])

    def test_stale_cache_returns_latest_available_when_source_has_no_new_bars(self):
        self.save(make_day("2025-01-02"))
        source = FakeSource(frame=pd.DataFrame(columns=make_day("2025-01-02").columns))

        frame = self.service(source).get_30m(
            "600000",
            datetime(2025, 1, 2),
            datetime(2025, 1, 5, 15),
        )

        self.assertEqual(len(frame), 8)
        self.assertEqual(len(source.calls), 1)

    def test_network_failure_returns_latest_partial_cache(self):
        self.save(make_day("2025-01-02"))
        source = FakeSource(error=RuntimeError("offline"))

        frame = self.service(source).get_30m(
            "600000",
            datetime(2025, 1, 2),
            datetime(2025, 1, 5, 15),
        )

        self.assertEqual(len(frame), 8)
    def test_invalid_download_is_not_saved(self):
        from backend.intraday.service import IntradayDataUnavailable

        source = FakeSource(frame=make_day("2025-01-02").iloc[:-1])

        with self.assertRaisesRegex(IntradayDataUnavailable, "validation"):
            self.service(source).get_30m("600000", datetime(2025, 1, 2, 10), datetime(2025, 1, 2, 15))

        self.assertTrue(self.cache.load("600000").empty)

    def test_network_failure_uses_covered_cache(self):
        self.save(make_day("2025-01-02"))
        source = FakeSource(error=RuntimeError("offline"))

        frame = self.service(source).get_30m("600000", datetime(2025, 1, 2, 10), datetime(2025, 1, 2, 15))

        self.assertEqual(len(frame), 8)

    def test_network_failure_raises_for_insufficient_cache(self):
        from backend.intraday.service import IntradayDataUnavailable

        source = FakeSource(error=RuntimeError("offline"))

        with self.assertRaisesRegex(IntradayDataUnavailable, "600000.*2025-01-02"):
            self.service(source).get_30m("600000", datetime(2025, 1, 2, 10), datetime(2025, 1, 2, 15))


if __name__ == "__main__":
    unittest.main()
