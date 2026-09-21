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
from backend.crypto.persistence import CryptoFuturesRepository
from backend.crypto.session import CryptoReplaySession
from backend.crypto.trading import FuturesReplayExecutor


UTC = timezone.utc
START = datetime(2025, 1, 1, tzinfo=UTC)


def _bars(count=4):
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
        for index in range(count)
    ])


def _training(training_id="crypto-api", *, period="5m", bar_count=4, bars=None):
    if bars is None:
        bars = _bars(bar_count)
    session = CryptoReplaySession(
        bars,
        initial_time=START,
        symbol="BTCUSDT",
        source="binance",
        active_period=period,
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
        "period": period,
        "mode": "specified",
        "start_date": "2025-01-01",
        "training_start": "2025-01-01 00:00:00",
        "training_end": "2025-01-01 00:15:00",
        "max_training_days": 1,
        "initial_period": period,
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

    def test_stop_loss_survives_bars_that_do_not_reach_it(self):
        """回归（用户报告）：开仓后从图上拖出的止损线，不该在点下一根 K 线时就被平掉。

        根因：止损当时被当成"平仓限价单"提交，而引擎对卖出限价的撮合条件是
        ``high >= 限价``——挂在现价下方的止损必然立刻满足，于是下一根就成交。
        止损必须是**突破单**（``low <= 触发价`` 才成交）。
        """
        bars = pd.DataFrame([
            {"timestamp": START + timedelta(minutes=5 * i), "open": o, "high": h,
             "low": low, "close": c, "volume": 10, "turnover": 1000}
            for i, (o, h, low, c) in enumerate([
                (100, 102, 98, 100),   # 开仓价 100
                (100, 101, 97, 99),    # 未触及 95
                (99, 99, 90, 91),      # 跌破 95 → 止损在此成交
                (91, 92, 88, 90),
            ])
        ])
        training_id = "crypto-protective-regression"
        app_module.active_trainings[training_id] = _training(training_id, bars=bars)
        try:
            opened = self.client.post(
                f"/api/training/{training_id}/trade",
                json={"action": "open_long", "order_type": "market", "margin": 100, "leverage": 5},
            )
            self.assertEqual(opened.status_code, 200, opened.get_json())

            # 旧写法（平仓限价挂在现价下方）必须被拒绝，并给出可操作的提示
            rejected = self.client.post(
                f"/api/training/{training_id}/trade",
                json={"action": "close", "order_type": "limit", "limit_price": 95},
            )
            self.assertEqual(rejected.status_code, 400, rejected.get_json())
            self.assertEqual(rejected.get_json()["code"], "invalid_limit_direction")
            self.assertIn("突破单", rejected.get_json()["error"])

            # 正确写法：突破单当止损
            stop = self.client.post(
                f"/api/training/{training_id}/trade",
                json={"action": "close", "order_type": "breakout", "trigger_price": 95},
            )
            self.assertEqual(stop.status_code, 200, stop.get_json())
            self.assertEqual(stop.get_json()["order"]["order_type"], "breakout")

            # 推进一根 K 线：最低价 97 没碰到 95 → 必须仍在持仓
            untouched = self.client.post(f"/api/training/{training_id}/next")
            self.assertEqual(untouched.status_code, 200, untouched.get_json())
            self.assertEqual(untouched.get_json()["position"]["side"], "long")

            # 再推进一根：最低价 90 跌破 95 → 止损成交、持仓了结
            crossed = self.client.post(f"/api/training/{training_id}/next")
            self.assertEqual(crossed.status_code, 200, crossed.get_json())
            self.assertNotEqual(crossed.get_json()["position"]["side"], "long")
        finally:
            app_module.active_trainings.pop(training_id, None)

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

    def test_account_exposes_fee_aware_open_margin_constraints(self):
        response = self.client.get(f"/api/training/{self.training_id}/account")
        self.assertEqual(response.status_code, 200, response.get_json())
        constraints = response.get_json()["order_constraints"]
        self.assertEqual(constraints["maker_fee_rate"], 0.0)
        self.assertEqual(constraints["taker_fee_rate"], 0.0)
        self.assertEqual(constraints["leverage"], 5)
        self.assertEqual(constraints["quantity_step"], 0.001)
        self.assertEqual(constraints["min_quantity"], 0.001)
        self.assertEqual(constraints["min_notional"], 5.0)
        self.assertGreater(constraints["current_price"], 0)
        self.assertLessEqual(constraints["max_market_margin"], 10000)
        self.assertLessEqual(constraints["max_limit_margin"], 10000)

        order = self.client.post(
            f"/api/training/{self.training_id}/trade",
            json={
                "action": "open_short",
                "order_type": "market",
                "margin": constraints["max_market_margin"],
                "leverage": 5,
            },
        )
        self.assertEqual(order.status_code, 200, order.get_json())
        self.assertEqual(order.get_json()["position"]["side"], "short")

    def test_breakout_order_accepts_trigger_price_and_uses_taker_margin_constraint(self):
        account = self.client.get(f"/api/training/{self.training_id}/account").get_json()
        self.assertEqual(
            account["order_constraints"]["max_breakout_margin"],
            account["order_constraints"]["max_market_margin"],
        )

        response = self.client.post(
            f"/api/training/{self.training_id}/trade",
            json={
                "action": "open_long",
                "order_type": "breakout",
                "margin": 100,
                "leverage": 5,
                "trigger_price": 105,
            },
        )

        self.assertEqual(response.status_code, 200, response.get_json())
        order = response.get_json()["order"]
        self.assertEqual(order["order_type"], "breakout")
        self.assertEqual(order["trigger_price"], 105.0)
        self.assertEqual(response.get_json()["pending_orders"][0]["order_id"], order["order_id"])

    def test_crypto_next_returns_delta_and_compact_account_payload(self):
        training = app_module.active_trainings[self.training_id]
        training["_crypto_chart_window_start"] = datetime(2024, 1, 1, tzinfo=timezone.utc)
        training["_crypto_period_window_cache"] = {"cached": {}}
        training["_crypto_chart_base_frame"] = _bars().iloc[:1].copy()
        response = self.client.post(f"/api/training/{self.training_id}/next")

        self.assertEqual(response.status_code, 200, response.get_json())
        payload = response.get_json()
        self.assertIn("delta", payload)
        self.assertIn("new_bar", payload["delta"])
        self.assertNotIn("snapshot", payload)
        self.assertNotIn("kline_data", payload["delta"])
        self.assertIn("account", payload)
        self.assertIn("position", payload)
        self.assertIn("pending_orders", payload)
        self.assertNotIn("equity_snapshots", payload)
        self.assertNotIn("_crypto_period_window_cache", training)
        self.assertIn("_crypto_chart_window_end", training)
        self.assertEqual(len(training["_crypto_chart_base_frame"]), 2)
        self.assertEqual(
            training["_crypto_chart_base_frame"].iloc[-1]["timestamp"].to_pydatetime(),
            START + timedelta(minutes=5),
        )

    def test_hourly_next_appends_every_completed_five_minute_bar(self):
        training_id = "crypto-hourly-continuity"
        training = _training(training_id, period="1h", bar_count=13)
        training["_crypto_chart_window_start"] = START - timedelta(days=730)
        training["_crypto_chart_window_end"] = START
        training["_crypto_chart_base_frame"] = _bars(1)
        app_module.active_trainings[training_id] = training
        try:
            response = self.client.post(f"/api/training/{training_id}/next")

            self.assertEqual(response.status_code, 200, response.get_json())
            payload = response.get_json()
            self.assertEqual(len(payload["completed_times"]), 11)
            cached = training["_crypto_chart_base_frame"]
            self.assertEqual(len(cached), 12)
            self.assertEqual(
                list(cached["timestamp"]),
                list(pd.date_range(START, START + timedelta(minutes=55), freq="5min", tz="UTC")),
            )
        finally:
            app_module.active_trainings.pop(training_id, None)

    def test_forward_chart_append_avoids_renormalizing_the_full_history(self):
        training = _training("crypto-fast-append", period="1h", bar_count=13)
        training["_crypto_chart_base_frame"] = _bars(1)

        with patch(
            "backend.crypto.aggregator.normalize_base_bars",
            side_effect=AssertionError("forward append must use the sorted fast path"),
        ):
            app_module._append_crypto_chart_base_range(
                training,
                START,
                START + timedelta(minutes=55),
            )

        self.assertEqual(len(training["_crypto_chart_base_frame"]), 12)
        self.assertEqual(
            training["_crypto_chart_base_frame"].iloc[-1]["timestamp"].to_pydatetime(),
            START + timedelta(minutes=55),
        )

    def test_crypto_next_restores_active_runtime_before_route(self):
        training_id = "restore-route"
        training = _training(training_id)
        training["user"] = "restore-user"
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "history.db"
            repository = CryptoFuturesRepository(db_path)
            repository.save_session_metadata(
                training_id,
                market_type="crypto_perpetual",
                symbol="BTCUSDT",
                quote_currency="USDT",
                base_interval="5m",
                timezone="UTC",
                source="binance",
                simulator_type="isolated_futures",
            )
            repository.save_runtime_state(training_id, app_module._crypto_runtime_state(training))
            bundle = training["crypto_bundle"]
            service = SimpleNamespace(get_bundle=lambda *args, **kwargs: bundle)
            app_module.active_trainings.pop(training_id, None)
            try:
                with patch.object(app_module.user_manager, "get_users", return_value=["restore-user"]), \
                     patch.object(app_module.user_manager.history_manager, "_get_user_db_path", return_value=str(db_path)), \
                     patch.object(app_module, "_get_crypto_data_service", return_value=service):
                    response = self.client.post(f"/api/training/{training_id}/next")
                payload = response.get_json()
                self.assertEqual(response.status_code, 200, payload)
                self.assertEqual(payload["delta"]["current_time"], "2025-01-01 00:05:00")
                self.assertNotIn("snapshot", payload)
                self.assertIn(training_id, app_module.active_trainings)
            finally:
                app_module.active_trainings.pop(training_id, None)

    def test_crypto_next_schedules_checkpoint_instead_of_writing_synchronously(self):
        with patch.object(app_module, "_schedule_crypto_checkpoint") as schedule:
            response = self.client.post(f"/api/training/{self.training_id}/next")

        self.assertEqual(response.status_code, 200, response.get_json())
        schedule.assert_called_once_with(app_module.active_trainings[self.training_id])
        self.checkpoint.assert_not_called()

    def test_fee_rates_can_be_updated_before_trading_and_affect_new_fills(self):
        response = self.client.post(
            f"/api/training/{self.training_id}/fee-rates",
            json={"maker_fee_rate": 0.0001, "taker_fee_rate": 0.0003},
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        constraints = response.get_json()["order_constraints"]
        self.assertEqual(constraints["maker_fee_rate"], 0.0001)
        self.assertEqual(constraints["taker_fee_rate"], 0.0003)

        order = self.client.post(
            f"/api/training/{self.training_id}/trade",
            json={"action": "open_long", "order_type": "market", "margin": 100, "leverage": 5},
        )
        self.assertEqual(order.status_code, 200, order.get_json())
        fill = order.get_json()["fills"][-1]
        self.assertAlmostEqual(fill["fee"], fill["quantity"] * fill["price"] * 0.0003)
        self.assertGreaterEqual(self.checkpoint.call_count, 2)

    def test_fee_rates_reject_changes_after_a_position_is_open(self):
        order = self.client.post(
            f"/api/training/{self.training_id}/trade",
            json={"action": "open_long", "order_type": "market", "margin": 100, "leverage": 5},
        )
        self.assertEqual(order.status_code, 200, order.get_json())

        response = self.client.post(
            f"/api/training/{self.training_id}/fee-rates",
            json={"maker_fee_rate": 0.0001, "taker_fee_rate": 0.0003},
        )
        self.assertEqual(response.status_code, 400, response.get_json())
        self.assertIn("空仓", response.get_json()["error"])

    def test_unaffordable_crypto_order_returns_localized_400_error(self):
        # 手续费默认 0：margin=10000 恰好等于可用余额可成交，超过（10001）才会被拒
        response = self.client.post(
            f"/api/training/{self.training_id}/trade",
            json={"action": "open_long", "order_type": "market", "margin": 10001, "leverage": 5},
        )
        self.assertEqual(response.status_code, 400, response.get_json())
        self.assertEqual(response.get_json()["code"], "insufficient_margin")
        self.assertIn("手续费", response.get_json()["error"])
        self.assertNotIn("insufficient available margin", response.get_json()["error"])

    def test_invalid_limit_direction_returns_stable_error_code_and_message(self):
        response = self.client.post(
            f"/api/training/{self.training_id}/trade",
            json={
                "action": "open_long",
                "order_type": "limit",
                "margin": 100,
                "leverage": 5,
                "limit_price": 100,
            },
        )

        self.assertEqual(response.status_code, 400, response.get_json())
        payload = response.get_json()
        self.assertEqual(payload["code"], "invalid_limit_direction")
        self.assertEqual(payload["message"], payload["error"])

    def test_duplicate_pending_entry_is_rejected_until_original_is_cancelled(self):
        first = self.client.post(
            f"/api/training/{self.training_id}/trade",
            json={
                "action": "open_long",
                "order_type": "limit",
                "margin": 100,
                "leverage": 5,
                "limit_price": 99,
            },
        )
        self.assertEqual(first.status_code, 200, first.get_json())

        duplicate = self.client.post(
            f"/api/training/{self.training_id}/trade",
            json={
                "action": "open_long",
                "order_type": "breakout",
                "margin": 100,
                "leverage": 5,
                "trigger_price": 105,
            },
        )

        self.assertEqual(duplicate.status_code, 400, duplicate.get_json())
        self.assertEqual(duplicate.get_json()["code"], "duplicate_pending_order")

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

        self.checkpoint.reset_mock()
        cancelled = self.client.delete(f"/api/training/{self.training_id}/orders/{order_id}")
        self.assertEqual(cancelled.status_code, 200, cancelled.get_json())
        self.assertEqual(cancelled.get_json()["pending_orders"], [])
        self.checkpoint.assert_called_once_with(app_module.active_trainings[self.training_id])

    def test_cancel_inactive_crypto_order_returns_authoritative_pending_orders(self):
        response = self.client.post(
            f"/api/training/{self.training_id}/trade",
            json={
                "action": "open_short",
                "order_type": "limit",
                "margin": 100,
                "leverage": 5,
                "limit_price": 105,
            },
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        order_id = response.get_json()["order"]["order_id"]
        order_book = app_module.active_trainings[self.training_id]["futures_executor"].engine.order_book
        self.assertTrue(order_book.cancel_order(order_id, START + timedelta(minutes=1)))

        cancelled = self.client.delete(f"/api/training/{self.training_id}/orders/{order_id}")

        self.assertEqual(cancelled.status_code, 409, cancelled.get_json())
        self.assertEqual(cancelled.get_json()["code"], "order_inactive")
        self.assertEqual(cancelled.get_json()["order_status"], "cancelled")
        self.assertEqual(cancelled.get_json()["pending_orders"], [])

    def test_end_saves_crypto_report_instead_of_resetting(self):
        training = app_module.active_trainings[self.training_id]
        training["_crypto_chart_window_start"] = datetime(2024, 1, 1, tzinfo=timezone.utc)
        training["_crypto_chart_window_end"] = datetime(2025, 1, 1, tzinfo=timezone.utc)
        training["_crypto_period_window_cache"] = {"cached": {}}
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
        self.assertNotIn("_crypto_chart_window_start", training)
        self.assertNotIn("_crypto_chart_window_end", training)
        self.assertNotIn("_crypto_period_window_cache", training)

    def test_reset_preserves_custom_fee_rates(self):
        updated = self.client.post(
            f"/api/training/{self.training_id}/fee-rates",
            json={"maker_fee_rate": 0.0001, "taker_fee_rate": 0.0003},
        )
        self.assertEqual(updated.status_code, 200, updated.get_json())

        training = app_module.active_trainings[self.training_id]
        training["_crypto_chart_window_start"] = datetime(2024, 1, 1, tzinfo=timezone.utc)
        training["_crypto_chart_window_end"] = datetime(2025, 1, 1, tzinfo=timezone.utc)
        training["_crypto_period_window_cache"] = {"cached": {}}
        response = self.client.post(f"/api/training/{self.training_id}/reset")

        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertNotIn("_crypto_chart_window_start", training)
        self.assertNotIn("_crypto_chart_window_end", training)
        self.assertNotIn("_crypto_period_window_cache", training)
        constraints = response.get_json()["snapshot"]["order_constraints"]
        self.assertEqual(constraints["maker_fee_rate"], 0.0001)
        self.assertEqual(constraints["taker_fee_rate"], 0.0003)

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
        history_start = START - timedelta(minutes=10)
        history_frame = _bars(3)
        history_frame["timestamp"] = pd.date_range(
            history_start, periods=3, freq="5min", tz="UTC",
        )
        training.update({
            "history_years": 2,
            "_crypto_history_start": history_start,
            "_crypto_history_end": START + timedelta(minutes=5),
            "_crypto_chart_window_start": history_start,
            "_crypto_chart_window_end": START + timedelta(minutes=5),
            "_crypto_chart_base_frame": history_frame,
        })
        service = SimpleNamespace(
            get_bundle=lambda *args, **kwargs: bundle,
            get_chart_bars=lambda *args, **kwargs: ("binance", history_frame),
        )

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
        self.assertEqual(restored["history_years"], 2)
        self.assertEqual(restored["_crypto_history_start"], history_start)
        self.assertEqual(len(restored["_crypto_chart_base_frame"]), 3)
        snapshot = restored["futures_executor"].snapshot()
        self.assertEqual(snapshot["position"]["side"], "long")
        self.assertEqual(len(restored["futures_executor"].engine.order_book.active_orders), 1)


if __name__ == "__main__":
    unittest.main()
