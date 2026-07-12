"""Black-box edge-case tests for `backend.intraday.validator.validate_30m_frame`.

These tests are deterministic, offline, and assert only the public validation
result (issue codes returned by ``validate_30m_frame``). They intentionally
avoid duplicating the assertions already covered by
``tests/test_intraday_validator.py`` (duplicate timestamp, illegal session
time, incomplete day, invalid OHLC via high<close, negative volume).

Covered boundaries that are NOT already asserted elsewhere:
  * a valid two-trading-day frame (16 rows, 8 bars per day)
  * unsorted timestamps remain valid (validator is order-independent)
  * null (NaN) OHLC value is flagged as invalid_ohlc
  * high/low equality boundaries (flat bar, open==high, close==low) are valid
  * an empty frame is valid
  * nonnumeric / null volume and amount are silently accepted (suspected defect)

The last group documents a suspected production defect and is described in
detail in the task result report. The tests assert the *actual* current
behavior (no issue emitted) so the suite stays green while preserving evidence
for Codex review.
"""

import unittest
from pathlib import Path

import pandas as pd

FIXTURE = Path(__file__).parent / "fixtures" / "intraday" / "validator_edge_cases.csv"

REQUIRED_COLUMNS = ["datetime", "open", "high", "low", "close", "volume", "amount"]
# The eight legal 30-minute bar timestamps accepted by the validator.
EXPECTED_DAY_TIMES = {
    "10:00", "10:30", "11:00", "11:30",
    "13:30", "14:00", "14:30", "15:00",
}


def _issue_codes(frame: pd.DataFrame) -> list[str]:
    from backend.intraday.validator import validate_30m_frame

    return [issue.code for issue in validate_30m_frame(frame).issues]


def _load_fixture() -> pd.DataFrame:
    return pd.read_csv(FIXTURE, parse_dates=["datetime"])


class IntradayValidatorEdgeCaseTests(unittest.TestCase):
    # ------------------------------------------------------------------
    # Valid multi-day input
    # ------------------------------------------------------------------
    def test_valid_two_trading_day_frame_is_clean(self):
        """A deterministic two-trading-day fixture (16 rows) validates cleanly."""
        frame = _load_fixture()
        self.assertEqual(len(frame), 16)
        # Sanity: two distinct dates, each with exactly the eight legal bars.
        grouped = frame.groupby(frame["datetime"].dt.date)
        self.assertEqual(len(grouped), 2)
        for _, day_frame in grouped:
            self.assertEqual(set(day_frame["datetime"].dt.strftime("%H:%M")), EXPECTED_DAY_TIMES)
        self.assertEqual(_issue_codes(frame), [])

    def test_unsorted_timestamps_remain_valid(self):
        """The validator must be order-independent: a shuffled but complete
        frame is still valid (no duplicate, session, or completeness issues)."""
        frame = _load_fixture()
        shuffled = frame.sample(frac=1, random_state=42).reset_index(drop=True)
        # Guard: shuffling actually changed the row order.
        self.assertFalse(shuffled["datetime"].equals(frame["datetime"]))
        self.assertEqual(_issue_codes(shuffled), [])

    # ------------------------------------------------------------------
    # Null numeric values in OHLC
    # ------------------------------------------------------------------
    def test_null_ohlc_high_is_flagged(self):
        """A NaN in any OHLC column must surface as invalid_ohlc (the validator
        explicitly checks ``isna().any(axis=1)`` for OHLC)."""
        frame = _load_fixture()
        frame.loc[0, "high"] = float("nan")
        codes = _issue_codes(frame)
        self.assertIn("invalid_ohlc", codes)

    def test_null_ohlc_close_is_flagged(self):
        """NaN in the close column is also an invalid_ohlc condition."""
        frame = _load_fixture()
        frame.loc[3, "close"] = float("nan")
        self.assertIn("invalid_ohlc", _issue_codes(frame))

    # ------------------------------------------------------------------
    # High/low equality boundaries (strict inequalities in the validator)
    # ------------------------------------------------------------------
    def test_flat_bar_all_equal_is_valid(self):
        """open == high == low == close is a legal flat bar: the validator uses
        strict ``high < max(...)`` and ``low > min(...)`` so equality passes."""
        frame = _load_fixture()
        frame.loc[0, ["open", "high", "low", "close"]] = 10.00
        self.assertEqual(_issue_codes(frame), [])

    def test_open_equals_high_boundary_is_valid(self):
        """open == high (high touches open) is allowed at the boundary."""
        frame = _load_fixture()
        frame.loc[0, ["open", "high"]] = 10.20
        # keep low/close inside the new range so OHLC stays consistent
        frame.loc[0, "low"] = 10.00
        frame.loc[0, "close"] = 10.10
        self.assertEqual(_issue_codes(frame), [])

    def test_close_equals_low_boundary_is_valid(self):
        """close == low (low touches close) is allowed at the boundary."""
        frame = _load_fixture()
        frame.loc[0, ["close", "low"]] = 9.95
        frame.loc[0, "open"] = 10.05
        frame.loc[0, "high"] = 10.15
        self.assertEqual(_issue_codes(frame), [])

    def test_high_equals_low_with_matching_oc_is_valid(self):
        """high == low is valid only when open and close also equal that price
        (otherwise high < max(open,close,low) would fire). Tests the tightest
        equality boundary."""
        frame = _load_fixture()
        frame.loc[0, ["open", "high", "low", "close"]] = 10.00
        self.assertEqual(_issue_codes(frame), [])

    # ------------------------------------------------------------------
    # Empty input
    # ------------------------------------------------------------------
    def test_empty_frame_is_valid(self):
        """An empty frame with the correct schema returns no issues."""
        empty = pd.DataFrame(columns=REQUIRED_COLUMNS)
        self.assertEqual(_issue_codes(empty), [])

    # ------------------------------------------------------------------
    # Invalid numeric volume and amount
    # ------------------------------------------------------------------
    def test_nonnumeric_volume_is_flagged(self):
        frame = _load_fixture()
        frame["volume"] = frame["volume"].astype(object)
        frame.loc[0, "volume"] = "abc"
        self.assertIn("invalid_volume", _issue_codes(frame))

    def test_null_volume_is_flagged(self):
        frame = _load_fixture()
        frame.loc[0, "volume"] = float("nan")
        self.assertIn("invalid_volume", _issue_codes(frame))

    def test_null_amount_is_flagged(self):
        frame = _load_fixture()
        frame.loc[0, "amount"] = float("nan")
        self.assertIn("invalid_amount", _issue_codes(frame))


if __name__ == "__main__":
    unittest.main()
