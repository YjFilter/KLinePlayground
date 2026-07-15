import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
from flask import jsonify

import backend.app_enhanced as app_module


class _FakeInstrument:
    def __init__(self, symbol, source="binance"):
        self.symbol = symbol
        self.source = source
        self.base_asset = symbol.removesuffix("USDT")
        self.quote_asset = "USDT"
        self.contract_type = "PERPETUAL"
        self.status = "TRADING"
        self.tick_size = "0.10"
        self.quantity_step = "0.001"
        self.min_quantity = "0.001"
        self.min_notional = "5"
        self.quote_turnover_24h = "1000000"


class _FakeUniverse:
    def search(self, query="", limit=20, refresh=False):
        values = [_FakeInstrument("BTCUSDT"), _FakeInstrument("ETHUSDT", "bybit")]
        return [item for item in values if query.upper() in item.symbol][:limit]


class _FakeCryptoSession:
    def __init__(self, bars, **kwargs):
        self.kwargs = kwargs

    def snapshot(self):
        return {
            "current_time": "2025-01-01 00:00:00",
            "kline_data": [],
            "volume_data": [],
        }


def _bundle(source="binance"):
    start = datetime(2024, 12, 2, tzinfo=timezone.utc)
    bars = pd.DataFrame([{
        "timestamp": start,
        "open": 1,
        "high": 1,
        "low": 1,
        "close": 1,
        "volume": 1,
        "turnover": 1,
    }])
    return SimpleNamespace(
        source=source,
        trade_bars=bars,
        mark_bars=bars,
        funding=(),
        instrument=_FakeInstrument("BTCUSDT", source),
    )


class CryptoAPITests(unittest.TestCase):
    def setUp(self):
        app_module.app.config["TESTING"] = True
        self.client = app_module.app.test_client()

    def test_crypto_constants_are_publicly_stable(self):
        self.assertEqual(app_module.MARKET_TYPE_CRYPTO_PERPETUAL, "crypto_perpetual")
        self.assertEqual(app_module.DATA_MODE_CRYPTO_5M, "crypto_5m")
        self.assertEqual(
            app_module.VALID_CRYPTO_PERIODS,
            ("5m", "15m", "30m", "1h", "4h", "daily", "weekly"),
        )

    def test_instrument_search_returns_normalized_payload(self):
        with patch.object(app_module, "_get_crypto_universe", return_value=_FakeUniverse()):
            response = self.client.get("/api/crypto/instruments?query=BTC&limit=10")
        self.assertEqual(response.status_code, 200, response.get_json())
        payload = response.get_json()
        self.assertEqual(payload["instruments"][0]["symbol"], "BTCUSDT")
        self.assertEqual(payload["instruments"][0]["quote_asset"], "USDT")

    def test_source_status_route_uses_normalized_status_payload(self):
        expected = [{"source": "binance", "available": True, "message": "ok"}]
        with patch.object(app_module, "_crypto_source_status_payload", return_value=expected):
            response = self.client.get("/api/crypto/sources/status")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["sources"], expected)

    def test_training_start_dispatches_crypto_payload(self):
        captured = {}

        def fake_start(**kwargs):
            captured.update(kwargs)
            return jsonify({"id": kwargs["training_id"], "market_type": "crypto_perpetual"})

        with patch.object(app_module, "_start_crypto_training", side_effect=fake_start):
            response = self.client.post("/api/training/start", json={
                "user": "tester",
                "market_type": "crypto_perpetual",
                "data_mode": "crypto_5m",
                "mode": "specified",
                "symbol": "BTCUSDT",
                "start_time": "2025-01-01T00:00:00Z",
                "period": "5m",
                "initial_capital": 10000,
                "leverage": 5,
                "max_training_days": 10,
            })
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(captured["payload"]["symbol"], "BTCUSDT")
        self.assertEqual(captured["period"], "5m")

    def test_training_start_rejects_invalid_crypto_period(self):
        response = self.client.post("/api/training/start", json={
            "user": "tester",
            "market_type": "crypto_perpetual",
            "data_mode": "crypto_5m",
            "mode": "specified",
            "symbol": "BTCUSDT",
            "start_time": "2025-01-01T00:00:00Z",
            "period": "4h_session",
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn("crypto", response.get_json()["error"].lower())

    def test_specified_crypto_start_allows_service_source_fallback(self):
        service = SimpleNamespace(get_bundle=lambda *args, **kwargs: _bundle("bybit"))
        with self.client.application.test_request_context():
            with patch.object(app_module, "_get_crypto_universe", side_effect=AssertionError("specified start must not refresh the universe")), \
                    patch.object(app_module, "_get_crypto_data_service", return_value=service), \
                    patch.object(app_module, "_initialize_crypto_futures"), \
                    patch.object(app_module.user_manager, "start_training_session", return_value=True) as start_session, \
                    patch("backend.crypto.session.CryptoReplaySession", _FakeCryptoSession), \
                    patch.object(service, "get_bundle", wraps=service.get_bundle) as get_bundle:
                response = app_module._start_crypto_training(
                    user="tester",
                    mode="specified",
                    period="5m",
                    initial_capital=10000,
                    training_id="fallback-test",
                    payload={"symbol": "BTCUSDT", "start_time": "2025-01-01T00:00:00Z"},
                    max_training_days=1,
                )
        self.assertEqual(response.get_json()["source"], "bybit")
        self.assertIsNone(get_bundle.call_args.kwargs["source"])
        self.assertEqual(start_session.call_args.args[1]["stock_code"], "BTCUSDT")
        self.assertEqual(app_module.active_trainings["fallback-test"]["id"], "fallback-test")
        app_module.active_trainings.pop("fallback-test", None)

    def test_random_crypto_start_retries_unusable_candidate(self):
        instruments = [_FakeInstrument("BADUSDT"), _FakeInstrument("BTCUSDT")]
        selections = []

        def select_random(**kwargs):
            selections.append(kwargs)
            return instruments.pop(0)

        universe = SimpleNamespace(select_random=select_random)
        attempts = []

        def get_bundle(symbol, *args, **kwargs):
            attempts.append(symbol)
            if symbol == "BADUSDT":
                raise ValueError("unusable range")
            return _bundle("binance")

        with self.client.application.test_request_context():
            with patch.object(app_module, "_get_crypto_universe", return_value=universe), \
                    patch.object(app_module, "_get_crypto_data_service", return_value=SimpleNamespace(get_bundle=get_bundle)), \
                    patch.object(app_module, "_random_crypto_timestamp", return_value=datetime(2025, 1, 1, tzinfo=timezone.utc)), \
                    patch.object(app_module, "_initialize_crypto_futures"), \
                    patch.object(app_module.user_manager, "start_training_session", return_value=True), \
                    patch("backend.crypto.session.CryptoReplaySession", _FakeCryptoSession):
                response = app_module._start_crypto_training(
                    user="tester",
                    mode="random",
                    period="5m",
                    initial_capital=10000,
                    training_id="retry-test",
                    payload={"date_start": "2025-01-01", "date_end": "2025-02-01"},
                    max_training_days=1,
                )
        self.assertEqual(attempts, ["BADUSDT", "BTCUSDT"])
        self.assertEqual(selections[0]["start"], datetime(2024, 12, 2, tzinfo=timezone.utc))
        self.assertEqual(selections[0]["end"], datetime(2025, 1, 1, 23, 55, tzinfo=timezone.utc))
        self.assertEqual(response.get_json()["symbol"], "BTCUSDT")
        app_module.active_trainings.pop("retry-test", None)

    def test_completed_crypto_history_uses_crypto_chart_window(self):
        report = {
            "market_type": "crypto_perpetual",
            "data_mode": "crypto_5m",
            "symbol": "BTCUSDT",
            "stock_code": "BTCUSDT",
            "source": "bybit",
            "period": "15m",
            "training_start": "2025-01-01 00:00:00",
            "training_end": "2025-01-02 00:00:00",
            "trade_details": [],
        }
        result = SimpleNamespace(to_dict=lambda: {
            "source": "bybit",
            "symbol": "BTCUSDT",
            "period": "15m",
            "kline_data": [],
            "volume_data": [],
            "read_only": True,
        })
        service = SimpleNamespace(load=lambda **kwargs: result)
        with patch.object(app_module.user_manager, "get_session_report", return_value=report), \
                patch("backend.crypto.chart_window.CryptoChartWindowService", return_value=service) as chart_service:
            response = self.client.get(
                "/api/users/tester/history/session/chart"
                "?period=15m&range_start=2025-01-01T00:00:00Z&range_end=2025-01-01T01:00:00Z"
            )
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json()["market_type"], "crypto_perpetual")
        chart_service.assert_called_once()


if __name__ == "__main__":
    unittest.main()
