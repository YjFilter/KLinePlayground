"""Tests for crypto offline data manager backend and API."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from backend.app_enhanced import app
from backend.crypto.data_manager import (
    scan_crypto_offline_status,
    _get_target_months,
    sync_crypto_offline_data,
)


class CryptoOfflineDataManagerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = app.test_client()

    def test_get_target_months_helper(self):
        months_2024 = _get_target_months("2024")
        self.assertEqual(len(months_2024), 12)
        self.assertEqual(months_2024[0], "2024-01")
        self.assertEqual(months_2024[-1], "2024-12")

        months_2026 = _get_target_months("2026")
        self.assertEqual(len(months_2026), 8)
        self.assertEqual(months_2026[-1], "2026-08")

        months_all = _get_target_months("all")
        self.assertEqual(len(months_all), 32)
        self.assertEqual(months_all[0], "2024-01")
        self.assertEqual(months_all[-1], "2026-08")

    def test_scan_crypto_offline_status_returns_valid_structure(self):
        res = scan_crypto_offline_status()
        self.assertIn("total_symbols", res)
        self.assertIn("total_size_mb", res)
        self.assertIn("symbols", res)
        self.assertGreaterEqual(res["total_symbols"], 1)

        # BTCUSDT (binance) should be in the list
        btc = next((s for s in res["symbols"] if s["symbol"] == "BTCUSDT" and s["source"] == "binance"), None)
        self.assertIsNotNone(btc)
        self.assertEqual(btc["source"], "binance")
        self.assertGreaterEqual(btc["trade_count"], 32)
        self.assertGreaterEqual(btc["mark_count"], 32)
        self.assertGreaterEqual(btc["funding_count"], 32)
        self.assertTrue(btc["is_complete_2024_now"])

    def test_api_offline_status_route(self):
        response = self.client.get("/api/crypto/data/offline_status")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("total_symbols", data)
        self.assertIn("symbols", data)
        self.assertIsInstance(data["symbols"], list)

    def test_api_download_route_validation(self):
        # Missing symbol
        response = self.client.post("/api/crypto/data/download", json={})
        self.assertEqual(response.status_code, 400)
        self.assertIn("symbol", response.get_json()["error"])

    def test_sync_crypto_offline_data_already_cached(self):
        # Test syncing BTCUSDT 2024 when already cached (should report already_cached without download)
        result = sync_crypto_offline_data(symbol="BTCUSDT", year="2024", kinds=("trade",))
        self.assertEqual(result["symbol"], "BTCUSDT")
        self.assertEqual(result["year"], "2024")
        self.assertEqual(result["already_cached"], 12)
        self.assertEqual(result["failed"], 0)


if __name__ == "__main__":
    unittest.main()
