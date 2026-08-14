from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pandas as pd

from backend.crypto.futures_engine import FuturesEngine
from backend.crypto.futures_orders import FuturesOrderBook
from backend.crypto.futures_simulator import FuturesSimulator
from backend.crypto.models import FundingEvent
from backend.crypto.persistence import CryptoFuturesRepository, migrate_crypto_futures_schema
from backend.crypto.replay_clock import CryptoReplayClock
from backend.crypto.trading import FuturesReplayExecutor


UTC = timezone.utc


class CryptoFuturesPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "history.db"
        with closing(sqlite3.connect(self.db_path)) as connection:
            connection.execute("CREATE TABLE training_sessions (session_id TEXT PRIMARY KEY, stock_code TEXT NOT NULL, initial_capital REAL NOT NULL)")
            connection.execute("CREATE TABLE trade_history (id INTEGER PRIMARY KEY, session_id TEXT, quantity INTEGER NOT NULL)")
            connection.execute("INSERT INTO training_sessions VALUES ('legacy-1', '000001', 100000)")
            connection.execute("INSERT INTO trade_history VALUES (1, 'legacy-1', 100)")
            connection.commit()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_migration_is_additive_repeatable_and_legacy_compatible(self):
        migrate_crypto_futures_schema(self.db_path)
        migrate_crypto_futures_schema(self.db_path)
        with closing(sqlite3.connect(self.db_path)) as connection:
            session_columns = {row[1] for row in connection.execute("PRAGMA table_info(training_sessions)")}
            self.assertTrue({"market_type", "symbol", "quote_currency", "base_interval", "timezone", "source", "simulator_type"} <= session_columns)
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertTrue({
                "crypto_futures_orders", "crypto_futures_fills", "crypto_funding_events",
                "crypto_liquidation_events", "crypto_equity_snapshots",
            } <= tables)
            quantity_type = next(row[2] for row in connection.execute("PRAGMA table_info(trade_history)") if row[1] == "quantity")
            self.assertEqual(quantity_type.upper(), "INTEGER")
            self.assertEqual(connection.execute("SELECT stock_code, initial_capital FROM training_sessions WHERE session_id='legacy-1'").fetchone(), ("000001", 100000.0))
        repository = CryptoFuturesRepository(self.db_path)
        self.assertEqual(repository.get_session_metadata("legacy-1")["market_type"], "a_share")

    def test_events_and_metadata_rehydrate_after_repository_restart(self):
        repository = CryptoFuturesRepository(self.db_path)
        repository.save_session_metadata("legacy-1", market_type="crypto_perpetual", symbol="BTCUSDT", quote_currency="USDT", base_interval="5m", timezone="UTC", source="binance", simulator_type="isolated_futures")
        repository.record_order("legacy-1", {"order_id": "order-1", "action": "open_long", "order_type": "market", "side": "buy", "quantity": Decimal("0.1"), "margin": Decimal("100"), "leverage": 5, "submitted_at": "2024-01-01T00:00:00+00:00", "status": "filled"})
        repository.record_fill("legacy-1", {"fill_id": "fill-1", "order_id": "order-1", "action": "open_long", "side": "buy", "quantity": Decimal("0.1"), "price": Decimal("50000"), "fee": Decimal("2.5"), "fee_type": "taker", "timestamp": "2024-01-01T00:00:00+00:00", "realized_pnl": Decimal("0")})
        repository.record_funding("legacy-1", {"event_key": "funding-1", "timestamp": "2024-01-01T08:00:00+00:00", "rate": Decimal("0.0001"), "mark_price": Decimal("51000"), "notional": Decimal("5100"), "transfer": Decimal("-0.51"), "position_side": "long", "source": "binance", "symbol": "BTCUSDT", "status": "settled"})
        repository.record_liquidation("legacy-1", {"liquidation_id": "liq-1", "timestamp": "2024-01-02T00:00:00+00:00", "side": "long", "quantity": Decimal("0.1"), "entry_price": Decimal("50000"), "price": Decimal("45000"), "fee": Decimal("22.5"), "equity_before": Decimal("22.5"), "maintenance_margin": Decimal("22.5"), "reason": "isolated_margin"})
        repository.record_equity("legacy-1", {"timestamp": "2024-01-01T00:00:00+00:00", "equity": Decimal("1000"), "balance": Decimal("1000"), "unrealized_pnl": Decimal("0"), "mark_price": Decimal("50000")})

        restarted = CryptoFuturesRepository(self.db_path)
        state = restarted.load_session_state("legacy-1")
        self.assertEqual(state["metadata"]["symbol"], "BTCUSDT")
        self.assertEqual(state["orders"][0]["order_id"], "order-1")
        self.assertEqual(state["fills"][0]["fill_id"], "fill-1")
        self.assertEqual(state["funding_events"][0]["event_key"], "funding-1")
        self.assertEqual(state["liquidation_events"][0]["liquidation_id"], "liq-1")
        self.assertEqual(state["equity_snapshots"][0]["equity"], Decimal("1000"))
        self.assertIsInstance(state["fills"][0]["price"], Decimal)
        with closing(sqlite3.connect(self.db_path)) as connection:
            payload = connection.execute("SELECT payload FROM crypto_futures_fills").fetchone()[0]
        self.assertIn('"price": "50000"', payload)

    def test_migration_respects_caller_managed_connection_transaction(self):
        connection = sqlite3.connect(":memory:")
        try:
            connection.execute("CREATE TABLE training_sessions (session_id TEXT PRIMARY KEY)")
            connection.execute("INSERT INTO training_sessions VALUES ('pending')")
            self.assertTrue(connection.in_transaction)
            migrate_crypto_futures_schema(connection)
            self.assertTrue(connection.in_transaction)
            connection.rollback()
            with self.assertRaises(sqlite3.OperationalError):
                connection.execute("SELECT market_type FROM training_sessions")
        finally:
            connection.close()

    def test_runtime_rehydrate_continues_clock_orders_ids_and_funding_without_duplicates(self):
        start = datetime(2024, 1, 1, tzinfo=UTC)
        rows = []
        for index in range(5):
            timestamp = start + timedelta(minutes=5 * index)
            rows.append({"timestamp": timestamp, "open": Decimal("100"), "high": Decimal("102"), "low": Decimal("98"), "close": Decimal("100")})
        trade = pd.DataFrame(rows)
        mark = pd.DataFrame(rows)
        funding = [FundingEvent(source="binance", symbol="BTCUSDT", timestamp=start + timedelta(minutes=5), rate=Decimal("0.001"), mark_price=Decimal("100"))]
        simulator = FuturesSimulator(initial_balance="1000", quantity_step="0.001", min_quantity="0.001", min_notional="5")
        orders = FuturesOrderBook(simulator)
        engine = FuturesEngine(simulator, orders)
        executor = FuturesReplayExecutor(clock=CryptoReplayClock(trade["timestamp"], active_period="5m", base_step_minutes=5), trade_bars=trade, mark_bars=mark, engine=engine, funding_events=funding, symbol="BTCUSDT", source="binance")
        executor.submit_order(action="open_long", order_type="market", margin="100", leverage=5)
        pending = executor.submit_order(action="open_long", order_type="limit", margin="50", leverage=5, limit_price="90")
        executor.advance()
        repository = CryptoFuturesRepository(self.db_path)
        repository.save_runtime_state("legacy-1", executor)

        restarted = CryptoFuturesRepository(self.db_path).rehydrate_executor(
            "legacy-1", trade_bars=trade, mark_bars=mark, funding_events=funding,
        )
        self.assertEqual(restarted.clock.current_time, start + timedelta(minutes=5))
        self.assertEqual(restarted.engine.simulator.account.funding_paid, Decimal("0.500000"))
        self.assertEqual(restarted.engine.order_book.active_orders[0].order_id, pending.order_id)
        self.assertTrue(restarted.engine.order_book.cancel_order(pending.order_id, restarted.clock.current_time))
        new_order = restarted.submit_order(action="open_long", order_type="limit", margin="10", leverage=5, limit_price="80")
        self.assertEqual(new_order.order_id, "order-3")
        market_order = restarted.submit_order(action="open_long", order_type="market", margin="10", leverage=5)
        self.assertEqual(market_order.order_id, "order-4")
        self.assertEqual(restarted.engine.simulator.fills[-1].fill_id, "fill-2")
        restarted.advance()
        self.assertEqual(len(restarted.engine.funding_events), 1)
        self.assertEqual(restarted.engine.simulator.fills[-1].fill_id, "fill-2")
        self.assertIsInstance(restarted.engine.simulator.position.quantity, Decimal)

    def test_runtime_period_update_preserves_state_and_restores_active_period(self):
        repository = CryptoFuturesRepository(self.db_path)
        repository.save_runtime_state("period-1", {
            "version": 1,
            "clock": {
                "current_time": "2024-01-01T00:10:00+00:00",
                "active_period": "5m",
            },
            "training": {
                "period": "5m",
                "initial_period": "5m",
                "status": "active",
            },
            "orders": [{"order_id": "order-1"}],
        })

        repository.update_runtime_period("period-1", "15m")

        state = CryptoFuturesRepository(self.db_path).load_runtime_state("period-1")
        self.assertEqual(state["clock"]["active_period"], "15m")
        self.assertEqual(state["training"]["period"], "15m")
        self.assertEqual(state["training"]["initial_period"], "5m")
        self.assertEqual(state["orders"], [{"order_id": "order-1"}])


if __name__ == "__main__":
    unittest.main()
