from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from backend.crypto.futures_engine import FuturesEngine
from backend.crypto.futures_orders import FuturesOrderBook
from backend.crypto.futures_simulator import FuturesSimulator
from backend.crypto.models import FundingEvent


UTC = timezone.utc


class FuturesEngineTests(unittest.TestCase):
    def make_engine(self, balance="1000"):
        simulator = FuturesSimulator(
            initial_balance=balance,
            quantity_step="0.001",
            min_quantity="0.001",
            min_notional="5",
            leverage=5,
            maintenance_margin_rate="0.005",
        )
        orders = FuturesOrderBook(simulator)
        return simulator, orders, FuturesEngine(simulator, orders, liquidation_fee_rate="0.005")

    def funding(self, timestamp, rate, mark="100"):
        return FundingEvent(source="binance", symbol="BTCUSDT", timestamp=timestamp, rate=Decimal(rate), mark_price=Decimal(mark))

    def test_positive_negative_funding_signs_flat_noop_and_duplicate_protection(self):
        timestamp = datetime(2024, 1, 1, 8, tzinfo=UTC)
        simulator, _, engine = self.make_engine()
        flat = engine.settle_funding(self.funding(timestamp, "0.001"))
        self.assertEqual(flat.status, "skipped_flat")
        self.assertEqual(flat.transfer, Decimal("0"))

        simulator.open_long(margin="100", price="100", timestamp=timestamp - timedelta(minutes=5))
        paid = engine.settle_funding(self.funding(timestamp + timedelta(hours=8), "0.001"))
        self.assertEqual(paid.transfer, Decimal("-0.500000"))
        self.assertEqual(simulator.account.funding_paid, Decimal("0.500000"))
        self.assertIsNone(engine.settle_funding(self.funding(timestamp + timedelta(hours=8), "0.001")))

        received = engine.settle_funding(self.funding(timestamp + timedelta(hours=16), "-0.001"))
        self.assertEqual(received.transfer, Decimal("0.500000"))
        self.assertEqual(simulator.account.funding_received, Decimal("0.500000"))

        short_simulator, _, short_engine = self.make_engine()
        short_simulator.open_short(margin="100", price="100", timestamp=timestamp)
        short_received = short_engine.settle_funding(self.funding(timestamp + timedelta(hours=8), "0.001"))
        self.assertEqual(short_received.transfer, Decimal("0.500000"))

    def test_solved_long_and_short_liquidation_prices_use_mark_extremes(self):
        timestamp = datetime(2024, 1, 1, tzinfo=UTC)
        long_simulator, _, long_engine = self.make_engine()
        long_simulator.open_long(margin="100", price="100", timestamp=timestamp)
        long_price = long_engine.liquidation_price()
        self.assertEqual(long_price.quantize(Decimal("0.000001")), Decimal("80.808081"))
        self.assertIsNone(long_engine.check_liquidation(timestamp=timestamp, mark_low="81", mark_high="120"))
        long_event = long_engine.check_liquidation(timestamp=timestamp, mark_low="80", mark_high="120")
        self.assertEqual(long_event.price, long_price)
        self.assertEqual(long_event.side, "long")
        self.assertTrue(long_simulator.position.is_flat)

        short_simulator, _, short_engine = self.make_engine()
        short_simulator.open_short(margin="100", price="100", timestamp=timestamp)
        short_price = short_engine.liquidation_price()
        self.assertEqual(short_price.quantize(Decimal("0.000001")), Decimal("118.811881"))
        self.assertIsNone(short_engine.check_liquidation(timestamp=timestamp, mark_low="80", mark_high="118"))
        short_event = short_engine.check_liquidation(timestamp=timestamp, mark_low="80", mark_high="119")
        self.assertEqual(short_event.side, "short")
        self.assertTrue(short_simulator.position.is_flat)

    def test_liquidation_has_priority_applies_fee_cancels_orders_and_keeps_equity_nonnegative(self):
        timestamp = datetime(2024, 1, 1, tzinfo=UTC)
        simulator, orders, engine = self.make_engine()
        orders.submit_order(action="open_long", order_type="market", margin="99", leverage=5, timestamp=timestamp, current_price="100")
        pending = orders.submit_order(action="close", order_type="limit", limit_price="90", timestamp=timestamp, current_price="100")
        result = engine.process_bar(
            timestamp=timestamp + timedelta(minutes=5),
            trade_bar={"high": "110", "low": "80", "close": "90"},
            mark_bar={"high": "110", "low": "80", "close": "90"},
            funding_events=[],
        )
        self.assertEqual(len(result["liquidations"]), 1)
        self.assertEqual(result["fills"], [])
        self.assertEqual(pending.status, "cancelled")
        self.assertGreater(simulator.account.liquidation_fees, Decimal("0"))
        self.assertGreaterEqual(result["equity"], Decimal("0"))

    def test_funding_can_trigger_liquidation_before_orders(self):
        timestamp = datetime(2024, 1, 1, tzinfo=UTC)
        simulator, orders, engine = self.make_engine(balance="100")
        orders.submit_order(action="open_long", order_type="market", margin="99", leverage=5, timestamp=timestamp, current_price="100")
        result = engine.process_bar(
            timestamp=timestamp + timedelta(hours=8),
            trade_bar={"high": "101", "low": "99", "close": "100"},
            mark_bar={"high": "101", "low": "99", "close": "100"},
            funding_events=[self.funding(timestamp + timedelta(hours=8), "0.25")],
        )
        self.assertEqual(len(result["funding"]), 1)
        self.assertEqual(len(result["liquidations"]), 1)
        self.assertGreaterEqual(result["equity"], Decimal("0"))


if __name__ == "__main__":
    unittest.main()
