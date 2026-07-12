import subprocess
import sys
import unittest
from pathlib import Path
from datetime import datetime
from types import SimpleNamespace


class FakeResult:
    def __init__(self, rows=None, error_code="0", error_msg="success"):
        self.rows = list(rows or [])
        self.error_code = error_code
        self.error_msg = error_msg
        self.fields = [
            "date", "time", "code", "open", "high", "low", "close",
            "volume", "amount", "adjustflag",
        ]
        self.index = -1

    def next(self):
        self.index += 1
        return self.index < len(self.rows)

    def get_row_data(self):
        return self.rows[self.index]


class FakeBaoStock:
    def __init__(self, *, login_code="0", query_code="0", rows=None):
        self.login_result = SimpleNamespace(error_code=login_code, error_msg="login message")
        self.query_result = FakeResult(rows=rows, error_code=query_code, error_msg="query message")
        self.query_calls = []
        self.logout_calls = 0

    def login(self):
        return self.login_result

    def logout(self):
        self.logout_calls += 1

    def query_history_k_data_plus(self, *args, **kwargs):
        self.query_calls.append((args, kwargs))
        return self.query_result


class LiveScriptEntryTests(unittest.TestCase):
    def test_live_verification_script_help_runs_from_repository_root(self):
        repo_root = Path(__file__).resolve().parents[1]
        completed = subprocess.run(
            [sys.executable, "scripts/verify_baostock_30m.py", "--help"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)

class IntradayModelTests(unittest.TestCase):
    def test_intraday_range_reports_coverage(self):
        from backend.intraday.models import IntradayRange

        coverage = IntradayRange(
            start=datetime(2021, 7, 12, 10, 0),
            end=datetime(2026, 7, 10, 15, 0),
        )

        self.assertTrue(coverage.covers(datetime(2022, 1, 1), datetime(2025, 1, 1)))
        self.assertFalse(coverage.covers(datetime(2020, 1, 1), datetime(2025, 1, 1)))


class BaoStockSourceTests(unittest.TestCase):
    def test_fetch_30m_normalizes_symbol_timestamp_and_numeric_fields(self):
        from backend.intraday.baostock_source import BaoStockSource

        api = FakeBaoStock(rows=[["2025-01-02", "20250102100000000", "sh.600000", "10.00", "10.20", "9.95", "10.10", "10000", "101000.00", "3"]])

        frame = BaoStockSource(api=api).fetch_30m(
            "600000", datetime(2025, 1, 2), datetime(2025, 1, 3)
        )

        self.assertEqual(list(frame.columns), ["datetime", "open", "high", "low", "close", "volume", "amount"])
        self.assertEqual(frame.iloc[0]["datetime"], datetime(2025, 1, 2, 10, 0))
        self.assertEqual(frame.iloc[0]["close"], 10.10)
        self.assertEqual(api.query_calls[0][0][0], "sh.600000")
        self.assertEqual(api.query_calls[0][1]["frequency"], "30")
        self.assertEqual(api.logout_calls, 1)

    def test_fetch_30m_rejects_beijing_exchange_codes_explicitly(self):
        from backend.intraday.baostock_source import BaoStockSource, IntradaySourceError

        api = FakeBaoStock()
        with self.assertRaisesRegex(IntradaySourceError, "Beijing Stock Exchange"):
            BaoStockSource(api=api).fetch_30m(
                "430047", datetime(2025, 1, 2), datetime(2025, 1, 3)
            )

        self.assertEqual(api.query_calls, [])

    def test_fetch_30m_raises_when_login_fails(self):
        from backend.intraday.baostock_source import BaoStockSource, IntradaySourceError

        api = FakeBaoStock(login_code="1001")

        with self.assertRaisesRegex(IntradaySourceError, "login message"):
            BaoStockSource(api=api).fetch_30m("600000", datetime(2025, 1, 2), datetime(2025, 1, 3))

        self.assertEqual(api.query_calls, [])
        self.assertEqual(api.logout_calls, 0)

    def test_fetch_30m_raises_when_query_fails(self):
        from backend.intraday.baostock_source import BaoStockSource, IntradaySourceError

        api = FakeBaoStock(query_code="1002")

        with self.assertRaisesRegex(IntradaySourceError, "query message"):
            BaoStockSource(api=api).fetch_30m("600000", datetime(2025, 1, 2), datetime(2025, 1, 3))

        self.assertEqual(api.logout_calls, 1)

    def test_fetch_30m_returns_empty_normalized_frame_for_no_rows(self):
        from backend.intraday.baostock_source import BaoStockSource

        frame = BaoStockSource(api=FakeBaoStock()).fetch_30m(
            "300750", datetime(2025, 1, 2), datetime(2025, 1, 3)
        )

        self.assertTrue(frame.empty)
        self.assertEqual(list(frame.columns), ["datetime", "open", "high", "low", "close", "volume", "amount"])


if __name__ == "__main__":
    unittest.main()


