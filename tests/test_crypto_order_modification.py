"""Tests for modifying active futures orders and TP/SL prices."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from decimal import Decimal

from backend.app_enhanced import app, active_trainings
from backend.crypto.futures_engine import FuturesEngine
from backend.crypto.futures_models import FuturesAccount, FuturesPosition
from backend.crypto.futures_orders import FuturesOrder, FuturesOrderBook
from backend.crypto.futures_simulator import FuturesSimulator


class CryptoOrderModificationTests(unittest.TestCase):
    def setUp(self):
        self.simulator = FuturesSimulator(
            initial_balance=Decimal("10000"),
            quantity_step="0.001",
            min_quantity="0.001",
            min_notional="5",
            leverage=10,
        )
        self.order_book = FuturesOrderBook(simulator=self.simulator)
        self.engine = FuturesEngine(simulator=self.simulator, order_book=self.order_book)
        self.now = datetime(2024, 7, 1, 12, 0, tzinfo=timezone.utc)

    def test_modify_limit_order_price(self):
        order = self.order_book.submit_order(
            action="open_long",
            order_type="limit",
            timestamp=self.now,
            current_price=Decimal("60000"),
            margin=Decimal("100"),
            limit_price=Decimal("59000"),
        )
        self.assertEqual(order.limit_price, Decimal("59000"))

        updated = self.order_book.modify_order_price(order.order_id, 59500)
        self.assertIsNotNone(updated)
        self.assertEqual(updated.limit_price, Decimal("59500"))

    def test_modify_breakout_order_trigger_price(self):
        order = self.order_book.submit_order(
            action="open_long",
            order_type="breakout",
            timestamp=self.now,
            current_price=Decimal("60000"),
            margin=Decimal("100"),
            trigger_price=Decimal("62000"),
        )
        self.assertEqual(order.trigger_price, Decimal("62000"))

        updated = self.order_book.modify_order_price(order.order_id, Decimal("63000"))
        self.assertIsNotNone(updated)
        self.assertEqual(updated.trigger_price, Decimal("63000"))

    def test_modify_tpsl_child_orders(self):
        # First open a position
        self.order_book.submit_order(
            action="open_long",
            order_type="market",
            timestamp=self.now,
            current_price=Decimal("60000"),
            margin=Decimal("100"),
            tp_price=Decimal("64000"),
            sl_price=Decimal("58000"),
        )
        self.assertEqual(len(self.order_book.active_orders), 2)
        tp_order = next((o for o in self.order_book.active_orders if o.protection_type == "tp"), None)
        sl_order = next((o for o in self.order_book.active_orders if o.protection_type == "sl"), None)
        self.assertIsNotNone(tp_order)
        self.assertIsNotNone(sl_order)

        # Modify TP price
        updated_tp = self.order_book.modify_order_price(tp_order.order_id, 65500)
        self.assertEqual(updated_tp.limit_price, Decimal("65500"))
        self.assertEqual(updated_tp.tp_price, Decimal("65500"))

        # Modify SL price
        updated_sl = self.order_book.modify_order_price(sl_order.order_id, 57200)
        self.assertEqual(updated_sl.trigger_price, Decimal("57200"))
        self.assertEqual(updated_sl.sl_price, Decimal("57200"))

    def test_modify_invalid_order_or_price(self):
        order = self.order_book.submit_order(
            action="open_long",
            order_type="limit",
            timestamp=self.now,
            current_price=Decimal("60000"),
            margin=Decimal("100"),
            limit_price=Decimal("59000"),
        )
        # Invalid price <= 0
        with self.assertRaises(ValueError):
            self.order_book.modify_order_price(order.order_id, 0)
        with self.assertRaises(ValueError):
            self.order_book.modify_order_price(order.order_id, -100)

        # Non-existent order
        self.assertIsNone(self.order_book.modify_order_price("non-existent-id", 60000))

        # Cancelled order
        self.order_book.cancel_order(order.order_id, self.now)
        self.assertIsNone(self.order_book.modify_order_price(order.order_id, 62000))

    def test_api_modify_pending_order(self):
        client = app.test_client()

        # 1. Missing training -> 404
        res = client.put("/api/training/non-existent-session/orders/ord-1", json={"price": 60000})
        self.assertEqual(res.status_code, 404)

        # 2. Mock crypto training session
        order = self.order_book.submit_order(
            action="open_long",
            order_type="limit",
            timestamp=self.now,
            current_price=Decimal("60000"),
            margin=Decimal("100"),
            limit_price=Decimal("59000"),
        )

        class MockSession:
            class MockClock:
                current_time = datetime(2024, 7, 1, 12, 0, tzinfo=timezone.utc)
                active_period = type("Period", (), {"value": "5m"})
                def has_next(self): return True
            clock = MockClock()

        class MockExecutor:
            def __init__(self, engine):
                self.engine = engine
                self.symbol = "BTCUSDT"
                self.source = "binance"
                self.clock = MockSession.MockClock()
                self._trade_bars = {self.clock.current_time: {"close": Decimal("60000")}}
            def snapshot(self):
                sim = self.engine.simulator.snapshot()
                return {
                    "account": sim["account"],
                    "position": sim["position"],
                    "pending_orders": [o.to_dict() for o in self.engine.order_book.active_orders],
                    "fills": [],
                    "trade_markers": [],
                    "equity_curve": [],
                }
            def export_state(self):
                return {"version": 1}

        import uuid
        training_id = f"test-modify-session-{uuid.uuid4().hex[:8]}"
        active_trainings[training_id] = {
            "id": training_id,
            "market_type": "crypto_perpetual",
            "symbol": "BTCUSDT",
            "stock_code": "BTCUSDT",
            "stock_name": "BTC/USDT",
            "source": "binance",
            "start_date": "2024-07-01",
            "end_date": "2024-07-31",
            "training_start": "2024-07-01 00:00:00",
            "training_end": "2024-07-31 23:59:00",
            "initial_capital": 100000,
            "futures_executor": MockExecutor(self.engine),
            "crypto_session": MockSession(),
            "user": "test_user",
        }

        from backend.app_enhanced import user_manager
        user_manager.history_manager.start_training_session(
            "test_user",
            {
                "session_id": training_id,
                "stock_code": "BTCUSDT",
                "stock_name": "BTC/USDT",
                "start_date": "2024-07-01",
                "end_date": "2024-07-31",
                "mode": "specified",
                "initial_capital": 100000,
                "market_type": "crypto_perpetual",
                "status": "active",
            },
        )

        # 3. Missing price -> 400
        res = client.put(f"/api/training/{training_id}/orders/{order.order_id}", json={})
        self.assertEqual(res.status_code, 400)

        # 4. Modify price via PUT -> 200
        res = client.put(f"/api/training/{training_id}/orders/{order.order_id}", json={"price": 59500})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["order"]["limit_price"], 59500)

        # 5. Modify price via POST /modify -> 200
        res = client.post(f"/api/training/{training_id}/orders/{order.order_id}/modify", json={"price": 58500})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["order"]["limit_price"], 58500)

        # Clean up
        active_trainings.pop(training_id, None)


if __name__ == "__main__":
    unittest.main()
