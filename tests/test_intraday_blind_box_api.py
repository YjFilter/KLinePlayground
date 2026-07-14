from datetime import datetime
from unittest.mock import MagicMock, patch

from backend.intraday.chart_window import ChartWindowResult
from backend.intraday.random_selector import RandomIntradaySelection
from tests.test_intraday_api import IntradayAPITestBase, _four_day_frame


class IntradayBlindBoxAPITests(IntradayAPITestBase):
    def setUp(self):
        super().setUp()
        self.selector_patcher = patch.object(
            self.app_module,
            "_get_intraday_random_selector",
            create=True,
        )
        self.mock_selector_factory = self.selector_patcher.start()
        self.mock_selector = MagicMock()
        self.mock_selector_factory.return_value = self.mock_selector

        self.chart_patcher = patch.object(
            self.app_module,
            "_get_chart_window_service",
            create=True,
        )
        self.mock_chart_factory = self.chart_patcher.start()
        self.mock_chart_service = MagicMock()
        self.mock_chart_factory.return_value = self.mock_chart_service
        self.mock_chart_service.load.return_value = ChartWindowResult(
            period="30m",
            window_start=datetime(2023, 1, 3, 10),
            window_end=datetime(2025, 1, 3, 10),
            kline_data=[{
                "period": "30m",
                "start_time": "2025-01-03 10:00:00",
                "end_time": "2025-01-03 10:00:00",
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
                "time": "2025-01-03 10:00:00",
                "value": 1000,
                "color": "#ff4d4f",
            }],
            has_earlier=True,
            has_later=False,
            read_only=False,
        )

    def tearDown(self):
        self.chart_patcher.stop()
        self.selector_patcher.stop()
        super().tearDown()

    def _selection(self):
        return RandomIntradaySelection(
            stock_code="600000",
            start_time=datetime(2025, 1, 3, 10),
            context_start=datetime(2023, 1, 3, 10),
            available_training_days=3,
            base_bars=_four_day_frame(),
        )

    def test_random_intraday_start_uses_real_selected_timestamp_and_trading_days(self):
        self.mock_selector.select.return_value = self._selection()

        response = self.client.post("/api/training/start", json={
            "user": "api_test_user",
            "mode": "random",
            "data_mode": "intraday_30m",
            "sector": "all",
            "date_start": "2024-01-01",
            "date_end": "2026-01-01",
            "max_training_days": 2,
            "period": "30m",
            "initial_capital": 100000,
        })

        self.assertEqual(response.status_code, 200, response.get_json())
        body = response.get_json()
        self.assertEqual(body["data_mode"], "intraday_30m")
        self.assertEqual(body["active_period"], "30m")
        self.assertEqual(body["max_training_days"], 2)
        self.assertEqual(body["training_start"], "2025-01-03 10:00:00")
        self.assertTrue(body["context_kline_data"])
        self.assertGreaterEqual(body["training_start"][:10], "2024-01-01")
        self.assertLessEqual(body["training_start"][:10], "2026-01-01")
        self.mock_selector.select.assert_called_once_with(
            sector="all",
            date_start="2024-01-01",
            date_end="2026-01-01",
            max_training_days=2,
        )

        training = self.app_module.active_trainings[body["id"]]
        self.assertEqual(training["max_training_days"], 2)
        self.assertEqual(training["training_start"], "2025-01-03 10:00:00")
        replay_dates = training["intraday_session"]._base_bars["datetime"].dt.date.unique()
        self.assertEqual(len(replay_dates), 2)

    def test_negative_training_day_limit_is_rejected(self):
        response = self.client.post("/api/training/start", json={
            "user": "api_test_user",
            "mode": "random",
            "data_mode": "intraday_30m",
            "date_start": "2024-01-01",
            "date_end": "2026-01-01",
            "max_training_days": -1,
            "period": "30m",
        })

        self.assertEqual(response.status_code, 400)
        self.assertIn("训练交易日限制不能为负数", response.get_json()["error"])
        self.mock_selector.select.assert_not_called()

    def test_active_chart_window_caps_at_current_replay_time(self):
        self.mock_selector.select.return_value = self._selection()
        start_response = self.client.post("/api/training/start", json={
            "user": "api_test_user",
            "mode": "random",
            "data_mode": "intraday_30m",
            "sector": "all",
            "date_start": "2024-01-01",
            "date_end": "2026-01-01",
            "max_training_days": 2,
            "period": "30m",
        })
        training_id = start_response.get_json()["id"]
        self.mock_chart_service.load.reset_mock()

        response = self.client.get(
            f"/api/training/{training_id}/chart-window",
            query_string={
                "period": "30m",
                "range_start": "2023-01-03 10:00:00",
                "range_end": "2026-01-01 15:00:00",
            },
        )

        self.assertEqual(response.status_code, 200, response.get_json())
        call = self.mock_chart_service.load.call_args.kwargs
        self.assertFalse(call["read_only"])
        self.assertEqual(call["current_time"], datetime(2025, 1, 3, 10))
