from __future__ import annotations
import unittest
from backend.app_enhanced import app
from backend.services.ashare_live_service import get_ashare_bucket_time
from datetime import datetime

class AshareLive16PeriodsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = app.test_client()

    def test_bucket_time_calculation(self):
        dt_morning = datetime(2026, 9, 8, 9, 32)
        b3 = get_ashare_bucket_time(dt_morning, "3m")
        self.assertEqual(b3.hour, 9)
        self.assertEqual(b3.minute, 33)

        dt_afternoon = datetime(2026, 9, 8, 13, 1)
        b5 = get_ashare_bucket_time(dt_afternoon, "5m")
        self.assertEqual(b5.hour, 13)
        self.assertEqual(b5.minute, 5)

    def test_all_16_periods_api_response(self):
        periods = [
            "1m", "3m", "5m", "15m", "30m", "60m", "1h", "120m", "2h", "3h", "240m", "4h", "6h", "8h", "12h",
            "daily", "2d", "3d", "weekly", "monthly"
        ]
        for p in periods:
            resp = self.client.get(f"/api/ashare/live/kline?symbol=600519&period={p}&limit=5")
            self.assertEqual(resp.status_code, 200, f"Period {p} status={resp.status_code}")
            data = resp.get_json()
            self.assertIn("kline_data", data)
            self.assertIn("volume_data", data)
            bars = data["kline_data"]
            self.assertGreater(len(bars), 0, f"Period {p} returned empty kline_data")
            if len(bars) >= 2:
                sec_diff = bars[-1]["time"] - bars[-2]["time"]
                if p == "1m":
                    self.assertEqual(sec_diff, 60)
                elif p == "3m":
                    self.assertGreaterEqual(sec_diff, 180)
                elif p in ("5m", "15m", "30m", "60m", "1h"):
                    self.assertGreaterEqual(sec_diff, 300)
                elif p in ("120m", "2h", "3h", "240m", "4h", "6h", "8h", "12h", "daily", "2d", "3d", "weekly", "monthly"):
                    self.assertGreaterEqual(sec_diff, 3600, f"Period {p} diff={sec_diff}")

if __name__ == "__main__":
    unittest.main()
