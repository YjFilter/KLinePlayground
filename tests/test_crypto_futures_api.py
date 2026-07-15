from __future__ import annotations

import unittest
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

import backend.app_enhanced as app_module
from backend.crypto.futures_engine import FuturesEngine
from backend.crypto.futures_orders import FuturesOrderBook
from backend.crypto.futures_simulator import FuturesSimulator
from backend.crypto.session import CryptoReplaySession
from backend.crypto.trading import FuturesReplayExecutor


UTC = timezone.utc
START = datetime(2025, 1, 1, tzinfo=UTC)


def _bars():
    return pd.DataFrame([
        {
            "timestamp": START + timedelta(minutes=5 * index),
            "open": 100 + index,
            "high": 102 + index,
            "low": 98 + index,
            "close": 100 + index,
            "volume": 10,
            "turnover": 1000,
        }
        for index in range(4)
    ])


def _training(training_id="crypto-api"):
    bars = _bars()
    session = CryptoReplaySession(
        bars,
        initial_time=START,
        symbol="BTCUSDT",
        source="binance",
        active_period="5m",
    )
    simulator = FuturesSimulator(
        10000,
        quantity_step="0.001",
        min_quantity="0.001",
        min_notional="5",
        leverage=5,
    )
    order_book = FuturesOrderBook(simulator)
    engine = FuturesEngine(simulator, order_book)
    executor = FuturesReplayExecutor(
        clock=session.clock,
        trade_bars=bars,
        mark_bars=bars,
        engine=engine,
        symbol="BTCUSDT",
        source="binance",
    )
    session._on_bar = executor.on_bar
    training = {
        "user": "tester",
        "market_type": "crypto_perpetual",
        "data_mode": "crypto_5m",
        "symbol": "BTCUSDT",
        "stock_code": "BTCUSDT",
        "source": "binance",
        "data_source": "binance",
        "period": "5m",
        "mode": "specified",
        "start_date": "2025-01-01",
        "training_start": "2025-01-01 00:00:00",
        "training_end": "2025-01-01 00:15:00",
        "max_training_days": 1,
        "initial_period": "5m",
        "initial_capital": 10000,
        "leverage": 5,
        "crypto_session": session,
        "futures_executor": executor,
        "crypto_bundle": type("Bundle", (), {
            "trade_bars": bars,
            "mark_bars": bars,
            "funding": (),
            "source": "binance",
        })(),
        "instrument": type("Instrument", (), {
            "symbol": "BTCUSDT",
            "source": "binance",
            "quantity_step": "0.001",
            "min_quantity": "0.001",
            "min_notional": "5",
        })(),
        "status": "active",
        "id": training_id,
    }
    training["crypto_bundle"].instrument = training["instrument"]
    return training


class CryptoFuturesAPITests(unittest.TestCase):
    def setUp(self):
        app_module.app.config["TESTING"] = True
        self.client = app_module.app.test_client()
        self.training_id = "crypto-api"
        app_module.active_trainings[self.training_id] = _training(self.training_id)
        self.checkpoint_patcher = patch.object(app_module, "_checkpoint_crypto_futures")
        self.checkpoint = self.checkpoint_patcher.start()

    def tearDown(self):
        app_module.active_trainings.pop(self.training_id, None)
        self.checkpoint_patcher.stop()

    def test_market_open_and_account_snapshot(self):
        response = self.client.post(
            f"/api/training/{self.training_id}/trade",
            json={"action": "open_long", "order_type": "market", "margin": 100, "leverage": 5},
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        payload = response.get_json()
        self.assertEqual(payload["position"]["side"], "long")
        self.assertEqual(payload["trade_markers"][-1]["type"], "L")
        self.checkpoint.assert_called_once()

        account = self.client.get(f"/api/training/{self.training_id}/account")
        self.assertEqual(account.status_code, 200, account.get_json())
        self.assertEqual(account.get_json()["position"]["side"], "long")
        self.assertIn("liquidation_price", account.get_json()["position"])

        records = self.client.get(f"/api/training/{self.training_id}/trade_records")
        self.assertEqual(records.status_code, 200, records.get_json())
        self.assertEqual(records.get_json()[0]["action"], "open_long")

    def test_limit_order_is_pending_until_next_bar_and_can_be_cancelled(self):
        response = self.client.post(
            f"/api/training/{self.training_id}/trade",
            json={
                "action": "open_long",
                "order_type": "limit",
                "margin": 100,
                "leverage": 5,
                "limit_price": 99,
            },
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        order_id = response.get_json()["order"]["order_id"]
        self.assertEqual(len(response.get_json()["pending_orders"]), 1)

        cancelled = self.client.delete(f"/api/training/{self.training_id}/orders/{order_id}")
        self.assertEqual(cancelled.status_code, 200, cancelled.get_json())
        self.assertEqual(cancelled.get_json()["pending_orders"], [])

    def test_end_saves_crypto_report_instead_of_resetting(self):
        self.client.post(
            f"/api/training/{self.training_id}/trade",
            json={"action": "open_short", "order_type": "market", "margin": 100, "leverage": 5},
        )
        with patch.object(app_module.user_manager, "save_training_session", return_value=True) as save, \
                patch.object(app_module, "_persist_crypto_futures_state") as persist:
            response = self.client.post(f"/api/training/{self.training_id}/end")
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json()["market_type"], "crypto_perpetual")
        self.assertEqual(app_module.active_trainings[self.training_id]["status"], "ended")
        saved = save.call_args.args[1]
        self.assertEqual(saved["report_data"]["symbol"], "BTCUSDT")
        self.assertEqual(saved["report_data"]["simulator_type"], "isolated_futures")
        persist.assert_called_once()

    def test_reset_recreates_empty_futures_account(self):
        self.client.post(
            f"/api/training/{self.training_id}/trade",
            json={"action": "open_long", "order_type": "market", "margin": 100, "leverage": 5},
        )
        response = self.client.post(f"/api/training/{self.training_id}/reset")
        self.assertEqual(response.status_code, 200, response.get_json())
        snapshot = response.get_json()["snapshot"]
        self.assertEqual(snapshot["position"]["side"], "flat")
        self.assertEqual(snapshot["account"]["balance"], 10000)


class CryptoFuturesRuntimeRestoreTests(unittest.TestCase):
    def test_checkpoint_and_restore_rebuild_active_runtime_after_memory_clear(self):
        training_id = "crypto-restore"
        training = _training(training_id)
        training["futures_executor"].submit_order(
            action="open_long", order_type="market", margin=100, leverage=5,
        )
        training["futures_executor"].submit_order(
            action="open_long", order_type="limit", margin=100, leverage=5, limit_price=90,
        )
        training["crypto_session"].advance()
        bundle = training["crypto_bundle"]
        service = SimpleNamespace(get_bundle=lambda *args, **kwargs: bundle)

        with tempfile.TemporaryDirectory() as temp:
            database = Path(temp) / "training_history.db"
            with patch.object(
                app_module.user_manager.history_manager,
                "_get_user_db_path",
                return_value=str(database),
            ), patch.object(
                app_module.user_manager,
                "get_users",
                return_value=["tester"],
            ), patch.object(
                app_module,
                "_get_crypto_data_service",
                return_value=service,
            ):
                app_module._checkpoint_crypto_futures(training)
                app_module.active_trainings.pop(training_id, None)
                response = app_module.app.test_client().get(
                    f"/api/training/{training_id}/account"
                )
                restored = app_module.active_trainings.get(training_id)

        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertIsNotNone(restored)
        self.assertEqual(restored["id"], training_id)
        self.assertEqual(restored["crypto_session"].clock.current_time, START + timedelta(minutes=5))
        snapshot = restored["futures_executor"].snapshot()
        self.assertEqual(snapshot["position"]["side"], "long")
        self.assertEqual(len(restored["futures_executor"].engine.order_book.active_orders), 1)


if __name__ == "__main__":
    unittest.main()
