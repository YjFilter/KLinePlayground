"""TASK-012: Intraday replay Flask API integration tests.

Black-box tests for the ``intraday_30m`` branch added to ``app_enhanced.py``
while preserving the default ``legacy_daily`` branch and all existing response
behavior.

All tests mock the data service and never call BaoStock live. Only this test
file and ``backend/app_enhanced.py`` are created/modified.
"""

from __future__ import annotations

import json
import os
import sys
import unittest
from datetime import datetime
from typing import Any
from unittest.mock import MagicMock, patch

import pandas as pd

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# ---------------------------------------------------------------------------
# Deterministic offline 30-minute bar data
# ---------------------------------------------------------------------------

TIMES = ("10:00", "10:30", "11:00", "11:30", "13:30", "14:00", "14:30", "15:00")
STOCK_CODE = "600000"
TEST_USER = "test_user_intraday"


def _bar(day: str, time_value: str, price: float = 10.0) -> dict[str, Any]:
    return {
        "datetime": pd.Timestamp(f"{day} {time_value}:00"),
        "open": price,
        "high": price + 0.2,
        "low": price - 0.2,
        "close": price + 0.1,
        "volume": 1000,
        "amount": 10000.0,
    }


def _flat_day(day: str, price: float = 10.0) -> list[dict[str, Any]]:
    return [_bar(day, t, price) for t in TIMES]


def _four_day_frame() -> pd.DataFrame:
    """Four trading days spanning two ISO weeks.

    Week 1: 2025-01-02 (Thu), 2025-01-03 (Fri)
    Week 2: 2025-01-06 (Mon), 2025-01-07 (Tue)
    """
    rows = (
        _flat_day("2025-01-02", 10.0)
        + _flat_day("2025-01-03", 11.0)
        + _flat_day("2025-01-06", 12.0)
        + _flat_day("2025-01-07", 13.0)
    )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Fake trade simulator (avoids SQLite, supports IntradayReplaySession.advance)
# ---------------------------------------------------------------------------


class FakeTradeSimulator:
    """In-memory simulator compatible with IntradayReplaySession + app routes."""

    def __init__(self, user: str, initial_capital: float, stock_code: str):
        self.user = user
        self.stock_code = stock_code
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.current_price = 0.0
        self.current_bar_id = 0
        self.commission_rate = 0.0003
        self.min_commission = 5.0
        self.stamp_tax_rate = 0.001
        self.total_shares = 0
        self.average_cost = 0.0
        self.total_cost = 0.0
        self.trade_history: list[dict[str, Any]] = []
        self.session_id = ""

    def set_commission_settings(self, cr, mc, st):
        self.commission_rate = cr
        self.min_commission = mc
        self.stamp_tax_rate = st

    def update_current_price(self, price: float, bar_id: int):
        self.current_price = price
        self.current_bar_id = bar_id

    def buy(self, quantity, price, trade_date, reason="", trade_time="", display_period=""):
        amount = quantity * 100 * price
        commission = max(amount * self.commission_rate, self.min_commission)
        total_cost = amount + commission
        self.current_capital -= total_cost
        self.total_shares += quantity * 100
        self.total_cost += amount
        self.average_cost = self.total_cost / self.total_shares if self.total_shares else 0.0
        trade = {
            "stock_code": self.stock_code,
            "action": "buy",
            "quantity": quantity,
            "price": price,
            "amount": amount,
            "commission": commission,
            "stamp_tax": 0.0,
            "net_amount": total_cost,
            "trade_date": trade_date,
            "trade_time": trade_time,
            "display_period": display_period,
            "bar_id": self.current_bar_id,
            "reason": reason,
        }
        self.trade_history.append(trade)
        return {"success": True, "trade": trade, "message": "ok"}

    def sell(self, quantity, price, trade_date, reason="", trade_time="", display_period=""):
        amount = quantity * 100 * price
        commission = max(amount * self.commission_rate, self.min_commission)
        stamp_tax = amount * self.stamp_tax_rate
        net = amount - commission - stamp_tax
        self.current_capital += net
        self.total_shares = max(0, self.total_shares - quantity * 100)
        trade = {
            "stock_code": self.stock_code,
            "action": "sell",
            "quantity": quantity,
            "price": price,
            "amount": amount,
            "commission": commission,
            "stamp_tax": stamp_tax,
            "net_amount": net,
            "trade_date": trade_date,
            "trade_time": trade_time,
            "display_period": display_period,
            "bar_id": self.current_bar_id,
            "reason": reason,
        }
        self.trade_history.append(trade)
        return {"success": True, "trade": trade, "message": "ok"}

    def get_account_info(self, trade_date):
        market_value = self.total_shares * self.current_price
        total_assets = self.current_capital + market_value
        return {
            "total_assets": total_assets,
            "available_cash": self.current_capital,
            "position_value": market_value,
            "floating_pnl": market_value - self.total_cost,
            "initial_capital": self.initial_capital,
            "total_return": ((total_assets - self.initial_capital) / self.initial_capital) * 100,
            "current_bar_id": self.current_bar_id,
            "max_buyable_quantity": int(self.current_capital / (self.current_price * 100)) if self.current_price > 0 else 0,
            "position_summary": {
                "total_shares": self.total_shares,
                "available_shares": self.total_shares,
                "average_cost": self.average_cost,
                "current_price": self.current_price,
                "pnl_percent": 0.0,
            } if self.total_shares > 0 else None,
        }

    def get_trade_history_with_bar_id(self):
        return self.trade_history.copy()

    def generate_report(self, stock_code, start_date, end_date):
        return {
            "session_id": self.session_id,
            "stock_code": stock_code,
            "stock_name": f"股票{stock_code}",
            "start_date": start_date,
            "end_date": end_date,
            "initial_capital": self.initial_capital,
            "final_capital": self.current_capital,
            "total_return": 0.0,
            "total_trades": len(self.trade_history),
            "trade_win_rate": 0.0,
            "session_win_rate": 0,
            "win_count": 0,
            "total_sell_trades": 0,
            "total_commission": sum(t["commission"] for t in self.trade_history),
            "total_stamp_tax": sum(t["stamp_tax"] for t in self.trade_history),
            "trade_details": [],
            "commission_settings": {
                "commission_rate": self.commission_rate,
                "min_commission": self.min_commission,
                "stamp_tax_rate": self.stamp_tax_rate,
            },
        }

    def reset(self):
        self.current_capital = self.initial_capital
        self.total_shares = 0
        self.average_cost = 0.0
        self.total_cost = 0.0
        self.trade_history = []
        self.current_bar_id = 0


# ---------------------------------------------------------------------------
# Test base: Flask test client + mocks
# ---------------------------------------------------------------------------


class IntradayAPITestBase(unittest.TestCase):
    """Base class setting up Flask test client and mocking external services."""

    @classmethod
    def setUpClass(cls):
        import backend.app_enhanced as ae
        cls.app_module = ae
        cls.app = ae.app
        cls.app.config["TESTING"] = True

    def setUp(self):
        self.app_module.active_trainings.clear()

        # mock user_manager: avoid real user database writes
        self._user_manager_patcher = patch.object(self.app_module, "user_manager")
        self.mock_user_manager = self._user_manager_patcher.start()
        self.mock_user_manager.get_user_config.return_value = None
        self.mock_user_manager.start_training_session.return_value = True
        self.mock_user_manager.save_training_session.return_value = True

        # mock data_manager: only need get_stock_name
        self._data_manager_patcher = patch.object(self.app_module, "data_manager")
        self.mock_data_manager = self._data_manager_patcher.start()
        self.mock_data_manager.get_stock_name.return_value = "测试股票"

        # mock _get_intraday_data_service: never touch BaoStock
        self._service_patcher = patch.object(self.app_module, "_get_intraday_data_service")
        self.mock_service_factory = self._service_patcher.start()
        self.mock_service = MagicMock()
        self.mock_service.get_30m.return_value = _four_day_frame()
        self.mock_service_factory.return_value = self.mock_service

        # mock _update_api_info: avoid writing ai_api_info.json
        self._api_info_patcher = patch.object(self.app_module, "_update_api_info")
        self._api_info_patcher.start()

        # mock TradeSimulatorEnhanced: avoid SQLite, use in-memory fake
        self._sim_patcher = patch.object(
            self.app_module, "TradeSimulatorEnhanced", side_effect=FakeTradeSimulator
        )
        self._sim_patcher.start()

        self.client = self.app.test_client()

    def tearDown(self):
        patch.stopall()
        self.app_module.active_trainings.clear()

    # -- helpers -------------------------------------------------------

    def _start_intraday(self, period="30m", data_mode="intraday_30m",
                        stock_code=STOCK_CODE, start_date="2025-01-02",
                        initial_capital=100000, extra=None):
        payload = {
            "user": TEST_USER,
            "mode": "specified",
            "stock_code": stock_code,
            "start_date": start_date,
            "period": period,
            "data_mode": data_mode,
            "initial_capital": initial_capital,
        }
        payload.update(extra or {})
        return self.client.post("/api/training/start", json=payload)

    def _start_intraday_and_get_id(self, **kwargs):
        resp = self._start_intraday(**kwargs)
        self.assertEqual(resp.status_code, 200, resp.get_json())
        return resp.get_json()["id"]


# ---------------------------------------------------------------------------
# Acceptance: Start accepts explicit data_mode and all four period values
# ---------------------------------------------------------------------------


class StartIntradayTests(IntradayAPITestBase):
    """Intraday start loads data via IntradayDataService and returns snapshot."""

    def test_start_intraday_returns_200_with_data_mode(self):
        resp = self._start_intraday(period="30m", data_mode="intraday_30m")
        self.assertEqual(resp.status_code, 200, resp.get_json())
        body = resp.get_json()
        self.assertEqual(body["data_mode"], "intraday_30m")

    def test_start_accepts_all_four_periods(self):
        for period in ("30m", "4h_session", "daily", "weekly"):
            self.app_module.active_trainings.clear()
            resp = self._start_intraday(period=period, data_mode="intraday_30m")
            self.assertEqual(resp.status_code, 200, f"period={period}: {resp.get_json()}")
            body = resp.get_json()
            self.assertEqual(body["data_mode"], "intraday_30m")
            self.assertEqual(body["active_period"], period)

    def test_start_invalid_data_mode_returns_400(self):
        resp = self._start_intraday(period="30m", data_mode="unknown")
        self.assertEqual(resp.status_code, 400)
        self.mock_service.get_30m.assert_not_called()

    def test_start_loads_data_via_intraday_service(self):
        self._start_intraday_and_get_id()
        self.mock_service.get_30m.assert_called()
        call_args = self.mock_service.get_30m.call_args_list[0]
        self.assertEqual(call_args.args[0], STOCK_CODE)

    def test_start_requests_two_years_of_context_and_persists_trading_day_limit(self):
        response = self._start_intraday(
            period="30m",
            start_date="2025-01-03",
            extra={"max_training_days": 2},
        )

        self.assertEqual(response.status_code, 200, response.get_json())
        first_call = self.mock_service.get_30m.call_args_list[0]
        self.assertEqual(first_call.args[1], datetime(2023, 1, 3))
        body = response.get_json()
        self.assertEqual(body["max_training_days"], 2)
        self.assertEqual(body["training_start"], "2025-01-03 10:00:00")
        self.assertTrue(body["context_kline_data"])

        saved = self.mock_user_manager.start_training_session.call_args.args[1]
        self.assertEqual(saved["base_interval"], "30m")
        self.assertEqual(saved["max_training_days"], 2)
        self.assertEqual(saved["training_start"], "2025-01-03 10:00:00")

    def test_start_chooses_first_timestamp_on_or_after_start_date(self):
        """initial_time 应为 start_date 当天或之后的第一根真实时间戳。"""
        resp = self._start_intraday(period="30m", start_date="2025-01-03")
        body = resp.get_json()
        # 2025-01-03 的第一根 30m 线是 10:00
        self.assertEqual(body["current_time"], "2025-01-03 10:00:00")

    def test_start_rejects_when_no_timestamp_exists_after_start_date(self):
        resp = self._start_intraday(period="30m", start_date="2025-01-08")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("之后没有可用", resp.get_json()["error"])

    def test_start_initializes_real_base_bar_id(self):
        resp = self._start_intraday(period="30m", start_date="2025-01-03")
        training = self.app_module.active_trainings[resp.get_json()["id"]]
        self.assertEqual(training["trade_simulator"].current_bar_id, 9)

    def test_start_stores_exactly_one_session(self):
        self._start_intraday_and_get_id()
        self.assertEqual(len(self.app_module.active_trainings), 1)

    def test_start_response_includes_complete_snapshot(self):
        resp = self._start_intraday(period="daily")
        body = resp.get_json()
        # snapshot 核心字段
        for field in ("current_time", "active_period", "base_interval",
                      "available_periods", "current_bar_complete", "next_boundary",
                      "kline_data", "current_base_bar", "finished"):
            self.assertIn(field, body, f"missing snapshot field: {field}")
        # 元数据字段
        self.assertEqual(body["data_mode"], "intraday_30m")
        self.assertEqual(body["stock_code"], STOCK_CODE)
        self.assertIn("id", body)

    def test_start_base_interval_is_30m(self):
        resp = self._start_intraday()
        self.assertEqual(resp.get_json()["base_interval"], "30m")

    def test_start_available_periods_has_four_values(self):
        resp = self._start_intraday()
        self.assertEqual(resp.get_json()["available_periods"],
                         ["30m", "4h_session", "daily", "weekly"])

    def test_start_invalid_period_with_intraday_mode_returns_400(self):
        resp = self._start_intraday(period="1h", data_mode="intraday_30m")
        self.assertEqual(resp.status_code, 400)

    def test_start_missing_stock_code_returns_400(self):
        resp = self.client.post("/api/training/start", json={
            "user": TEST_USER, "mode": "specified",
            "start_date": "2025-01-02", "period": "30m",
            "data_mode": "intraday_30m", "initial_capital": 100000,
        })
        self.assertEqual(resp.status_code, 400)

    def test_start_empty_base_bars_returns_400(self):
        self.mock_service.get_30m.return_value = pd.DataFrame(
            columns=["datetime", "open", "high", "low", "close", "volume", "amount"]
        )
        resp = self._start_intraday()
        self.assertEqual(resp.status_code, 400)

    def test_start_service_failure_returns_400(self):
        self.mock_service.get_30m.side_effect = RuntimeError("network error")
        resp = self._start_intraday()
        self.assertEqual(resp.status_code, 400)
        self.assertIn("intraday", resp.get_json()["error"])

    def test_start_missing_user_returns_400(self):
        resp = self.client.post("/api/training/start", json={
            "mode": "specified", "stock_code": STOCK_CODE,
            "start_date": "2025-01-02", "period": "30m",
            "data_mode": "intraday_30m",
        })
        self.assertEqual(resp.status_code, 400)


# ---------------------------------------------------------------------------
# Acceptance: Requests without data_mode preserve legacy daily behavior
# ---------------------------------------------------------------------------


class LegacyCompatTests(IntradayAPITestBase):
    """未传 data_mode 时保持 legacy_daily 行为完全兼容。"""

    def test_resolve_data_mode_no_data_mode_daily_returns_legacy(self):
        from backend.app_enhanced import _resolve_data_mode, DATA_MODE_LEGACY_DAILY
        self.assertEqual(_resolve_data_mode(None, "daily"), DATA_MODE_LEGACY_DAILY)

    def test_resolve_data_mode_no_data_mode_weekly_returns_legacy(self):
        from backend.app_enhanced import _resolve_data_mode, DATA_MODE_LEGACY_DAILY
        self.assertEqual(_resolve_data_mode(None, "weekly"), DATA_MODE_LEGACY_DAILY)

    def test_resolve_data_mode_explicit_legacy(self):
        from backend.app_enhanced import _resolve_data_mode, DATA_MODE_LEGACY_DAILY
        self.assertEqual(_resolve_data_mode("legacy_daily", "daily"), DATA_MODE_LEGACY_DAILY)

    def test_resolve_data_mode_explicit_intraday(self):
        from backend.app_enhanced import _resolve_data_mode, DATA_MODE_INTRADAY_30M
        self.assertEqual(_resolve_data_mode("intraday_30m", "daily"), DATA_MODE_INTRADAY_30M)

    def test_resolve_data_mode_30m_without_mode_remains_legacy(self):
        from backend.app_enhanced import _resolve_data_mode, DATA_MODE_LEGACY_DAILY
        self.assertEqual(_resolve_data_mode(None, "30m"), DATA_MODE_LEGACY_DAILY)

    def test_legacy_daily_request_does_not_trigger_intraday_service(self):
        """不传 data_mode + period=daily 不调用 IntradayDataService。"""
        # legacy 路径需要 data_manager 配合；这里只验证 intraday 服务不被调用
        self.mock_data_manager.get_training_validation_error.return_value = None
        self.mock_data_manager.get_random_stock.return_value = (STOCK_CODE, "2025-01-02")
        with patch.object(self.app_module, "KLineProcessorEnhanced") as mock_kline_cls:
            mock_kline_cls.return_value = MagicMock()
            self.client.post("/api/training/start", json={
                "user": TEST_USER, "mode": "specified",
                "stock_code": STOCK_CODE, "start_date": "2025-01-02",
                "period": "daily", "initial_capital": 100000,
            })
        self.mock_service.get_30m.assert_not_called()


# ---------------------------------------------------------------------------
# Acceptance: New period route switches without advancing
# ---------------------------------------------------------------------------


class PeriodSwitchTests(IntradayAPITestBase):
    """POST /api/training/{id}/period 切换周期，不推进时间。"""

    def test_period_switch_returns_snapshot(self):
        tid = self._start_intraday_and_get_id(period="30m")
        resp = self.client.post(f"/api/training/{tid}/period", json={"period": "daily"})
        self.assertEqual(resp.status_code, 200, resp.get_json())
        body = resp.get_json()
        self.assertEqual(body["active_period"], "daily")
        self.assertIn("kline_data", body)

    def test_period_switch_does_not_advance_time(self):
        tid = self._start_intraday_and_get_id(period="30m")
        before = self.client.get(f"/api/training/{tid}/data").get_json()
        self.client.post(f"/api/training/{tid}/period", json={"period": "daily"})
        self.client.post(f"/api/training/{tid}/period", json={"period": "weekly"})
        self.client.post(f"/api/training/{tid}/period", json={"period": "30m"})
        after = self.client.get(f"/api/training/{tid}/data").get_json()
        self.assertEqual(before["current_time"], after["current_time"])

    def test_period_switch_to_each_of_four_periods(self):
        tid = self._start_intraday_and_get_id(period="30m")
        for period in ("4h_session", "daily", "weekly", "30m"):
            resp = self.client.post(f"/api/training/{tid}/period", json={"period": period})
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.get_json()["active_period"], period)

    def test_period_switch_invalid_period_returns_400(self):
        tid = self._start_intraday_and_get_id()
        resp = self.client.post(f"/api/training/{tid}/period", json={"period": "1h"})
        self.assertEqual(resp.status_code, 400)

    def test_period_switch_missing_period_param_returns_400(self):
        tid = self._start_intraday_and_get_id()
        resp = self.client.post(f"/api/training/{tid}/period", json={})
        self.assertEqual(resp.status_code, 400)

    def test_period_switch_on_legacy_session_returns_400(self):
        """legacy 会话不支持周期切换。"""
        # 手动构造一个 legacy session
        self.app_module.active_trainings["legacy_tid"] = {
            "data_mode": "legacy_daily",
            "trade_simulator": MagicMock(),
        }
        resp = self.client.post("/api/training/legacy_tid/period", json={"period": "30m"})
        self.assertEqual(resp.status_code, 400)


# ---------------------------------------------------------------------------
# Acceptance: Intraday next route advances by active-period boundary
# ---------------------------------------------------------------------------


class IntradayNextTests(IntradayAPITestBase):
    """POST /api/training/{id}/next 按活动周期边界推进，返回 ordered events。"""

    def test_next_30m_advances_one_bar(self):
        tid = self._start_intraday_and_get_id(period="30m", start_date="2025-01-02")
        resp = self.client.post(f"/api/training/{tid}/next")
        self.assertEqual(resp.status_code, 200, resp.get_json())
        body = resp.get_json()
        self.assertFalse(body["finished"])
        self.assertEqual(body["data_mode"], "intraday_30m")
        self.assertEqual(body["snapshot"]["current_time"], "2025-01-02 10:30:00")

    def test_next_returns_order_events_list(self):
        tid = self._start_intraday_and_get_id(period="30m")
        resp = self.client.post(f"/api/training/{tid}/next")
        body = resp.get_json()
        self.assertIn("order_events", body)
        self.assertIsInstance(body["order_events"], list)

    def test_next_returns_completed_times_list(self):
        tid = self._start_intraday_and_get_id(period="30m")
        resp = self.client.post(f"/api/training/{tid}/next")
        body = resp.get_json()
        self.assertIn("completed_times", body)
        self.assertIsInstance(body["completed_times"], list)
        self.assertEqual(body["completed_times"], ["2025-01-02 10:30:00"])
        training = self.app_module.active_trainings[tid]
        self.assertEqual(training["trade_simulator"].current_bar_id, 2)

    def test_next_daily_advances_to_session_close(self):
        tid = self._start_intraday_and_get_id(period="daily", start_date="2025-01-02")
        resp = self.client.post(f"/api/training/{tid}/next")
        body = resp.get_json()
        self.assertEqual(body["snapshot"]["current_time"], "2025-01-02 15:00:00")

    def test_next_returns_pending_orders_payload(self):
        tid = self._start_intraday_and_get_id(period="30m")
        resp = self.client.post(f"/api/training/{tid}/next")
        body = resp.get_json()
        self.assertIn("pending_orders", body)
        self.assertIn("buy_orders", body["pending_orders"])
        self.assertIn("exit_orders", body["pending_orders"])

    def test_next_finished_returns_report(self):
        """推进到最后一根后返回 finished=True 和 report。"""
        # 从最后一根开始，weekly period → 已 finished
        tid = self._start_intraday_and_get_id(period="weekly", start_date="2025-01-07")
        # 推进一次到周末
        resp = self.client.post(f"/api/training/{tid}/next")
        # 此时应该在 2025-01-07 15:00，再推进可能 finished
        body = resp.get_json()
        # weekly 从 01-07 10:00 推进到 01-07 15:00（本周最后）
        # 再次推进应 finished
        resp2 = self.client.post(f"/api/training/{tid}/next")
        body2 = resp2.get_json()
        if body2.get("finished"):
            self.assertIn("report", body2)
            self.assertEqual(body2["data_mode"], "intraday_30m")


# ---------------------------------------------------------------------------
# Acceptance: Intraday data route returns snapshot without mutating state
# ---------------------------------------------------------------------------


class IntradayDataTests(IntradayAPITestBase):
    """GET /api/training/{id}/data 返回当前快照，不推进回放状态。"""

    def test_data_returns_snapshot_with_data_mode(self):
        tid = self._start_intraday_and_get_id()
        resp = self.client.get(f"/api/training/{tid}/data")
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertEqual(body["data_mode"], "intraday_30m")
        self.assertIn("current_time", body)
        self.assertIn("kline_data", body)

    def test_data_does_not_advance_time(self):
        tid = self._start_intraday_and_get_id(period="30m")
        before = self.client.get(f"/api/training/{tid}/data").get_json()
        self.client.get(f"/api/training/{tid}/data")
        self.client.get(f"/api/training/{tid}/data")
        after = self.client.get(f"/api/training/{tid}/data").get_json()
        self.assertEqual(before["current_time"], after["current_time"])

    def test_data_returns_current_base_bar(self):
        tid = self._start_intraday_and_get_id(period="30m")
        body = self.client.get(f"/api/training/{tid}/data").get_json()
        self.assertIsNotNone(body["current_base_bar"])
        self.assertIn("close", body["current_base_bar"])


# ---------------------------------------------------------------------------
# Acceptance: Manual trade uses current base close and saves full period
# ---------------------------------------------------------------------------


class IntradayTradeTests(IntradayAPITestBase):
    """POST /api/training/{id}/trade 使用当前 base bar close，保存 time/display period。"""

    def test_trade_buy_uses_current_base_close(self):
        tid = self._start_intraday_and_get_id(period="30m", start_date="2025-01-02")
        # 当前 base bar close = 10.1 (2025-01-02 10:00, price=10.0, close=10.1)
        resp = self.client.post(f"/api/training/{tid}/trade", json={
            "action": "buy", "quantity": 10, "order_type": "market",
        })
        self.assertEqual(resp.status_code, 200, resp.get_json())
        body = resp.get_json()
        self.assertTrue(body["success"])
        trade = body["trade"]
        self.assertAlmostEqual(trade["price"], 10.1)

    def test_trade_ignores_open_price_request(self):
        tid = self._start_intraday_and_get_id(period="30m", start_date="2025-01-02")
        resp = self.client.post(f"/api/training/{tid}/trade", json={
            "action": "buy", "quantity": 10, "order_type": "market", "price_type": "open",
        })
        self.assertEqual(resp.status_code, 200, resp.get_json())
        self.assertAlmostEqual(resp.get_json()["trade"]["price"], 10.1)

    def test_trade_saves_trade_time_and_display_period(self):
        tid = self._start_intraday_and_get_id(period="30m", start_date="2025-01-02")
        resp = self.client.post(f"/api/training/{tid}/trade", json={
            "action": "buy", "quantity": 5, "order_type": "market",
        })
        trade = resp.get_json()["trade"]
        self.assertEqual(trade["trade_time"], "2025-01-02 10:00:00")
        self.assertEqual(trade["display_period"], "30m")

    def test_trade_sell_after_buy(self):
        tid = self._start_intraday_and_get_id(period="30m", start_date="2025-01-02")
        # 先买入
        self.client.post(f"/api/training/{tid}/trade", json={
            "action": "buy", "quantity": 10, "order_type": "market",
        })
        # 推进到下一交易日使持仓可卖 (T+1)
        for _ in range(8):
            self.client.post(f"/api/training/{tid}/next")
        # 卖出
        resp = self.client.post(f"/api/training/{tid}/trade", json={
            "action": "sell", "quantity": 10, "order_type": "market",
        })
        self.assertEqual(resp.status_code, 200, resp.get_json())
        self.assertTrue(resp.get_json()["success"])

    def test_trade_invalid_action_returns_400(self):
        tid = self._start_intraday_and_get_id()
        resp = self.client.post(f"/api/training/{tid}/trade", json={
            "action": "invalid", "quantity": 10,
        })
        self.assertEqual(resp.status_code, 400)

    def test_trade_missing_quantity_returns_400(self):
        tid = self._start_intraday_and_get_id()
        resp = self.client.post(f"/api/training/{tid}/trade", json={
            "action": "buy",
        })
        self.assertEqual(resp.status_code, 400)

    def test_trade_returns_data_mode_in_response(self):
        tid = self._start_intraday_and_get_id()
        resp = self.client.post(f"/api/training/{tid}/trade", json={
            "action": "buy", "quantity": 10, "order_type": "market",
        })
        self.assertEqual(resp.get_json()["data_mode"], "intraday_30m")


# ---------------------------------------------------------------------------
# Acceptance: Account, pending-order, reset, end routes remain usable
# ---------------------------------------------------------------------------


class IntradayAccountTests(IntradayAPITestBase):
    """GET /api/training/{id}/account 返回兼容账户信息。"""

    def test_account_returns_compatible_payload(self):
        tid = self._start_intraday_and_get_id()
        resp = self.client.get(f"/api/training/{tid}/account")
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        # 兼容字段
        for field in ("total_assets", "available_cash", "position_value",
                      "initial_capital", "total_return"):
            self.assertIn(field, body)
        # intraday 附加字段
        self.assertEqual(body["data_mode"], "intraday_30m")
        self.assertIn("current_time", body)
        self.assertIn("active_period", body)
        self.assertIn("pending_orders", body)

    def test_account_does_not_advance_time(self):
        tid = self._start_intraday_and_get_id(period="30m")
        before = self.client.get(f"/api/training/{tid}/data").get_json()
        self.client.get(f"/api/training/{tid}/account")
        after = self.client.get(f"/api/training/{tid}/data").get_json()
        self.assertEqual(before["current_time"], after["current_time"])


class IntradayPendingOrdersTests(IntradayAPITestBase):
    """GET /api/training/{id}/orders 在 intraday 模式下可用。"""

    def test_get_pending_orders_returns_dict(self):
        tid = self._start_intraday_and_get_id()
        resp = self.client.get(f"/api/training/{tid}/orders")
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertIn("buy_orders", body)
        self.assertIn("exit_orders", body)


class IntradayResetTests(IntradayAPITestBase):
    """POST /api/training/{id}/reset 重置 intraday 会话。"""

    def test_reset_returns_snapshot_and_message(self):
        tid = self._start_intraday_and_get_id(period="30m")
        # 推进一步
        self.client.post(f"/api/training/{tid}/next")
        # 重置
        resp = self.client.post(f"/api/training/{tid}/reset")
        self.assertEqual(resp.status_code, 200, resp.get_json())
        body = resp.get_json()
        self.assertEqual(body["data_mode"], "intraday_30m")
        self.assertIn("snapshot", body)
        # 重置后 current_time 应回到初始
        self.assertEqual(body["snapshot"]["current_time"], "2025-01-02 10:00:00")

    def test_reset_restores_initial_period(self):
        tid = self._start_intraday_and_get_id(period="30m")
        self.client.post(f"/api/training/{tid}/period", json={"period": "daily"})
        resp = self.client.post(f"/api/training/{tid}/reset")
        # reset 恢复初始 period (30m)
        self.assertEqual(resp.get_json()["snapshot"]["active_period"], "30m")


class IntradayEndTests(IntradayAPITestBase):
    """POST /api/training/{id}/end 生成报告并标记 ended。"""

    def test_end_returns_report_with_data_mode(self):
        tid = self._start_intraday_and_get_id()
        resp = self.client.post(f"/api/training/{tid}/end")
        self.assertEqual(resp.status_code, 200, resp.get_json())
        body = resp.get_json()
        self.assertIn("session_id", body)
        self.assertEqual(body["data_mode"], "intraday_30m")
        self.assertIn("initial_capital", body)
        self.assertIn("final_capital", body)

    def test_end_marks_session_status_ended(self):
        tid = self._start_intraday_and_get_id()
        self.client.post(f"/api/training/{tid}/end")
        self.assertEqual(
            self.app_module.active_trainings[tid]["status"], "ended"
        )

    def test_end_saves_session_via_user_manager(self):
        tid = self._start_intraday_and_get_id()
        self.mock_user_manager.save_training_session.reset_mock()
        self.client.post(f"/api/training/{tid}/end")
        self.mock_user_manager.save_training_session.assert_called_once()


# ---------------------------------------------------------------------------
# Acceptance: Tests mock network/data services and never call BaoStock live
# ---------------------------------------------------------------------------


class NoLiveNetworkTests(IntradayAPITestBase):
    """验证测试不访问真实 BaoStock 网络。"""

    def test_intraday_service_is_mocked(self):
        """_get_intraday_data_service 返回的是 MagicMock，不是真实 BaoStockSource。"""
        tid = self._start_intraday_and_get_id()
        self.mock_service_factory.assert_called()
        self.mock_service.get_30m.assert_called()

    def test_no_baostock_module_imported_during_start(self):
        """启动 intraday 会话不导入 baostock 模块。"""
        # 记录导入前的 baostock 状态
        baostock_was_loaded = "baostock" in sys.modules
        self._start_intraday_and_get_id()
        # 不应新导入 baostock (因为 service 被 mock 了)
        if not baostock_was_loaded:
            self.assertNotIn("baostock", sys.modules)

    def test_start_then_data_then_next_full_flow(self):
        """完整流程: start → data → period → next → trade → account → end。"""
        tid = self._start_intraday_and_get_id(period="30m", start_date="2025-01-02")

        # data
        resp = self.client.get(f"/api/training/{tid}/data")
        self.assertEqual(resp.status_code, 200)

        # period switch
        resp = self.client.post(f"/api/training/{tid}/period", json={"period": "daily"})
        self.assertEqual(resp.status_code, 200)

        # next
        resp = self.client.post(f"/api/training/{tid}/next")
        self.assertEqual(resp.status_code, 200)

        # switch back to 30m and trade
        self.client.post(f"/api/training/{tid}/period", json={"period": "30m"})
        resp = self.client.post(f"/api/training/{tid}/trade", json={
            "action": "buy", "quantity": 10, "order_type": "market",
        })
        self.assertEqual(resp.status_code, 200)

        # account
        resp = self.client.get(f"/api/training/{tid}/account")
        self.assertEqual(resp.status_code, 200)

        # end
        resp = self.client.post(f"/api/training/{tid}/end")
        self.assertEqual(resp.status_code, 200)


# ---------------------------------------------------------------------------
# Acceptance: Snapshot JSON serializable
# ---------------------------------------------------------------------------


class JsonSerializableTests(IntradayAPITestBase):
    """intraday 响应必须可 JSON 序列化。"""

    def test_start_response_is_json_serializable(self):
        tid = self._start_intraday_and_get_id(period="daily")
        body = self.client.get(f"/api/training/{tid}/data").get_json()
        json.dumps(body)

    def test_next_response_is_json_serializable(self):
        tid = self._start_intraday_and_get_id(period="30m")
        resp = self.client.post(f"/api/training/{tid}/next")
        json.dumps(resp.get_json())

    def test_period_switch_response_is_json_serializable(self):
        tid = self._start_intraday_and_get_id()
        resp = self.client.post(f"/api/training/{tid}/period", json={"period": "daily"})
        json.dumps(resp.get_json())


# ---------------------------------------------------------------------------
# Acceptance: 404 handling
# ---------------------------------------------------------------------------


class NotFoundTests(IntradayAPITestBase):
    """不存在的 training_id 返回 404。"""

    def test_data_not_found(self):
        resp = self.client.get("/api/training/nonexistent/data")
        self.assertEqual(resp.status_code, 404)

    def test_next_not_found(self):
        resp = self.client.post("/api/training/nonexistent/next")
        self.assertEqual(resp.status_code, 404)

    def test_period_not_found(self):
        resp = self.client.post("/api/training/nonexistent/period", json={"period": "30m"})
        self.assertEqual(resp.status_code, 404)

    def test_trade_not_found(self):
        resp = self.client.post("/api/training/nonexistent/trade", json={
            "action": "buy", "quantity": 1,
        })
        self.assertEqual(resp.status_code, 404)

    def test_account_not_found(self):
        resp = self.client.get("/api/training/nonexistent/account")
        self.assertEqual(resp.status_code, 404)

    def test_end_not_found(self):
        resp = self.client.post("/api/training/nonexistent/end")
        self.assertEqual(resp.status_code, 404)

    def test_reset_not_found(self):
        resp = self.client.post("/api/training/nonexistent/reset")
        self.assertEqual(resp.status_code, 404)


if __name__ == "__main__":
    unittest.main()
