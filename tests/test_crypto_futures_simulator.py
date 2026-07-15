from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from decimal import Decimal

from backend.crypto.futures_models import FuturesAccount, FuturesFill, FuturesPosition
from backend.crypto.futures_simulator import FuturesSimulator


UTC = timezone.utc


class FuturesSimulatorTests(unittest.TestCase):
    def make_simulator(self, **overrides):
        settings = {
            "initial_balance": "10000",
            "quantity_step": "0.001",
            "min_quantity": "0.001",
            "min_notional": "5",
            "leverage": 5,
            "maintenance_margin_rate": "0.005",
        }
        settings.update(overrides)
        return FuturesSimulator(**settings)

    def test_account_and_position_models_are_decimal_safe_and_json_serializable(self):
        account = FuturesAccount(initial_balance=Decimal("10000"), balance=Decimal("9999.5"))
        position = FuturesPosition(quantity=Decimal("0.125"), entry_price=Decimal("64000"), leverage=5)
        fill = FuturesFill(
            fill_id="fill-1",
            order_id="order-1",
            action="open_long",
            side="buy",
            quantity=Decimal("0.125"),
            price=Decimal("64000"),
            fee=Decimal("4"),
            fee_type="taker",
            timestamp=datetime(2024, 1, 1, tzinfo=UTC),
        )
        self.assertEqual(position.side, "long")
        self.assertEqual(account.available_balance, Decimal("9999.5"))
        json.dumps(account.to_dict())
        json.dumps(position.to_dict(mark_price=Decimal("65000")))
        json.dumps(fill.to_dict())

    def test_leverage_validation_and_changes_only_while_flat(self):
        for leverage in (0, 21, Decimal("1.5")):
            with self.assertRaises(ValueError):
                self.make_simulator(leverage=leverage)
        simulator = self.make_simulator()
        simulator.set_leverage(20)
        self.assertEqual(simulator.leverage, 20)
        simulator.open_long(margin="100", price="100", timestamp=datetime(2024, 1, 1, tzinfo=UTC))
        with self.assertRaisesRegex(ValueError, "flat"):
            simulator.set_leverage(10)

    def test_margin_to_quantity_rounds_down_and_enforces_minimums(self):
        simulator = self.make_simulator()
        self.assertEqual(simulator.margin_to_quantity("100", "5", "123.45"), Decimal("4.050"))
        with self.assertRaisesRegex(ValueError, "minimum quantity"):
            simulator.margin_to_quantity("0.01", "1", "100")
        with self.assertRaisesRegex(ValueError, "minimum notional"):
            self.make_simulator(min_quantity="0.001", min_notional="50").margin_to_quantity("1", "5", "10")

    def test_long_and_short_unrealized_pnl_equity_and_margin_metrics(self):
        simulator = self.make_simulator()
        simulator.open_long(margin="1000", price="100", timestamp=datetime(2024, 1, 1, tzinfo=UTC))
        self.assertEqual(simulator.position.quantity, Decimal("50.000"))
        self.assertEqual(simulator.unrealized_pnl("110"), Decimal("500.000"))
        self.assertEqual(simulator.equity("110"), Decimal("10500.000"))
        self.assertEqual(simulator.maintenance_margin("110"), Decimal("27.500000"))
        self.assertEqual(simulator.margin_ratio("110").quantize(Decimal("0.0001")), Decimal("1.8333"))

        short = self.make_simulator()
        short.open_short(margin="1000", price="100", timestamp=datetime(2024, 1, 1, tzinfo=UTC))
        self.assertEqual(short.unrealized_pnl("90"), Decimal("500.000"))
        self.assertEqual(short.unrealized_pnl("110"), Decimal("-500.000"))

    def test_average_price_partial_close_full_close_and_reversal(self):
        simulator = self.make_simulator()
        timestamp = datetime(2024, 1, 1, tzinfo=UTC)
        simulator.apply_quantity("buy", "10", "100", timestamp=timestamp)
        simulator.apply_quantity("buy", "10", "120", timestamp=timestamp)
        self.assertEqual(simulator.position.entry_price, Decimal("110"))

        partial = simulator.apply_quantity("sell", "5", "130", timestamp=timestamp)
        self.assertEqual(partial.realized_pnl, Decimal("100"))
        self.assertEqual(simulator.position.quantity, Decimal("15"))
        self.assertEqual(simulator.position.entry_price, Decimal("110"))

        reversal = simulator.apply_quantity("sell", "20", "90", timestamp=timestamp)
        self.assertEqual(reversal.realized_pnl, Decimal("-300"))
        self.assertEqual(simulator.position.quantity, Decimal("-5"))
        self.assertEqual(simulator.position.entry_price, Decimal("90"))

        closed = simulator.close(price="80", timestamp=timestamp)
        self.assertEqual(closed.realized_pnl, Decimal("50"))
        self.assertTrue(simulator.position.is_flat)
        self.assertEqual(simulator.account.realized_pnl, Decimal("-150"))


if __name__ == "__main__":
    unittest.main()
