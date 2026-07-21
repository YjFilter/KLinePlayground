"""Focused tests for crypto TP/SL (take-profit / stop-loss) order logic."""
from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from backend.crypto.futures_orders import FuturesOrderBook
from backend.crypto.futures_simulator import FuturesSimulator


def _make_book(balance="10000", leverage=5):
    sim = FuturesSimulator(
        initial_balance=balance, leverage=leverage,
        quantity_step="0.001", min_quantity="0.001", min_notional="5",
    )
    return FuturesOrderBook(sim), sim


T0 = datetime(2025, 1, 1, 10, 0)
T1 = datetime(2025, 1, 1, 10, 5)
T2 = datetime(2025, 1, 1, 10, 10)
T3 = datetime(2025, 1, 1, 10, 15)


class TestTpSlCreation(unittest.TestCase):
    """TP/SL child orders are created after an opening order fills."""

    def test_market_open_long_with_tp_sl(self):
        book, sim = _make_book()
        order = book.submit_order(
            action="open_long", order_type="market", timestamp=T0,
            current_price="100", margin="100", leverage=5,
            tp_price="110", sl_price="95",
        )
        self.assertEqual(order.status, "filled")
        self.assertEqual(order.tp_price, 110)
        self.assertEqual(order.sl_price, 95)
        # Two child orders should exist
        children = [o for o in book.orders if o.parent_order_id == order.order_id]
        self.assertEqual(len(children), 2)
        tp = next(o for o in children if o.order_type == "limit")
        sl = next(o for o in children if o.order_type == "breakout")
        self.assertTrue(tp.reduce_only)
        self.assertTrue(sl.reduce_only)
        self.assertEqual(tp.action, "close")
        self.assertEqual(sl.action, "close")
        self.assertEqual(tp.side, "sell")  # close long = sell
        self.assertEqual(sl.side, "sell")
        self.assertEqual(tp.limit_price, 110)
        self.assertEqual(sl.trigger_price, 95)

    def test_market_open_short_with_tp_sl(self):
        book, sim = _make_book()
        order = book.submit_order(
            action="open_short", order_type="market", timestamp=T0,
            current_price="100", margin="100", leverage=5,
            tp_price="90", sl_price="105",
        )
        children = [o for o in book.orders if o.parent_order_id == order.order_id]
        self.assertEqual(len(children), 2)
        tp = next(o for o in children if o.order_type == "limit")
        sl = next(o for o in children if o.order_type == "breakout")
        self.assertEqual(tp.side, "buy")  # close short = buy
        self.assertEqual(sl.side, "buy")
        self.assertEqual(tp.limit_price, 90)
        self.assertEqual(sl.trigger_price, 105)

    def test_tp_only(self):
        book, sim = _make_book()
        order = book.submit_order(
            action="open_long", order_type="market", timestamp=T0,
            current_price="100", margin="100", tp_price="110",
        )
        children = [o for o in book.orders if o.parent_order_id == order.order_id]
        self.assertEqual(len(children), 1)
        self.assertEqual(children[0].order_type, "limit")

    def test_sl_only(self):
        book, sim = _make_book()
        order = book.submit_order(
            action="open_long", order_type="market", timestamp=T0,
            current_price="100", margin="100", sl_price="95",
        )
        children = [o for o in book.orders if o.parent_order_id == order.order_id]
        self.assertEqual(len(children), 1)
        self.assertEqual(children[0].order_type, "breakout")

    def test_no_tp_sl_on_close(self):
        book, sim = _make_book()
        book.submit_order(
            action="open_long", order_type="market", timestamp=T0,
            current_price="100", margin="100",
        )
        with self.assertRaises(ValueError):
            book.submit_order(
                action="close", order_type="market", timestamp=T1,
                current_price="105", tp_price="110",
            )


class TestTpSlValidation(unittest.TestCase):
    """Directional validation for TP/SL prices."""

    def test_long_tp_below_entry_rejected(self):
        book, _ = _make_book()
        with self.assertRaises(ValueError):
            book.submit_order(
                action="open_long", order_type="market", timestamp=T0,
                current_price="100", margin="100", tp_price="95",
            )

    def test_long_sl_above_entry_rejected(self):
        book, _ = _make_book()
        with self.assertRaises(ValueError):
            book.submit_order(
                action="open_long", order_type="market", timestamp=T0,
                current_price="100", margin="100", sl_price="105",
            )

    def test_short_tp_above_entry_rejected(self):
        book, _ = _make_book()
        with self.assertRaises(ValueError):
            book.submit_order(
                action="open_short", order_type="market", timestamp=T0,
                current_price="100", margin="100", tp_price="105",
            )

    def test_short_sl_below_entry_rejected(self):
        book, _ = _make_book()
        with self.assertRaises(ValueError):
            book.submit_order(
                action="open_short", order_type="market", timestamp=T0,
                current_price="100", margin="100", sl_price="95",
            )


class TestTpSlTrigger(unittest.TestCase):
    """TP/SL orders trigger correctly on bar advance."""

    def test_tp_triggers_on_high(self):
        book, sim = _make_book()
        book.submit_order(
            action="open_long", order_type="market", timestamp=T0,
            current_price="100", margin="100", tp_price="110",
        )
        self.assertFalse(sim.position.is_flat)
        # Bar that reaches TP
        fills = book.process_bar(timestamp=T1, high="112", low="101", close="111", open="102")
        self.assertTrue(sim.position.is_flat)
        self.assertTrue(len(fills) > 0)
        # TP fill price should be max(open, tp) = max(102, 110) = 110
        self.assertEqual(fills[0].price, 110)

    def test_sl_triggers_on_low(self):
        book, sim = _make_book()
        book.submit_order(
            action="open_long", order_type="market", timestamp=T0,
            current_price="100", margin="100", sl_price="95",
        )
        self.assertFalse(sim.position.is_flat)
        # Bar that reaches SL
        fills = book.process_bar(timestamp=T1, high="101", low="93", close="94", open="100")
        self.assertTrue(sim.position.is_flat)
        self.assertTrue(len(fills) > 0)
        # SL fill price should be min(open, sl) = min(100, 95) = 95
        self.assertEqual(fills[0].price, 95)

    def test_tp_not_triggered_below(self):
        book, sim = _make_book()
        book.submit_order(
            action="open_long", order_type="market", timestamp=T0,
            current_price="100", margin="100", tp_price="110",
        )
        # Bar that does NOT reach TP
        fills = book.process_bar(timestamp=T1, high="108", low="99", close="105", open="100")
        self.assertFalse(sim.position.is_flat)
        self.assertEqual(len(fills), 0)


class TestTpSlOCO(unittest.TestCase):
    """One-Cancels-Other: when TP fills, SL is cancelled and vice versa."""

    def test_tp_fill_cancels_sl(self):
        book, sim = _make_book()
        order = book.submit_order(
            action="open_long", order_type="market", timestamp=T0,
            current_price="100", margin="100", tp_price="110", sl_price="95",
        )
        children = [o for o in book.orders if o.parent_order_id == order.order_id]
        self.assertEqual(len(children), 2)
        # Trigger TP
        book.process_bar(timestamp=T1, high="112", low="101", close="111", open="102")
        self.assertTrue(sim.position.is_flat)
        # SL should be cancelled
        sl = next(o for o in book.orders if o.order_type == "breakout" and o.parent_order_id == order.order_id)
        self.assertEqual(sl.status, "cancelled")
        self.assertEqual(sl.cancel_reason, "oco_sibling_filled")

    def test_sl_fill_cancels_tp(self):
        book, sim = _make_book()
        order = book.submit_order(
            action="open_long", order_type="market", timestamp=T0,
            current_price="100", margin="100", tp_price="110", sl_price="95",
        )
        # Trigger SL
        book.process_bar(timestamp=T1, high="101", low="93", close="94", open="100")
        self.assertTrue(sim.position.is_flat)
        tp = next(o for o in book.orders if o.order_type == "limit" and o.parent_order_id == order.order_id)
        self.assertEqual(tp.status, "cancelled")
        self.assertEqual(tp.cancel_reason, "oco_sibling_filled")


class TestTpSlSameBarConflict(unittest.TestCase):
    """When both TP and SL could trigger on the same bar, SL fires first (conservative)."""

    def test_sl_first_on_wide_bar(self):
        book, sim = _make_book()
        order = book.submit_order(
            action="open_long", order_type="market", timestamp=T0,
            current_price="100", margin="100", tp_price="110", sl_price="90",
        )
        # Wide bar that touches both TP and SL
        fills = book.process_bar(timestamp=T1, high="115", low="85", close="100", open="100")
        self.assertTrue(sim.position.is_flat)
        # SL should have fired (breakout processed first)
        sl = next(o for o in book.orders if o.order_type == "breakout" and o.parent_order_id == order.order_id)
        tp = next(o for o in book.orders if o.order_type == "limit" and o.parent_order_id == order.order_id)
        self.assertEqual(sl.status, "filled")
        self.assertEqual(tp.status, "cancelled")
        self.assertEqual(tp.cancel_reason, "oco_sibling_filled")


class TestTpSlManualClose(unittest.TestCase):
    """Manual close cancels orphaned TP/SL orders."""

    def test_manual_close_cancels_tp_sl(self):
        book, sim = _make_book()
        order = book.submit_order(
            action="open_long", order_type="market", timestamp=T0,
            current_price="100", margin="100", tp_price="110", sl_price="95",
        )
        self.assertFalse(sim.position.is_flat)
        # Manual close
        book.submit_order(action="close", order_type="market", timestamp=T1, current_price="105")
        self.assertTrue(sim.position.is_flat)
        # TP/SL should be cancelled
        children = [o for o in book.orders if o.parent_order_id == order.order_id]
        for child in children:
            self.assertEqual(child.status, "cancelled")


class TestTpSlPersistence(unittest.TestCase):
    """TP/SL fields survive state serialization round-trip."""

    def test_order_state_round_trip(self):
        from backend.crypto.futures_orders import FuturesOrder
        order = FuturesOrder(
            order_id="order-1", action="open_long", order_type="market",
            side="buy", quantity="0.05", margin="100", leverage=5,
            submitted_at=T0, tp_price="110", sl_price="95",
        )
        state = order.to_state()
        restored = FuturesOrder.from_state(state)
        self.assertEqual(restored.tp_price, 110)
        self.assertEqual(restored.sl_price, 95)
        self.assertIsNone(restored.parent_order_id)

    def test_child_order_state_round_trip(self):
        from backend.crypto.futures_orders import FuturesOrder
        order = FuturesOrder(
            order_id="order-2", action="close", order_type="limit",
            side="sell", quantity="0.05", margin="0", leverage=5,
            submitted_at=T0, limit_price="110", reduce_only=True,
            parent_order_id="order-1",
        )
        state = order.to_state()
        restored = FuturesOrder.from_state(state)
        self.assertEqual(restored.parent_order_id, "order-1")
        self.assertTrue(restored.reduce_only)
        self.assertEqual(restored.limit_price, 110)


if __name__ == "__main__":
    unittest.main()
