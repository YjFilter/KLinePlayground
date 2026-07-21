from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pandas as pd

from backend.crypto.futures_engine import FuturesEngine
from backend.crypto.futures_orders import FuturesOrderBook
from backend.crypto.futures_simulator import FuturesSimulator
from backend.crypto.session import CryptoReplaySession
from backend.crypto.trading import FuturesReplayExecutor


UTC = timezone.utc
SUBMITTED_AT = datetime(2025, 1, 1, tzinfo=UTC)


class CryptoBreakoutOrderTests(unittest.TestCase):
    def make_book(self):
        simulator = FuturesSimulator(
            initial_balance='10000',
            quantity_step='0.001',
            min_quantity='0.001',
            min_notional='5',
            leverage=5,
        )
        return simulator, FuturesOrderBook(
            simulator,
            maker_fee_rate='0.0002',
            taker_fee_rate='0.0005',
        )

    def test_open_orders_use_strict_direction_and_deterministic_fill_prices(self):
        cases = (
            ('limit', 'open_long', '98', '105', '95', '99', '99', 'maker'),
            ('limit', 'open_short', '102', '105', '95', '101', '101', 'maker'),
            ('breakout', 'open_long', '102', '105', '95', '101', '101', 'taker'),
            ('breakout', 'open_short', '98', '105', '95', '99', '99', 'taker'),
        )

        for order_type, action, opening, high, low, trigger, expected_price, fee_type in cases:
            with self.subTest(order_type=order_type, action=action):
                simulator, book = self.make_book()
                price_args = (
                    {'limit_price': trigger}
                    if order_type == 'limit'
                    else {'trigger_price': trigger}
                )
                order = book.submit_order(
                    action=action,
                    order_type=order_type,
                    margin='100',
                    leverage=5,
                    timestamp=SUBMITTED_AT,
                    current_price='100',
                    **price_args,
                )

                same_bar_fills = book.process_bar(
                    timestamp=SUBMITTED_AT,
                    open=opening,
                    high=high,
                    low=low,
                    close='100',
                )
                self.assertEqual(same_bar_fills, [])
                self.assertEqual(order.status, 'active')

                fills = book.process_bar(
                    timestamp=SUBMITTED_AT + timedelta(minutes=5),
                    open=opening,
                    high=high,
                    low=low,
                    close='100',
                )
                self.assertEqual(len(fills), 1)
                self.assertEqual(fills[0].price, Decimal(expected_price))
                self.assertEqual(fills[0].fee_type, fee_type)
                self.assertEqual(order.status, 'filled')
                self.assertFalse(simulator.position.is_flat)

    def test_limit_and_breakout_orders_can_close_long_and_short_positions(self):
        cases = (
            ('long', 'limit', '107', '108', '104', '105', '105', 'maker'),
            ('long', 'breakout', '93', '96', '92', '95', '95', 'taker'),
            ('short', 'limit', '93', '96', '92', '95', '95', 'maker'),
            ('short', 'breakout', '107', '108', '104', '105', '105', 'taker'),
        )

        for position_side, order_type, opening, high, low, trigger, expected_price, fee_type in cases:
            with self.subTest(position_side=position_side, order_type=order_type):
                simulator, book = self.make_book()
                if position_side == 'long':
                    simulator.open_long(margin='100', price='100', timestamp=SUBMITTED_AT)
                else:
                    simulator.open_short(margin='100', price='100', timestamp=SUBMITTED_AT)

                price_args = (
                    {'limit_price': trigger}
                    if order_type == 'limit'
                    else {'trigger_price': trigger}
                )
                order = book.submit_order(
                    action='close',
                    order_type=order_type,
                    timestamp=SUBMITTED_AT,
                    current_price='100',
                    **price_args,
                )
                self.assertTrue(order.reduce_only)

                fills = book.process_bar(
                    timestamp=SUBMITTED_AT + timedelta(minutes=5),
                    open=opening,
                    high=high,
                    low=low,
                    close='100',
                    reduce_only=True,
                )
                self.assertEqual(len(fills), 1)
                self.assertEqual(fills[0].price, Decimal(expected_price))
                self.assertEqual(fills[0].fee_type, fee_type)
                self.assertTrue(simulator.position.is_flat)

    def test_pending_trigger_orders_round_trip_order_type_and_trigger_price(self):
        for order_type, action, trigger in (
            ('limit', 'open_long', '95'),
            ('breakout', 'open_short', '95'),
        ):
            with self.subTest(order_type=order_type):
                simulator, book = self.make_book()
                price_key = 'limit_price' if order_type == 'limit' else 'trigger_price'
                order = book.submit_order(
                    action=action,
                    order_type=order_type,
                    margin='100',
                    leverage=5,
                    timestamp=SUBMITTED_AT,
                    current_price='100',
                    **{price_key: trigger},
                )

                public_order = order.to_dict()
                state = book.to_state()
                restored = FuturesOrderBook.from_state(simulator, state)
                restored_order = restored.active_orders[0]

                self.assertEqual(public_order['order_type'], order_type)
                self.assertEqual(public_order[price_key], float(trigger))
                self.assertEqual(state['orders'][0]['order_type'], order_type)
                self.assertEqual(state['orders'][0][price_key], trigger)
                self.assertEqual(restored_order.order_type, order_type)
                self.assertEqual(getattr(restored_order, price_key), Decimal(trigger))

    def test_daily_replay_fills_short_limit_from_revealed_underlying_bar_only(self):
        start = datetime(2025, 1, 1, 23, 55, tzinfo=UTC)
        rows = []
        for index in range(289):
            timestamp = start + timedelta(minutes=5 * index)
            rows.append({
                'timestamp': timestamp,
                'open': 100,
                'high': 106 if index == 120 else 104,
                'low': 98,
                'close': 100,
                'volume': 10,
                'turnover': 1000,
            })
        bars = pd.DataFrame(rows)
        session = CryptoReplaySession(
            bars,
            initial_time=start,
            symbol='BTCUSDT',
            source='offline-cache',
            active_period='daily',
            max_training_days=2,
        )
        simulator, book = self.make_book()
        executor = FuturesReplayExecutor(
            clock=session.clock,
            trade_bars=bars,
            mark_bars=bars,
            engine=FuturesEngine(simulator, book),
            symbol='BTCUSDT',
            source='offline-cache',
        )
        session._on_bar = executor.on_bar

        initial_snapshot = session.snapshot()
        self.assertEqual(initial_snapshot['current_time'], '2025-01-01 23:55:00')
        self.assertEqual(initial_snapshot['kline_data'][-1]['end_time'], '2025-01-01 23:55:00')
        order = executor.submit_order(
            action='open_short',
            order_type='limit',
            margin='100',
            leverage=5,
            limit_price='105',
        )

        session.advance_delta(max_bars=300)

        self.assertEqual(order.status, 'filled')
        self.assertEqual(order.filled_at, start + timedelta(minutes=5 * 120))
        self.assertEqual(book.fills[-1].price, Decimal('105'))
