import importlib
import unittest

import pandas as pd

from backend.kline_processor_enhanced import KLineProcessorEnhanced


class DummyDataManager:
    def __init__(self, rows=160):
        dates = pd.date_range("2024-01-01", periods=rows, freq="B")
        self.data = pd.DataFrame(
            {
                "date": dates,
                "open": [10.0 + i * 0.01 for i in range(rows)],
                "high": [10.5 + i * 0.01 for i in range(rows)],
                "low": [9.5 + i * 0.01 for i in range(rows)],
                "close": [10.1 + i * 0.01 for i in range(rows)],
                "volume": [100000 + i for i in range(rows)],
            }
        )

    def get_stock_data(self, stock_code, source="akshare", interval="daily"):
        return self.data.copy()

    def get_factor_data(self, stock_code, source="akshare", interval="daily"):
        return pd.DataFrame(columns=["date", "factor"])

    def get_dividend_data(self, stock_code):
        return pd.DataFrame()


class MarketRuleTests(unittest.TestCase):
    def _load_rules(self):
        try:
            return importlib.import_module("backend.market_rules")
        except ModuleNotFoundError as exc:
            self.fail(f"backend.market_rules module should exist: {exc}")

    def test_main_board_limit_prices_are_10_percent(self):
        rules = self._load_rules()

        status = rules.get_limit_status("600000", prev_close=10.0, price=11.0)

        self.assertEqual(status.status, "limit_up")
        self.assertEqual(status.limit_up, 11.0)
        self.assertEqual(status.limit_down, 9.0)

    def test_chinext_and_star_market_limit_prices_are_20_percent(self):
        rules = self._load_rules()

        self.assertEqual(rules.get_limit_status("300001", 10.0, 12.0).status, "limit_up")
        self.assertEqual(rules.get_limit_status("688001", 10.0, 8.0).status, "limit_down")


class PendingOrderTests(unittest.TestCase):
    def _manager(self):
        try:
            module = importlib.import_module("backend.order_manager")
        except ModuleNotFoundError as exc:
            self.fail(f"backend.order_manager module should exist: {exc}")
        return module.PendingOrderManager()

    def test_limit_buy_triggers_on_future_bar_and_creates_exit_orders(self):
        manager = self._manager()
        manager.add_buy_order(
            order_type="limit",
            quantity=3,
            trigger_price=10.0,
            take_profit_price=12.0,
            stop_loss_price=9.0,
        )
        buys = []

        def execute_buy(quantity, price, order):
            buys.append((quantity, price, order["order_type"]))
            return {"success": True, "message": "ok"}

        events = manager.process_bar(
            bar={"open": 10.5, "high": 10.8, "low": 9.9, "close": 10.2},
            prev_close=10.0,
            stock_code="600000",
            trade_date="2024-02-01",
            execute_buy=execute_buy,
            execute_sell=lambda quantity, price, order: {"success": True},
        )

        self.assertEqual(buys, [(3, 10.0, "limit")])
        self.assertEqual(events[0]["status"], "filled")
        self.assertEqual(len(manager.active_buy_orders), 0)
        self.assertEqual(len(manager.active_exit_orders), 2)

    def test_breakout_buy_gaps_to_open_price(self):
        manager = self._manager()
        manager.add_buy_order(order_type="breakout", quantity=2, trigger_price=10.0)
        buys = []

        manager.process_bar(
            bar={"open": 10.3, "high": 10.6, "low": 10.2, "close": 10.4},
            prev_close=9.8,
            stock_code="600000",
            trade_date="2024-02-01",
            execute_buy=lambda quantity, price, order: buys.append((quantity, price)) or {"success": True},
            execute_sell=lambda quantity, price, order: {"success": True},
        )

        self.assertEqual(buys, [(2, 10.3)])

    def test_limit_up_blocks_pending_buy_and_keeps_order_active(self):
        manager = self._manager()
        manager.add_buy_order(order_type="breakout", quantity=1, trigger_price=11.0)
        buys = []

        events = manager.process_bar(
            bar={"open": 11.0, "high": 11.0, "low": 11.0, "close": 11.0},
            prev_close=10.0,
            stock_code="600000",
            trade_date="2024-02-01",
            execute_buy=lambda quantity, price, order: buys.append((quantity, price)) or {"success": True},
            execute_sell=lambda quantity, price, order: {"success": True},
        )

        self.assertEqual(buys, [])
        self.assertEqual(events[0]["status"], "blocked")
        self.assertEqual(len(manager.active_buy_orders), 1)

    def test_stop_loss_has_priority_and_remains_active_when_sell_is_blocked(self):
        manager = self._manager()
        manager.add_exit_order(order_type="take_profit", quantity=2, trigger_price=12.0)
        manager.add_exit_order(order_type="stop_loss", quantity=2, trigger_price=9.0)
        sells = []

        events = manager.process_bar(
            bar={"open": 9.0, "high": 12.5, "low": 9.0, "close": 9.0},
            prev_close=10.0,
            stock_code="600000",
            trade_date="2024-02-01",
            execute_buy=lambda quantity, price, order: {"success": True},
            execute_sell=lambda quantity, price, order: sells.append((quantity, price, order["order_type"]))
            or {"success": False, "message": "blocked by limit down"},
        )

        self.assertEqual(sells, [])
        self.assertEqual(events[0]["order_type"], "stop_loss")
        self.assertEqual(events[0]["status"], "blocked")
        self.assertEqual(len(manager.active_exit_orders), 2)


class KLineLimitTests(unittest.TestCase):
    def test_max_training_bars_counts_visible_training_bars(self):
        data_manager = DummyDataManager(rows=160)
        start_date = data_manager.data.iloc[100]["date"].strftime("%Y-%m-%d")

        processor = KLineProcessorEnhanced(
            data_manager,
            "600000",
            start_date,
            max_training_bars=20,
        )
        progress = processor.get_progress()

        self.assertEqual(progress["total_bars"] - progress["preview_bars"], 20)
        self.assertEqual(progress["training_total_bars"], 20)
        self.assertEqual(progress["current_bar_id"], 1)



class ReportSessionIdentityTests(unittest.TestCase):
    def test_end_training_attaches_active_session_id_to_report_and_persistence(self):
        from unittest.mock import patch
        import backend.app_enhanced as app_module

        training_id = "report-session-regression"
        persisted_sessions = []

        class FakeSimulator:
            def generate_report(self, stock_code, start_date, end_date):
                return {
                    "stock_code": stock_code,
                    "initial_capital": 100000.0,
                    "final_capital": 100500.0,
                    "total_return": 0.5,
                    "total_trades": 1,
                    "trade_win_rate": 100.0,
                    "session_win_rate": 100.0,
                    "trade_details": [],
                }

        class FakeProcessor:
            @staticmethod
            def get_current_date():
                return "2026-07-10"

        app_module.active_trainings[training_id] = {
            "user": "report-session-user",
            "stock_code": "600000",
            "start_date": "2026-01-01",
            "mode": "custom",
            "trade_simulator": FakeSimulator(),
            "kline_processor": FakeProcessor(),
        }

        try:
            with patch.object(app_module.data_manager, "get_stock_name", return_value="浦发银行"), patch.object(
                app_module.user_manager,
                "save_training_session",
                side_effect=lambda username, session: persisted_sessions.append((username, session)) or True,
            ):
                response = app_module.app.test_client().post(f"/api/training/{training_id}/end")

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()["session_id"], training_id)
            self.assertEqual(persisted_sessions[0][1]["report_data"]["session_id"], training_id)
        finally:
            app_module.active_trainings.pop(training_id, None)
if __name__ == "__main__":
    unittest.main()
