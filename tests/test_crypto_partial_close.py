"""Tests for crypto futures partial position closing."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import unittest

from backend.crypto.futures_simulator import FuturesSimulator
from backend.crypto.futures_orders import FuturesOrderBook


class CryptoPartialCloseTests(unittest.TestCase):
    def setUp(self):
        self.simulator = FuturesSimulator(
            initial_balance=10000,
            quantity_step=Decimal("0.001"),
            min_quantity=Decimal("0.001"),
            min_notional=Decimal("5"),
            leverage=10,
        )
        self.order_book = FuturesOrderBook(
            self.simulator,
            maker_fee_rate=Decimal("0.0002"),
            taker_fee_rate=Decimal("0.0005"),
        )
        self.now = datetime(2024, 7, 1, 0, 0, 0, tzinfo=timezone.utc)

    def test_market_open_and_partial_close_by_margin(self):
        # 1. Open long with 100 USDT margin at price 60,000 (10x leverage -> 1000 USDT notional, 0.016 BTC with 0.001 step, margin ~96 USDT)
        open_order = self.order_book.submit_order(
            action="open_long",
            order_type="market",
            timestamp=self.now,
            current_price=60000,
            margin=100,
        )
        self.assertEqual(open_order.status, "filled")
        pos = self.simulator.position
        self.assertFalse(pos.is_flat)
        self.assertAlmostEqual(float(pos.isolated_margin), 96.0, places=2)
        total_qty = pos.absolute_quantity
        self.assertEqual(total_qty, Decimal("0.016"))

        # 2. Market close 50% by specifying margin=48 at price 66,000 (+10% gain)
        close_order = self.order_book.submit_order(
            action="close",
            order_type="market",
            timestamp=self.now,
            current_price=66000,
            margin=48,
        )
        self.assertEqual(close_order.status, "filled")
        
        # Position should still exist with 50% remaining quantity (0.008 BTC) and ~48 USDT margin
        pos_after = self.simulator.position
        self.assertFalse(pos_after.is_flat)
        self.assertAlmostEqual(float(pos_after.isolated_margin), 48.0, places=2)
        self.assertEqual(pos_after.absolute_quantity, Decimal("0.008"))
        self.assertEqual(pos_after.entry_price, Decimal("60000"))

        # 3. Market close remaining 100% (or margin >= remaining margin)
        close_remaining = self.order_book.submit_order(
            action="close",
            order_type="market",
            timestamp=self.now,
            current_price=66000,
            margin=50,  # More than remaining 48 margin -> closes remaining 100%
        )
        self.assertEqual(close_remaining.status, "filled")
        self.assertTrue(self.simulator.position.is_flat)
        self.assertEqual(self.simulator.position.isolated_margin, Decimal("0"))

    def test_partial_close_by_explicit_quantity(self):
        # Open short with 200 USDT margin at price 60,000
        self.order_book.submit_order(
            action="open_short",
            order_type="market",
            timestamp=self.now,
            current_price=60000,
            margin=200,
        )
        pos = self.simulator.position
        self.assertFalse(pos.is_flat)
        initial_qty = pos.absolute_quantity

        # Partially close 0.01 BTC
        close_order = self.order_book.submit_order(
            action="close",
            order_type="market",
            timestamp=self.now,
            current_price=58000,
            quantity=Decimal("0.01"),
        )
        self.assertEqual(close_order.status, "filled")
        self.assertEqual(self.simulator.position.absolute_quantity, initial_qty - Decimal("0.01"))

    def test_partial_limit_close_order(self):
        # Open long 100 USDT margin at price 60,000
        self.order_book.submit_order(
            action="open_long",
            order_type="market",
            timestamp=self.now,
            current_price=60000,
            margin=100,
        )
        total_qty = self.simulator.position.absolute_quantity

        # Place limit order to close 50% at 65,000
        limit_close = self.order_book.submit_order(
            action="close",
            order_type="limit",
            timestamp=self.now,
            current_price=60000,
            limit_price=65000,
            margin=48,
        )
        self.assertEqual(limit_close.status, "active")
        self.assertEqual(limit_close.quantity, Decimal("0.008"))


if __name__ == "__main__":
    unittest.main()
