import unittest
from pathlib import Path

import pandas as pd


FIXTURE = Path(__file__).parent / "fixtures" / "intraday" / "600000_30m_sample.csv"


class IntradayValidatorTests(unittest.TestCase):
    def load_frame(self):
        frame = pd.read_csv(FIXTURE, parse_dates=["datetime"])
        return frame

    def issue_codes(self, frame):
        from backend.intraday.validator import validate_30m_frame

        return [issue.code for issue in validate_30m_frame(frame).issues]

    def test_complete_fixture_is_valid(self):
        self.assertEqual(self.issue_codes(self.load_frame()), [])

    def test_duplicate_timestamp_is_reported(self):
        frame = pd.concat([self.load_frame(), self.load_frame().iloc[[0]]], ignore_index=True)
        self.assertIn("duplicate_timestamp", self.issue_codes(frame))

    def test_invalid_ohlc_is_reported(self):
        frame = self.load_frame()
        frame.loc[0, "high"] = frame.loc[0, "close"] - 1
        self.assertIn("invalid_ohlc", self.issue_codes(frame))

    def test_negative_volume_is_reported(self):
        frame = self.load_frame()
        frame.loc[0, "volume"] = -1
        self.assertIn("negative_volume", self.issue_codes(frame))

    def test_illegal_session_time_is_reported(self):
        frame = self.load_frame()
        frame.loc[0, "datetime"] = pd.Timestamp("2025-01-02 12:00:00")
        self.assertIn("illegal_session_time", self.issue_codes(frame))

    def test_incomplete_day_is_reported(self):
        frame = self.load_frame().iloc[:-1].copy()
        self.assertIn("incomplete_trading_day", self.issue_codes(frame))


if __name__ == "__main__":
    unittest.main()
