from __future__ import annotations

import unittest

from backend.crypto.persistence import build_crypto_futures_report


class CryptoFuturesReportTests(unittest.TestCase):
    def test_report_contains_required_performance_fee_funding_and_liquidation_metrics(self):
        report = build_crypto_futures_report(
            initial_equity=1000,
            final_equity=800,
            unrealized_pnl=-20,
            fills=[
                {"action": "open_long", "realized_pnl": 0, "fee": 5, "fee_type": "taker"},
                {"action": "close", "realized_pnl": 100, "fee": 2, "fee_type": "maker"},
                {"action": "liquidation", "realized_pnl": -50, "fee": 3, "fee_type": "liquidation"},
            ],
            orders=[{"order_id": "1"}, {"order_id": "2"}, {"order_id": "3"}],
            funding_events=[{"transfer": -10}, {"transfer": 4}],
            liquidation_events=[{"fee": 3}],
            equity_snapshots=[{"equity": 1000}, {"equity": 900}, {"equity": 1100}, {"equity": 800}],
            leverage=5,
            source="binance",
            symbol="BTCUSDT",
            display_period="1h",
        )
        self.assertEqual(report["initial_equity"], 1000.0)
        self.assertEqual(report["final_equity"], 800.0)
        self.assertEqual(report["realized_pnl"], 50.0)
        self.assertEqual(report["unrealized_pnl"], -20.0)
        self.assertEqual(report["total_return"], -20.0)
        self.assertAlmostEqual(report["max_drawdown"], 27.2727272727)
        self.assertEqual(report["maker_fees"], 2.0)
        self.assertEqual(report["taker_fees"], 5.0)
        self.assertEqual(report["liquidation_fees"], 3.0)
        self.assertEqual(report["total_fees"], 10.0)
        self.assertEqual(report["funding_paid"], 10.0)
        self.assertEqual(report["funding_received"], 4.0)
        self.assertEqual(report["liquidation_count"], 1)
        self.assertEqual(report["order_count"], 3)
        self.assertEqual(report["fill_count"], 3)
        self.assertEqual(report["win_rate"], 50.0)
        self.assertEqual(report["leverage"], 5)
        self.assertEqual(report["source"], "binance")
        self.assertEqual(report["symbol"], "BTCUSDT")
        self.assertEqual(report["display_period"], "1h")

    def test_reversal_close_fill_counts_toward_win_rate(self):
        report = build_crypto_futures_report(
            initial_equity="1000",
            final_equity="1050",
            fills=[
                {"action": "close", "realized_pnl": "50", "fee": "1", "fee_type": "taker"},
                {"action": "open_short", "realized_pnl": "0", "fee": "1", "fee_type": "taker"},
            ],
        )
        self.assertEqual(report["win_rate"], 100.0)


if __name__ == "__main__":
    unittest.main()
