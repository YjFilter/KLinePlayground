from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from backend.crypto.futures_orders import FuturesOrderBook
from backend.crypto.futures_simulator import FuturesSimulator


UTC = timezone.utc


class FuturesOrderBookTests(unittest.TestCase):
    def make_book(self, balance="10000"):
        simulator = FuturesSimulator(
            initial_balance=balance,
            quantity_step="0.001",
            min_quantity="0.001",
            min_notional="5",
            leverage=5,
        )
        return simulator, FuturesOrderBook(simulator, maker_fee_rate="0.0002", taker_fee_rate="0.0005")

    def test_market_open_long_short_and_close_use_current_close_and_taker_fee(self):
        timestamp = datetime(2024, 1, 1, 0, 5, tzinfo=UTC)
        simulator, book = self.make_book()
        order = book.submit_order(
            action="open_long", order_type="market", margin="1000", leverage=5,
            timestamp=timestamp, current_price="100",
        )
        fill = book.fills[-1]
        self.assertEqual(order.status, "filled")
        self.assertEqual(fill.timestamp, timestamp)
        self.assertEqual(fill.price, Decimal("100"))
        self.assertEqual(fill.fee, Decimal("2.5000000"))
        self.assertEqual(simulator.position.quantity, Decimal("50.000"))

        close = book.submit_order(
            action="close", order_type="market", timestamp=timestamp,
            current_price="110",
        )
        self.assertTrue(close.reduce_only)
        self.assertTrue(simulator.position.is_flat)

        short = book.submit_order(
            action="open_short", order_type="market", margin="500", leverage=5,
            timestamp=timestamp, current_price="100",
        )
        self.assertEqual(short.status, "filled")
        self.assertEqual(simulator.position.side, "short")

    def test_limit_orders_wait_for_a_subsequent_bar_and_fill_at_limit_with_maker_fee(self):
        submitted_at = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
        later = submitted_at + timedelta(minutes=5)
        simulator, book = self.make_book()
        order = book.submit_order(
            action="open_long", order_type="limit", margin="100", leverage=5,
            limit_price="99", timestamp=submitted_at, current_price="100",
        )
        self.assertEqual(book.process_bar(timestamp=submitted_at, high="101", low="98", close="100"), [])
        fills = book.process_bar(timestamp=later, high="101", low="98", close="100")
        self.assertEqual(len(fills), 1)
        self.assertEqual(fills[0].price, Decimal("99"))
        self.assertEqual(fills[0].timestamp, later)
        self.assertEqual(fills[0].fee_type, "maker")
        self.assertEqual(order.status, "filled")
        self.assertEqual(simulator.position.entry_price, Decimal("99"))

    def test_breakout_buy_waits_for_a_later_bar_and_fills_at_trigger_with_taker_fee(self):
        submitted_at = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
        later = submitted_at + timedelta(minutes=5)
        simulator, book = self.make_book()
        order = book.submit_order(
            action="open_long", order_type="breakout", margin="100", leverage=5,
            trigger_price="105", timestamp=submitted_at, current_price="100",
        )

        self.assertEqual(
            book.process_bar(timestamp=submitted_at, open="106", high="108", low="104", close="107"),
            [],
        )
        fills = book.process_bar(timestamp=later, open="106", high="108", low="104", close="107")

        self.assertEqual(len(fills), 1)
        self.assertEqual(fills[0].price, Decimal("105"))
        self.assertEqual(fills[0].fee_type, "taker")
        self.assertEqual(order.status, "filled")
        self.assertEqual(simulator.position.entry_price, Decimal("105"))

    def test_breakout_sell_and_reduce_only_close_use_mirrored_trigger_rules(self):
        submitted_at = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
        later = submitted_at + timedelta(minutes=5)
        simulator, book = self.make_book()
        short = book.submit_order(
            action="open_short", order_type="breakout", margin="100", leverage=5,
            trigger_price="95", timestamp=submitted_at, current_price="100",
        )
        fills = book.process_bar(timestamp=later, open="94", high="97", low="92", close="93")
        self.assertEqual(fills[0].price, Decimal("95"))
        self.assertEqual(short.status, "filled")
        self.assertEqual(simulator.position.side, "short")

        close = book.submit_order(
            action="close", order_type="breakout", trigger_price="100",
            timestamp=later, current_price="94",
        )
        fills = book.process_bar(
            timestamp=later + timedelta(minutes=5), open="101", high="103", low="98", close="102",
            reduce_only=True,
        )
        self.assertEqual(fills[0].price, Decimal("100"))
        self.assertTrue(close.reduce_only)
        self.assertTrue(simulator.position.is_flat)

    def test_breakout_trigger_price_survives_order_book_state_round_trip(self):
        timestamp = datetime(2024, 1, 1, tzinfo=UTC)
        simulator, book = self.make_book()
        order = book.submit_order(
            action="open_long", order_type="breakout", margin="100", leverage=5,
            trigger_price="105", timestamp=timestamp, current_price="100",
        )

        restored = FuturesOrderBook.from_state(simulator, book.to_state())

        self.assertEqual(restored.orders[0].order_type, "breakout")
        self.assertEqual(restored.orders[0].trigger_price, Decimal("105"))
        self.assertEqual(restored.orders[0].order_id, order.order_id)

    def test_limit_crossing_is_side_specific_and_close_is_reduce_only(self):
        timestamp = datetime(2024, 1, 1, tzinfo=UTC)
        simulator, book = self.make_book()
        short_order = book.submit_order(
            action="open_short", order_type="limit", margin="100", leverage=5,
            limit_price="105", timestamp=timestamp, current_price="100",
        )
        self.assertEqual(book.process_bar(timestamp=timestamp + timedelta(minutes=5), high="104", low="90", close="100"), [])
        self.assertEqual(len(book.process_bar(timestamp=timestamp + timedelta(minutes=10), high="105", low="90", close="100")), 1)
        self.assertEqual(short_order.status, "filled")

        close_order = book.submit_order(
            action="close", order_type="limit", limit_price="95",
            timestamp=timestamp + timedelta(minutes=10), current_price="100",
        )
        self.assertTrue(close_order.reduce_only)
        book.process_bar(timestamp=timestamp + timedelta(minutes=15), high="100", low="95", close="97", reduce_only=True)
        self.assertTrue(simulator.position.is_flat)

    def test_cancel_reversal_precision_and_insufficient_margin(self):
        timestamp = datetime(2024, 1, 1, tzinfo=UTC)
        simulator, book = self.make_book(balance="100")
        pending = book.submit_order(
            action="open_long", order_type="limit", margin="10", leverage=5,
            limit_price="123.45", timestamp=timestamp, current_price="125",
        )
        self.assertEqual(pending.quantity, Decimal("0.405"))
        self.assertTrue(book.cancel_order(pending.order_id, timestamp + timedelta(minutes=1)))
        self.assertEqual(pending.status, "cancelled")
        self.assertFalse(book.cancel_order(pending.order_id, timestamp + timedelta(minutes=2)))

        with self.assertRaisesRegex(ValueError, "insufficient"):
            book.submit_order(
                action="open_long", order_type="market", margin="101", leverage=5,
                timestamp=timestamp, current_price="100",
            )

        simulator, book = self.make_book()
        book.submit_order(action="open_long", order_type="market", margin="100", leverage=5, timestamp=timestamp, current_price="100")
        book.submit_order(action="open_short", order_type="market", margin="200", leverage=5, timestamp=timestamp, current_price="100")
        self.assertEqual(simulator.position.quantity, Decimal("-5.000"))
        self.assertEqual(simulator.position.entry_price, Decimal("100"))

    def test_leverage_changes_require_flat_position_and_no_active_orders(self):
        timestamp = datetime(2024, 1, 1, tzinfo=UTC)
        simulator, book = self.make_book()
        pending = book.submit_order(
            action="open_long", order_type="limit", margin="100", leverage=10,
            limit_price="90", timestamp=timestamp, current_price="100",
        )
        self.assertEqual(simulator.leverage, 10)
        with self.assertRaisesRegex(ValueError, "leverage"):
            book.submit_order(
                action="open_short", order_type="limit", margin="100", leverage=5,
                limit_price="110", timestamp=timestamp, current_price="100",
            )
        book.cancel_order(pending.order_id, timestamp)
        book.submit_order(action="open_long", order_type="market", margin="100", leverage=10, timestamp=timestamp, current_price="100")
        with self.assertRaisesRegex(ValueError, "leverage"):
            book.submit_order(action="open_long", order_type="market", margin="100", leverage=5, timestamp=timestamp, current_price="100")

    def test_opposite_order_reduces_with_zero_available_and_only_checks_reversal_excess(self):
        timestamp = datetime(2024, 1, 1, tzinfo=UTC)
        simulator, book = self.make_book(balance="100")
        simulator.open_long(margin="100", price="100", timestamp=timestamp)
        self.assertEqual(simulator.account.available_balance, Decimal("0"))
        order = book.submit_order(
            action="open_short", order_type="market", margin="100", leverage=5,
            timestamp=timestamp, current_price="100",
        )
        self.assertEqual(order.status, "filled")
        self.assertTrue(simulator.position.is_flat)
        self.assertEqual(book.fills[-1].action, "close")

        simulator, book = self.make_book(balance="100")
        simulator.open_long(margin="100", price="100", timestamp=timestamp)
        reversal = book.submit_order(
            action="open_short", order_type="market", margin="200", leverage=5,
            timestamp=timestamp, current_price="100",
        )
        self.assertEqual(reversal.status, "partially_filled")
        self.assertEqual(reversal.cancel_reason, "insufficient_margin_for_reversal")
        self.assertEqual(reversal.reserved_margin, Decimal("0"))
        self.assertTrue(simulator.position.is_flat)

    def test_successful_reversal_emits_close_then_open_fills(self):
        timestamp = datetime(2024, 1, 1, tzinfo=UTC)
        simulator, book = self.make_book(balance="300")
        simulator.open_long(margin="100", price="100", timestamp=timestamp)
        book.submit_order(
            action="open_short", order_type="market", margin="200", leverage=5,
            timestamp=timestamp, current_price="110",
        )
        self.assertEqual([fill.action for fill in book.fills], ["close", "open_short"])
        self.assertEqual(book.fills[0].realized_pnl, Decimal("50.000"))
        self.assertEqual(simulator.position.side, "short")

    def test_opening_margin_includes_fees_and_preserves_account_invariants(self):
        timestamp = datetime(2024, 1, 1, tzinfo=UTC)
        simulator, book = self.make_book(balance="100")
        with self.assertRaisesRegex(ValueError, "fee|margin"):
            book.submit_order(
                action="open_long", order_type="market", margin="100", leverage=5,
                timestamp=timestamp, current_price="100",
            )
        book.submit_order(
            action="open_long", order_type="market", margin="99", leverage=5,
            timestamp=timestamp, current_price="100",
        )
        self.assertLessEqual(simulator.account.used_margin, simulator.account.balance)

    def test_max_open_margin_rounds_down_and_can_be_submitted(self):
        timestamp = datetime(2024, 1, 1, tzinfo=UTC)
        simulator, book = self.make_book(balance="100")
        maximum = book.max_open_margin(order_type="market", leverage=5)
        self.assertEqual(maximum, Decimal("99.75"))
        order = book.submit_order(
            action="open_long", order_type="market", margin=maximum, leverage=5,
            timestamp=timestamp, current_price="100",
        )
        self.assertEqual(order.margin, Decimal("99.75"))
        self.assertLessEqual(simulator.account.used_margin, simulator.account.balance)

    def test_multiple_stale_reduce_only_orders_cancel_silently_with_reason(self):
        timestamp = datetime(2024, 1, 1, tzinfo=UTC)
        simulator, book = self.make_book()
        simulator.open_long(margin="100", price="100", timestamp=timestamp)
        first = book.submit_order(action="close", order_type="limit", limit_price="105", timestamp=timestamp, current_price="100")
        second = book.submit_order(action="close", order_type="limit", limit_price="105", timestamp=timestamp, current_price="100")
        fills = book.process_bar(timestamp=timestamp + timedelta(minutes=5), high="106", low="99", close="105", reduce_only=True)
        self.assertEqual(len(fills), 1)
        self.assertEqual(first.status, "filled")
        self.assertEqual(second.status, "cancelled")
        self.assertEqual(second.cancel_reason, "position_flat")


if __name__ == "__main__":
    unittest.main()
