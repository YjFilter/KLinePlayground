from datetime import datetime
import unittest
from unittest.mock import MagicMock, patch

import pandas as pd

import backend.app_enhanced as app_module
from backend.intraday.chart_window import ChartWindowResult


class IntradayHistoryChartAPITests(unittest.TestCase):
    def setUp(self):
        app_module.active_trainings.clear()
        self.client = app_module.app.test_client()

        self.user_patcher = patch.object(app_module, "user_manager")
        self.mock_user_manager = self.user_patcher.start()

        self.chart_patcher = patch.object(
            app_module,
            "_get_chart_window_service",
            create=True,
        )
        self.mock_chart_factory = self.chart_patcher.start()
        self.mock_chart_service = MagicMock()
        self.mock_chart_factory.return_value = self.mock_chart_service
        self.mock_chart_service.load.return_value = ChartWindowResult(
            period="30m",
            window_start=datetime(2023, 1, 3, 10),
            window_end=datetime(2025, 1, 10, 15),
            kline_data=[{
                "period": "30m",
                "start_time": "2025-01-10 14:30:00",
                "end_time": "2025-01-10 15:00:00",
                "open": 10.0,
                "high": 10.2,
                "low": 9.8,
                "close": 10.1,
                "volume": 1000,
                "amount": 10000.0,
                "source_bar_count": 1,
                "complete": True,
            }],
            volume_data=[{
                "time": "2025-01-10 15:00:00",
                "value": 1000,
                "color": "#ff4d4f",
            }],
            has_earlier=True,
            has_later=True,
            read_only=True,
        )

        self.data_patcher = patch.object(app_module, "data_manager")
        self.mock_data_manager = self.data_patcher.start()

    def tearDown(self):
        self.data_patcher.stop()
        self.chart_patcher.stop()
        self.user_patcher.stop()
        app_module.active_trainings.clear()

    def test_completed_intraday_history_loads_without_active_session(self):
        self.mock_user_manager.get_session_report.return_value = {
            "session_id": "session_1",
            "stock_code": "600000",
            "data_mode": "intraday_30m",
            "period": "30m",
            "training_start": "2025-01-03 10:00:00",
            "training_end": "2025-01-10 15:00:00",
            "max_training_days": 6,
            "trade_details": [{
                "action": "buy",
                "price": 10.1,
                "trade_time": "2025-01-06 10:30:00",
                "display_period": "30m",
            }],
        }

        response = self.client.get(
            "/api/users/test_user/history/session_1/chart",
            query_string={
                "period": "30m",
                "range_start": "2023-01-03 10:00:00",
                "range_end": "2026-01-01 15:00:00",
            },
        )

        self.assertEqual(response.status_code, 200, response.get_json())
        body = response.get_json()
        self.assertTrue(body["read_only"])
        self.assertTrue(body["kline_data"])
        self.assertTrue(body["volume_data"])
        self.assertEqual(body["trade_markers"][0]["time"], "2025-01-06 10:30:00")
        self.assertNotIn("session_1", app_module.active_trainings)
        call = self.mock_chart_service.load.call_args.kwargs
        self.assertTrue(call["read_only"])
        self.assertEqual(call["current_time"], datetime(2025, 1, 10, 15))

    def test_missing_chart_metadata_returns_specific_400(self):
        self.mock_user_manager.get_session_report.return_value = {
            "session_id": "old_session",
            "trade_details": [],
        }

        response = self.client.get(
            "/api/users/test_user/history/old_session/chart",
            query_string={
                "period": "30m",
                "range_start": "2023-01-01",
                "range_end": "2025-01-01",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("缺少走势图重建元数据", response.get_json()["error"])

    def test_legacy_daily_history_uses_read_only_best_effort_data(self):
        self.mock_user_manager.get_session_report.return_value = {
            "session_id": "legacy_1",
            "stock_code": "600000",
            "data_mode": "legacy_daily",
            "data_source": "akshare",
            "period": "daily",
            "training_start": "2024-01-02 00:00:00",
            "training_end": "2024-01-05 00:00:00",
            "trade_details": [{
                "action": "sell",
                "price": 11.0,
                "trade_date": "2024-01-04",
            }],
        }
        self.mock_data_manager.get_stock_data.return_value = pd.DataFrame({
            "date": pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"]),
            "open": [10.0, 10.5, 10.8],
            "high": [10.6, 10.9, 11.2],
            "low": [9.8, 10.2, 10.6],
            "close": [10.5, 10.8, 11.0],
            "volume": [1000, 1200, 1500],
        })

        response = self.client.get(
            "/api/users/test_user/history/legacy_1/chart",
            query_string={
                "period": "daily",
                "range_start": "2024-01-01",
                "range_end": "2024-12-31",
            },
        )

        self.assertEqual(response.status_code, 200, response.get_json())
        body = response.get_json()
        self.assertTrue(body["read_only"])
        self.assertEqual(len(body["kline_data"]), 3)
        self.assertEqual(body["trade_markers"][0]["time"], "2024-01-04")
        self.mock_chart_service.load.assert_not_called()

    def test_legacy_history_falls_back_to_date_level_metadata(self):
        self.mock_user_manager.get_session_report.return_value = {
            "session_id": "legacy_old",
            "stock_code": "600000",
            "start_date": "2024-01-02",
            "end_date": "2024-01-05",
            "trade_details": [],
        }
        self.mock_data_manager.get_stock_data.return_value = pd.DataFrame({
            "date": pd.to_datetime(["2024-01-02", "2024-01-03"]),
            "open": [10.0, 10.5],
            "high": [10.6, 10.9],
            "low": [9.8, 10.2],
            "close": [10.5, 10.8],
            "volume": [1000, 1200],
        })

        response = self.client.get(
            "/api/users/test_user/history/legacy_old/chart",
            query_string={
                "period": "daily",
                "range_start": "2023-01-02",
                "range_end": "2024-01-05",
            },
        )

        self.assertEqual(response.status_code, 200, response.get_json())
        body = response.get_json()
        self.assertEqual(body["training_start"], "2024-01-02 00:00:00")
        self.assertEqual(body["training_end"], "2024-01-05 00:00:00")
