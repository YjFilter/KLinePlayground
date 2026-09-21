from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from backend.crypto.futures_orders import FuturesOrderBook, FuturesOrderError
from backend.crypto.futures_simulator import FuturesSimulator


UTC = timezone.utc
T0 = datetime(2026, 1, 1, tzinfo=UTC)
T1 = T0 + timedelta(minutes=5)


class CryptoBinanceOrderTests(unittest.TestCase):
    def make_book(self, *, min_notional='5'):
        simulator = FuturesSimulator(
            initial_balance='10000', quantity_step='0.001',
            min_quantity='0.001', min_notional=min_notional, leverage=5,
        )
        return simulator, FuturesOrderBook(
            simulator, maker_fee_rate='0.0002', taker_fee_rate='0.0005',
        )

    def assert_order_error(self, code, callback):
        with self.assertRaises(FuturesOrderError) as context:
            callback()
        self.assertEqual(context.exception.code, code)
        self.assertTrue(context.exception.message)

    def submit_entry(self, book, action, order_type, price, timestamp=T0):
        field = 'limit_price' if order_type == 'limit' else 'trigger_price'
        return book.submit_order(
            action=action, order_type=order_type, margin='100', leverage=5,
            timestamp=timestamp, current_price='100', **{field: price},
        )

    def open_position(self, book, action):
        return book.submit_order(
            action=action, order_type='market', margin='100', leverage=5,
            timestamp=T0, current_price='100',
        )

    def open_long_with_protection(self, book):
        parent = book.submit_order(
            action='open_long', order_type='market', margin='100', leverage=5,
            tp_price='110', sl_price='95', timestamp=T0, current_price='100',
        )
        children = [order for order in book.orders if order.parent_order_id == parent.order_id]
        return (
            next(order for order in children if order.protection_type == 'tp'),
            next(order for order in children if order.protection_type == 'sl'),
        )

    def test_strict_limit_direction_accepts_all_four_valid_sides(self):
        _, book = self.make_book()
        self.assertEqual(self.submit_entry(book, 'open_long', 'limit', '99').side, 'buy')
        _, book = self.make_book()
        self.assertEqual(self.submit_entry(book, 'open_short', 'limit', '101').side, 'sell')

        _, book = self.make_book()
        self.open_position(book, 'open_long')
        close_long = book.submit_order(
            action='close', order_type='limit', limit_price='101',
            timestamp=T1, current_price='100',
        )
        self.assertEqual(close_long.side, 'sell')
        self.assertTrue(close_long.reduce_only)

        _, book = self.make_book()
        self.open_position(book, 'open_short')
        close_short = book.submit_order(
            action='close', order_type='limit', limit_price='99',
            timestamp=T1, current_price='100',
        )
        self.assertEqual(close_short.side, 'buy')
        self.assertTrue(close_short.reduce_only)

    def test_strict_limit_direction_rejects_equal_and_reversed_prices(self):
        for action, price in (
            ('open_long', '100'), ('open_long', '101'),
            ('open_short', '100'), ('open_short', '99'),
        ):
            with self.subTest(action=action, price=price):
                _, book = self.make_book()
                self.assert_order_error(
                    'invalid_limit_direction',
                    lambda book=book, action=action, price=price: self.submit_entry(
                        book, action, 'limit', price,
                    ),
                )

        # 平仓限价只能挂在"不会立刻成交"的一侧（= 止盈侧）。
        # 回归：曾经放开过这个限制，导致"低于现价的平多限价"在下一根 K 线立刻成交，
        # 用户设置的止损线还没到就被平仓（因为卖出限价的撮合条件是 high >= 限价）。
        for opening_action, price in (
            ('open_long', '100'), ('open_long', '99'),
            ('open_short', '100'), ('open_short', '101'),
        ):
            with self.subTest(opening_action=opening_action, price=price):
                _, book = self.make_book()
                self.open_position(book, opening_action)
                self.assert_order_error(
                    'invalid_limit_direction',
                    lambda book=book, price=price: book.submit_order(
                        action='close', order_type='limit', limit_price=price,
                        timestamp=T1, current_price='100',
                    ),
                )

        # 止盈侧的平仓限价照常受理
        _, book = self.make_book()
        self.open_position(book, 'open_long')
        self.assertTrue(book.submit_order(
            action='close', order_type='limit', limit_price='101',
            timestamp=T1, current_price='100',
        ).reduce_only)

    def test_stop_loss_breakout_does_not_fill_until_price_crosses(self):
        """回归：止损必须用突破单，且只有价格真的穿越触发价才成交。

        用户反馈的 bug —— 多头在 100 开仓、止损挂在 95，点下一根 K 线就被平仓。
        根因是当时把止损发成了 limit 单，而"卖出限价"的条件是 high >= 95，必然成立。
        """
        _, book = self.make_book()
        self.open_position(book, 'open_long')
        stop = book.submit_order(
            action='close', order_type='breakout', trigger_price='95',
            timestamp=T0, current_price='100',
        )
        self.assertEqual(stop.side, 'sell')

        # 下一根 K 线的低点没有碰到止损价 → 绝不能成交
        untouched = book.process_bar(timestamp=T1, open='100', high='101', low='98', close='99')
        self.assertEqual(untouched, [])
        self.assertEqual(stop.status, 'active')

        # 价格跌破触发价 → 成交在触发价
        T2 = T1 + timedelta(minutes=5)
        crossed = book.process_bar(timestamp=T2, open='99', high='99', low='94', close='94.5')
        self.assertEqual(len(crossed), 1)
        self.assertEqual(crossed[0].price, Decimal('95'))
        self.assertEqual(stop.status, 'filled')

    def test_take_profit_limit_only_fills_when_high_reaches_it(self):
        """止盈用限价单：只有最高价触及止盈价才成交（对称地不会提前成交）。"""
        _, book = self.make_book()
        self.open_position(book, 'open_long')
        target = book.submit_order(
            action='close', order_type='limit', limit_price='110',
            timestamp=T0, current_price='100',
        )
        self.assertEqual(book.process_bar(timestamp=T1, open='100', high='105', low='99', close='104'), [])
        self.assertEqual(target.status, 'active')
        T2 = T1 + timedelta(minutes=5)
        filled = book.process_bar(timestamp=T2, open='105', high='111', low='104', close='110')
        self.assertEqual(len(filled), 1)
        self.assertEqual(filled[0].price, Decimal('110'))

    def test_amending_protective_order_across_market_switches_order_type(self):
        """把保护线拖到现价另一侧时必须改判类型，否则下一根 K 线会立刻成交。"""
        _, book = self.make_book()
        self.open_position(book, 'open_long')
        stop = book.submit_order(
            action='close', order_type='breakout', trigger_price='95',
            timestamp=T0, current_price='100',
        )
        # 拖到现价上方 → 变成止盈限价单
        book.modify_order_price(stop.order_id, '110', T0, current_price='100')
        self.assertEqual(stop.order_type, 'limit')
        self.assertEqual(stop.protection_type, 'tp')
        self.assertEqual(stop.limit_price, Decimal('110'))
        self.assertIsNone(stop.trigger_price)
        self.assertEqual(book.process_bar(timestamp=T1, open='100', high='105', low='99', close='104'), [])

        # 再拖回现价下方 → 变回止损突破单，且不会立刻成交
        book.modify_order_price(stop.order_id, '90', T0, current_price='100')
        self.assertEqual(stop.order_type, 'breakout')
        self.assertEqual(stop.protection_type, 'sl')
        self.assertEqual(stop.trigger_price, Decimal('90'))
        self.assertIsNone(stop.limit_price)
        self.assertEqual(book.process_bar(timestamp=T1, open='100', high='101', low='98', close='99'), [])

    def test_amending_protective_order_onto_mark_price_is_rejected(self):
        _, book = self.make_book()
        self.open_position(book, 'open_long')
        stop = book.submit_order(
            action='close', order_type='breakout', trigger_price='95',
            timestamp=T0, current_price='100',
        )
        self.assert_order_error(
            'invalid_limit_direction',
            lambda: book.modify_order_price(stop.order_id, '100', T0, current_price='100'),
        )

    def test_amending_entry_order_onto_marketable_side_is_rejected(self):
        """开仓挂单也不能改到会立即成交的一侧（否则静默变成市价单）。"""
        _, book = self.make_book()
        entry = self.submit_entry(book, 'open_long', 'limit', '99')
        self.assert_order_error(
            'invalid_limit_direction',
            lambda: book.modify_order_price(entry.order_id, '101', T0, current_price='100'),
        )
        # 仍在安全一侧 → 正常改价
        book.modify_order_price(entry.order_id, '98', T0, current_price='100')
        self.assertEqual(entry.limit_price, Decimal('98'))

    def test_pending_order_never_fills_on_submission_bar(self):
        simulator, book = self.make_book()
        order = self.submit_entry(book, 'open_long', 'limit', '99')
        same_bar = book.process_bar(
            timestamp=T0, open='100', high='101', low='98', close='99',
        )
        next_bar = book.process_bar(
            timestamp=T1, open='100', high='101', low='98', close='99',
        )
        self.assertEqual(same_bar, [])
        self.assertEqual(len(next_bar), 1)
        self.assertEqual(order.status, 'filled')
        self.assertEqual(simulator.position.entry_price, Decimal('99'))

    def test_limit_gap_fills_at_configured_limit_for_both_sides(self):
        cases = (
            ('open_long', '99', {'open': '95', 'high': '96', 'low': '94', 'close': '95'}),
            ('open_short', '101', {'open': '105', 'high': '106', 'low': '104', 'close': '105'}),
        )
        for action, price, bar in cases:
            with self.subTest(action=action):
                _, book = self.make_book()
                self.submit_entry(book, action, 'limit', price)
                fills = book.process_bar(timestamp=T1, **bar)
                self.assertEqual(len(fills), 1)
                self.assertEqual(fills[0].price, Decimal(price))
                self.assertEqual(fills[0].fee_type, 'maker')

    def test_breakout_orders_fill_at_trigger_price_for_both_sides(self):
        cases = (
            ('open_long', '105', {'open': '108', 'high': '110', 'low': '104', 'close': '109'}),
            ('open_short', '95', {'open': '92', 'high': '96', 'low': '90', 'close': '91'}),
        )
        for action, price, bar in cases:
            with self.subTest(action=action):
                _, book = self.make_book()
                order = self.submit_entry(book, action, 'breakout', price)
                fills = book.process_bar(timestamp=T1, **bar)
                self.assertEqual(len(fills), 1)
                self.assertEqual(fills[0].price, Decimal(price))
                self.assertEqual(fills[0].fee_type, 'taker')
                self.assertEqual(order.status, 'filled')

    def test_each_open_direction_allows_only_one_pending_limit_or_breakout(self):
        _, book = self.make_book()
        long_order = self.submit_entry(book, 'open_long', 'limit', '99')
        short_order = self.submit_entry(book, 'open_short', 'breakout', '95')
        self.assertEqual(long_order.status, 'active')
        self.assertEqual(short_order.status, 'active')
        self.assert_order_error(
            'duplicate_pending_order',
            lambda: self.submit_entry(book, 'open_long', 'breakout', '105'),
        )
        self.assert_order_error(
            'duplicate_pending_order',
            lambda: self.submit_entry(book, 'open_short', 'limit', '101'),
        )

    def test_minimum_quantity_and_notional_errors_have_stable_codes(self):
        _, quantity_book = self.make_book()
        self.assert_order_error(
            'min_quantity',
            lambda: quantity_book.submit_order(
                action='open_long', order_type='limit', margin='0.01', leverage=5,
                limit_price='99', timestamp=T0, current_price='100',
            ),
        )

        _, notional_book = self.make_book(min_notional='50')
        self.assert_order_error(
            'min_notional',
            lambda: notional_book.submit_order(
                action='open_long', order_type='limit', margin='1', leverage=5,
                limit_price='99', timestamp=T0, current_price='100',
            ),
        )

    def test_tp_sl_use_mark_ohlc_taker_fill_and_oco(self):
        cases = (
            (
                'tp', '110',
                {'open': '100', 'high': '105', 'low': '99', 'close': '102',
                 'trigger_high': '111', 'trigger_low': '98'},
            ),
            (
                'sl', '95',
                {'open': '100', 'high': '103', 'low': '97', 'close': '99',
                 'trigger_high': '104', 'trigger_low': '94'},
            ),
        )
        for filled_type, expected_price, bar in cases:
            with self.subTest(filled_type=filled_type):
                simulator, book = self.make_book()
                take_profit, stop_loss = self.open_long_with_protection(book)
                selected = take_profit if filled_type == 'tp' else stop_loss
                sibling = stop_loss if filled_type == 'tp' else take_profit
                fills = book.process_bar(timestamp=T1, **bar)
                self.assertEqual(len(fills), 1)
                self.assertEqual(fills[0].price, Decimal(expected_price))
                self.assertEqual(fills[0].fee_type, 'taker')
                self.assertEqual(selected.status, 'filled')
                self.assertEqual(selected.trigger_source, 'mark_price')
                self.assertEqual(sibling.status, 'cancelled')
                self.assertEqual(sibling.cancel_reason, 'oco_sibling_filled')
                self.assertTrue(simulator.position.is_flat)

    def test_same_mark_bar_prefers_stop_loss(self):
        _, book = self.make_book()
        take_profit, stop_loss = self.open_long_with_protection(book)
        fills = book.process_bar(
            timestamp=T1, open='100', high='105', low='97', close='100',
            trigger_high='111', trigger_low='94',
        )
        self.assertEqual(len(fills), 1)
        self.assertEqual(fills[0].price, Decimal('95'))
        self.assertEqual(stop_loss.status, 'filled')
        self.assertEqual(take_profit.status, 'cancelled')

    def test_protection_fields_survive_order_book_state_round_trip(self):
        simulator, book = self.make_book()
        parent = book.submit_order(
            action='open_short', order_type='market', margin='100', leverage=5,
            tp_price='90', sl_price='105', timestamp=T0, current_price='100',
        )
        restored = FuturesOrderBook.from_state(simulator, book.to_state())
        children = [
            order for order in restored.orders if order.parent_order_id == parent.order_id
        ]
        self.assertEqual({order.protection_type for order in children}, {'tp', 'sl'})
        self.assertEqual({order.trigger_source for order in children}, {'mark_price'})

    def test_cancelled_pending_direction_can_be_submitted_again(self):
        _, book = self.make_book()
        first = self.submit_entry(book, 'open_long', 'limit', '99')
        self.assertTrue(book.cancel_order(first.order_id, T1))
        replacement = self.submit_entry(book, 'open_long', 'breakout', '105', T1)
        self.assertEqual(first.status, 'cancelled')
        self.assertEqual(replacement.status, 'active')
        self.assertNotEqual(first.order_id, replacement.order_id)


if __name__ == '__main__':
    unittest.main()
