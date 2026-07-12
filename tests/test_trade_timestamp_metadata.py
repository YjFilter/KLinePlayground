"""TASK-008: Trade timestamp and display-period metadata tests.

These tests verify that:
- buy/sell accept optional trade_time and display_period without breaking legacy callers.
- Trade dicts and report details expose the two new fields alongside trade_date.
- SQLite trades table gains columns through repeatable additive migration.
- Insert and update paths persist both fields.
- Two same-day trades at different times remain separate records and preserve order.
- T+1 continues to use trade_date, not trade_time.
- Legacy calls that pass only trade_date still work and receive safe defaults.

All tests use a temporary database file so no real user data is touched.
"""

import importlib
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

# Ensure project root is on sys.path so `backend.*` imports resolve.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.trade_simulator_enhanced import TradeSimulatorEnhanced


def _make_simulator(user='test_timestamp_user', initial_capital=100000.0, stock_code='600000'):
    """Create a simulator backed by a temporary database.

    The default constructor writes to ``../users/{user}/trade_records.db`` which
    would pollute real user data. We patch ``_init_database`` to a no-op during
    ``__init__`` so nothing is created at the default path, then point
    ``db_path`` at a temp file and run the real migration.
    """
    temp_dir = tempfile.mkdtemp(prefix='kline_task008_')
    db_path = os.path.join(temp_dir, 'trade_records.db')

    with patch.object(TradeSimulatorEnhanced, '_init_database', lambda self: None):
        sim = TradeSimulatorEnhanced(user, initial_capital, stock_code)

    sim.db_path = db_path
    sim._init_database()
    return sim, temp_dir, db_path


def _read_trades_from_db(db_path):
    """Return all rows from the trades table ordered by id."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute('SELECT * FROM trades ORDER BY id ASC').fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


class BuySellSignatureTests(unittest.TestCase):
    """Acceptance: buy/sell accept optional trade_time and display_period."""

    def setUp(self):
        self.sim, self.temp_dir, self.db_path = _make_simulator()
        self.sim.update_current_price(10.0, bar_id=1)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_buy_accepts_trade_time_and_display_period(self):
        result = self.sim.buy(
            quantity=1,
            price=10.0,
            trade_date='2024-01-02',
            reason='morning break',
            trade_time='2024-01-02 10:30:00',
            display_period='30m',
        )
        self.assertTrue(result['success'], result.get('message'))
        trade = result['trade']
        self.assertEqual(trade['trade_date'], '2024-01-02')
        self.assertEqual(trade['trade_time'], '2024-01-02 10:30:00')
        self.assertEqual(trade['display_period'], '30m')

    def test_sell_accepts_trade_time_and_display_period(self):
        self.sim.buy(quantity=2, price=10.0, trade_date='2024-01-02')
        # advance to next day so T+1 permits the sell
        self.sim.sell(
            quantity=1,
            price=10.5,
            trade_date='2024-01-03',
            reason='intraday exit',
            trade_time='2024-01-03 14:00:00',
            display_period='4h_session',
        )
        # The sell above must succeed and carry the new metadata.
        sell_result = self.sim.sell(
            quantity=1,
            price=10.6,
            trade_date='2024-01-03',
            reason='afternoon exit',
            trade_time='2024-01-03 14:30:00',
            display_period='30m',
        )
        self.assertTrue(sell_result['success'], sell_result.get('message'))
        trade = sell_result['trade']
        self.assertEqual(trade['trade_time'], '2024-01-03 14:30:00')
        self.assertEqual(trade['display_period'], '30m')

    def test_legacy_buy_without_new_params_still_works(self):
        result = self.sim.buy(quantity=1, price=10.0, trade_date='2024-01-02')
        self.assertTrue(result['success'], result.get('message'))
        trade = result['trade']
        # trade_date is always present; new fields must default to safe values.
        self.assertEqual(trade['trade_date'], '2024-01-02')
        self.assertIn('trade_time', trade)
        self.assertIn('display_period', trade)

    def test_legacy_sell_without_new_params_still_works(self):
        self.sim.buy(quantity=2, price=10.0, trade_date='2024-01-02')
        result = self.sim.sell(quantity=1, price=10.5, trade_date='2024-01-03')
        self.assertTrue(result['success'], result.get('message'))
        trade = result['trade']
        self.assertIn('trade_time', trade)
        self.assertIn('display_period', trade)


class TradeDictFieldsTests(unittest.TestCase):
    """Acceptance: trade dictionaries expose trade_date, trade_time, display_period."""

    def setUp(self):
        self.sim, self.temp_dir, self.db_path = _make_simulator()
        self.sim.update_current_price(10.0, bar_id=1)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_buy_trade_dict_has_all_three_fields(self):
        result = self.sim.buy(
            quantity=1,
            price=10.0,
            trade_date='2024-01-02',
            trade_time='2024-01-02 10:30:00',
            display_period='30m',
        )
        trade = result['trade']
        self.assertEqual(trade['trade_date'], '2024-01-02')
        self.assertEqual(trade['trade_time'], '2024-01-02 10:30:00')
        self.assertEqual(trade['display_period'], '30m')

    def test_sell_trade_dict_has_all_three_fields(self):
        self.sim.buy(quantity=2, price=10.0, trade_date='2024-01-02')
        result = self.sim.sell(
            quantity=1,
            price=10.5,
            trade_date='2024-01-03',
            trade_time='2024-01-03 14:00:00',
            display_period='4h_session',
        )
        trade = result['trade']
        self.assertEqual(trade['trade_date'], '2024-01-03')
        self.assertEqual(trade['trade_time'], '2024-01-03 14:00:00')
        self.assertEqual(trade['display_period'], '4h_session')


class ReportDetailsTests(unittest.TestCase):
    """Acceptance: generate_report trade_details include the new fields."""

    def setUp(self):
        self.sim, self.temp_dir, self.db_path = _make_simulator()
        self.sim.update_current_price(10.0, bar_id=1)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_report_trade_details_include_new_fields(self):
        self.sim.buy(
            quantity=1,
            price=10.0,
            trade_date='2024-01-02',
            trade_time='2024-01-02 10:30:00',
            display_period='30m',
        )
        self.sim.update_current_price(10.5, bar_id=2)
        self.sim.sell(
            quantity=1,
            price=10.5,
            trade_date='2024-01-03',
            trade_time='2024-01-03 14:00:00',
            display_period='4h_session',
        )

        report = self.sim.generate_report('600000', '2024-01-02', '2024-01-03')
        details = report['trade_details']
        self.assertEqual(len(details), 2)

        buy_detail = details[0]
        self.assertEqual(buy_detail['date'], '2024-01-02')
        self.assertEqual(buy_detail['trade_time'], '2024-01-02 10:30:00')
        self.assertEqual(buy_detail['display_period'], '30m')

        sell_detail = details[1]
        self.assertEqual(sell_detail['date'], '2024-01-03')
        self.assertEqual(sell_detail['trade_time'], '2024-01-03 14:00:00')
        self.assertEqual(sell_detail['display_period'], '4h_session')

    def test_report_trade_details_legacy_calls_have_safe_defaults(self):
        self.sim.buy(quantity=1, price=10.0, trade_date='2024-01-02')
        report = self.sim.generate_report('600000', '2024-01-02', '2024-01-02')
        details = report['trade_details']
        self.assertEqual(len(details), 1)
        self.assertIn('trade_time', details[0])
        self.assertIn('display_period', details[0])


class DatabaseMigrationTests(unittest.TestCase):
    """Acceptance: SQLite trades table gains columns via repeatable additive migration."""

    def setUp(self):
        self.sim, self.temp_dir, self.db_path = _make_simulator()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_trades_table_has_new_columns(self):
        conn = sqlite3.connect(self.db_path)
        try:
            cols = {row[1] for row in conn.execute('PRAGMA table_info(trades)').fetchall()}
        finally:
            conn.close()
        self.assertIn('trade_time', cols)
        self.assertIn('display_period', cols)
        # Existing columns must still be present.
        self.assertIn('trade_date', cols)
        self.assertIn('reason', cols)

    def test_migration_is_repeatable_without_error(self):
        # Calling _init_database multiple times must not raise.
        for _ in range(3):
            self.sim._init_database()
        # And columns are still there exactly once.
        conn = sqlite3.connect(self.db_path)
        try:
            cols = [row[1] for row in conn.execute('PRAGMA table_info(trades)').fetchall()]
        finally:
            conn.close()
        self.assertEqual(cols.count('trade_time'), 1)
        self.assertEqual(cols.count('display_period'), 1)

    def test_migration_preserves_existing_data(self):
        self.sim.update_current_price(10.0, bar_id=1)
        self.sim.buy(
            quantity=1,
            price=10.0,
            trade_date='2024-01-02',
            trade_time='2024-01-02 10:30:00',
            display_period='30m',
        )
        # Re-run init; existing row must survive.
        self.sim._init_database()
        rows = _read_trades_from_db(self.db_path)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['trade_time'], '2024-01-02 10:30:00')
        self.assertEqual(rows[0]['display_period'], '30m')


class DatabasePersistenceTests(unittest.TestCase):
    """Acceptance: insert and update paths persist both new fields."""

    def setUp(self):
        self.sim, self.temp_dir, self.db_path = _make_simulator()
        self.sim.update_current_price(10.0, bar_id=1)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_insert_path_persists_new_fields(self):
        self.sim.buy(
            quantity=1,
            price=10.0,
            trade_date='2024-01-02',
            trade_time='2024-01-02 10:30:00',
            display_period='30m',
        )
        rows = _read_trades_from_db(self.db_path)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['trade_time'], '2024-01-02 10:30:00')
        self.assertEqual(rows[0]['display_period'], '30m')
        self.assertEqual(rows[0]['trade_date'], '2024-01-02')

    def test_update_path_persists_new_fields(self):
        # Two same-day same-time buys should merge (legacy-compatible behavior).
        self.sim.buy(
            quantity=1,
            price=10.0,
            trade_date='2024-01-02',
            trade_time='2024-01-02 10:30:00',
            display_period='30m',
        )
        self.sim.buy(
            quantity=1,
            price=10.2,
            trade_date='2024-01-02',
            trade_time='2024-01-02 10:30:00',
            display_period='30m',
        )
        rows = _read_trades_from_db(self.db_path)
        # Merged into a single row.
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['trade_time'], '2024-01-02 10:30:00')
        self.assertEqual(rows[0]['display_period'], '30m')
        self.assertEqual(rows[0]['quantity'], 2)

    def test_legacy_insert_persists_safe_defaults(self):
        self.sim.buy(quantity=1, price=10.0, trade_date='2024-01-02')
        rows = _read_trades_from_db(self.db_path)
        self.assertEqual(len(rows), 1)
        # Defaults should be present (empty string is acceptable).
        self.assertIn('trade_time', rows[0])
        self.assertIn('display_period', rows[0])


class SameDayOrderingTests(unittest.TestCase):
    """Acceptance: two same-day trades at different times remain separate and ordered."""

    def setUp(self):
        self.sim, self.temp_dir, self.db_path = _make_simulator()
        self.sim.update_current_price(10.0, bar_id=1)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_same_day_different_times_keeps_two_records_in_order(self):
        self.sim.buy(
            quantity=1,
            price=10.0,
            trade_date='2024-01-02',
            trade_time='2024-01-02 10:30:00',
            display_period='30m',
        )
        self.sim.buy(
            quantity=1,
            price=10.2,
            trade_date='2024-01-02',
            trade_time='2024-01-02 14:00:00',
            display_period='30m',
        )
        # trade_history keeps insertion order.
        history = self.sim.get_trade_history_with_bar_id()
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]['trade_time'], '2024-01-02 10:30:00')
        self.assertEqual(history[1]['trade_time'], '2024-01-02 14:00:00')

        # Database also keeps two separate rows in order.
        rows = _read_trades_from_db(self.db_path)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['trade_time'], '2024-01-02 10:30:00')
        self.assertEqual(rows[1]['trade_time'], '2024-01-02 14:00:00')

    def test_same_day_different_times_does_not_merge_quantities(self):
        self.sim.buy(
            quantity=1,
            price=10.0,
            trade_date='2024-01-02',
            trade_time='2024-01-02 10:30:00',
            display_period='30m',
        )
        self.sim.buy(
            quantity=2,
            price=10.2,
            trade_date='2024-01-02',
            trade_time='2024-01-02 14:00:00',
            display_period='30m',
        )
        history = self.sim.get_trade_history_with_bar_id()
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]['quantity'], 1)
        self.assertEqual(history[1]['quantity'], 2)

    def test_legacy_same_day_buys_still_merge(self):
        # Backward compatibility: legacy calls (no trade_time) on the same day
        # must continue to merge as before.
        self.sim.buy(quantity=1, price=10.0, trade_date='2024-01-02')
        self.sim.buy(quantity=1, price=10.2, trade_date='2024-01-02')
        history = self.sim.get_trade_history_with_bar_id()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]['quantity'], 2)


class TPlusOneSemanticsTests(unittest.TestCase):
    """Acceptance: T+1 continues to use trade_date, not trade_time."""

    def setUp(self):
        self.sim, self.temp_dir, self.db_path = _make_simulator()
        self.sim.update_current_price(10.0, bar_id=1)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_same_day_sell_after_buy_is_blocked_by_t1(self):
        buy_result = self.sim.buy(
            quantity=1,
            price=10.0,
            trade_date='2024-01-02',
            trade_time='2024-01-02 10:30:00',
            display_period='30m',
        )
        self.assertTrue(buy_result['success'])

        # Even with a later trade_time on the same trade_date, sell is blocked.
        sell_result = self.sim.sell(
            quantity=1,
            price=10.5,
            trade_date='2024-01-02',
            trade_time='2024-01-02 14:00:00',
            display_period='30m',
        )
        self.assertFalse(sell_result['success'])

    def test_next_day_sell_after_buy_is_allowed(self):
        self.sim.buy(
            quantity=1,
            price=10.0,
            trade_date='2024-01-02',
            trade_time='2024-01-02 10:30:00',
            display_period='30m',
        )
        sell_result = self.sim.sell(
            quantity=1,
            price=10.5,
            trade_date='2024-01-03',
            trade_time='2024-01-03 09:30:00',
            display_period='30m',
        )
        self.assertTrue(sell_result['success'], sell_result.get('message'))


if __name__ == '__main__':
    unittest.main()
