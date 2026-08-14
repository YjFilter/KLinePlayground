import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
from flask import jsonify

import backend.app_enhanced as app_module
from backend.crypto.models import CryptoInstrument, CryptoRange
from backend.crypto.session import CryptoReplaySession


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
        self.base_bars = bars
        self.kwargs = kwargs

    def snapshot(self, **kwargs):
        return {
            "current_time": "2025-01-01 00:00:00",
            "kline_data": [],
            "volume_data": [],
        }


class _FakePeriodSession:
    def __init__(self):
        self.period = "5m"
        self.max_bars = None
        self.range_start = None
        self.range_end = None

    def snapshot(self, *, max_bars=None, range_start=None, range_end=None):
        self.max_bars = max_bars
        self.range_start = range_start
        self.range_end = range_end
        return {
            "market_type": "crypto_perpetual",
            "data_mode": "crypto_5m",
            "active_period": self.period,
            "period": self.period,
            "current_time": "2025-01-01 00:00:00",
            "kline_data": [],
            "volume_data": [],
        }

    def set_period(self, period, *, max_bars=None, range_start=None, range_end=None):
        self.period = period
        return self.snapshot(max_bars=max_bars, range_start=range_start, range_end=range_end)


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
            ("1m", "3m", "5m", "15m", "30m", "1h", "2h", "3h", "4h", "6h", "8h", "12h", "daily", "2d", "3d", "weekly"),
        )

    def test_crypto_universe_prefers_persisted_instruments_before_network(self):
        cached = CryptoInstrument(
            "BTCUSDT",
            "binance",
            "BTC",
            "USDT",
            "PERPETUAL",
            "TRADING",
            datetime(2020, 1, 1, tzinfo=timezone.utc),
            Decimal("0.1"),
            Decimal("0.001"),
            Decimal("0.001"),
            Decimal("5"),
            Decimal("100"),
        )
        cache = SimpleNamespace(list_instruments=lambda: [cached])
        service = SimpleNamespace(cache=cache)
        network_source = SimpleNamespace(name="network", list_instruments=lambda: (_ for _ in ()).throw(AssertionError("network should not be called")))
        with patch.object(app_module, "_crypto_universe_instance", None), patch.object(app_module, "_get_crypto_instrument_cache", return_value=cache), patch.object(app_module, "_get_crypto_sources", return_value=(network_source,)):
            result = app_module._get_crypto_universe().search("BTC")
        self.assertEqual([item.symbol for item in result], ["BTCUSDT"])

    def test_crypto_universe_skips_network_when_cache_has_data(self):
        """Explicit mock proof that network list_instruments() is never called."""
        from unittest.mock import Mock
        cached_btc = CryptoInstrument("BTCUSDT", "binance", "BTC", "USDT", "PERPETUAL", "TRADING", datetime(2020, 1, 1, tzinfo=timezone.utc), Decimal("0.1"), Decimal("0.001"), Decimal("0.001"), Decimal("5"), Decimal("100"))
        cached_eth = CryptoInstrument("ETHUSDT", "binance", "ETH", "USDT", "PERPETUAL", "TRADING", datetime(2020, 1, 1, tzinfo=timezone.utc), Decimal("0.01"), Decimal("0.01"), Decimal("0.01"), Decimal("5"), Decimal("90"))
        cache = SimpleNamespace(list_instruments=lambda: [cached_btc, cached_eth])
        service = SimpleNamespace(cache=cache)
        binance_mock = Mock()
        binance_mock.name = "binance"
        binance_mock.list_instruments.side_effect = AssertionError("binance list_instruments must not be called when cache has data")
        bybit_mock = Mock()
        bybit_mock.name = "bybit"
        bybit_mock.list_instruments.side_effect = AssertionError("bybit list_instruments must not be called when cache has data")
        with patch.object(app_module, "_crypto_universe_instance", None), patch.object(app_module, "_get_crypto_instrument_cache", return_value=cache), patch.object(app_module, "_get_crypto_sources", return_value=(binance_mock, bybit_mock)):
            universe = app_module._get_crypto_universe()
            result = universe.search("BTC")
            result2 = universe.search("ETH")
        self.assertEqual([item.symbol for item in result], ["BTCUSDT"])
        self.assertEqual([item.symbol for item in result2], ["ETHUSDT"])
        binance_mock.list_instruments.assert_not_called()
        bybit_mock.list_instruments.assert_not_called()

    def test_crypto_universe_does_not_build_network_sources_when_cache_has_data(self):
        cached = CryptoInstrument("BTCUSDT", "binance", "BTC", "USDT", "PERPETUAL", "TRADING", datetime(2020, 1, 1, tzinfo=timezone.utc), Decimal("0.1"), Decimal("0.001"), Decimal("0.001"), Decimal("5"), Decimal("100"))
        cache = SimpleNamespace(list_instruments=lambda: [cached])
        with patch.object(app_module, "_crypto_universe_instance", None), \
                patch.object(app_module, "_get_crypto_instrument_cache", return_value=cache, create=True), \
                patch.object(app_module, "_get_crypto_sources") as get_sources:
            result = app_module._get_crypto_universe().search("BTC")

        self.assertEqual([item.symbol for item in result], ["BTCUSDT"])
        get_sources.assert_not_called()

    def test_crypto_universe_falls_back_to_network_when_cache_empty(self):
        """When the local cache has no instruments, the universe falls back to network sources."""
        from unittest.mock import Mock
        cache = SimpleNamespace(list_instruments=lambda: [])
        service = SimpleNamespace(cache=cache)
        network_instrument = CryptoInstrument("BTCUSDT", "binance", "BTC", "USDT", "PERPETUAL", "TRADING", datetime(2020, 1, 1, tzinfo=timezone.utc), Decimal("0.1"), Decimal("0.001"), Decimal("0.001"), Decimal("5"), Decimal("100"))
        binance_mock = Mock()
        binance_mock.name = "binance"
        binance_mock.list_instruments.return_value = [network_instrument]
        with patch.object(app_module, "_crypto_universe_instance", None), patch.object(app_module, "_get_crypto_instrument_cache", return_value=cache), patch.object(app_module, "_get_crypto_sources", return_value=(binance_mock,)):
            universe = app_module._get_crypto_universe()
            result = universe.search("BTC")
        self.assertEqual([item.symbol for item in result], ["BTCUSDT"])
        binance_mock.list_instruments.assert_called_once()

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
        service = SimpleNamespace(
            get_bundle=lambda *args, **kwargs: _bundle("bybit"),
            prepare_chart_bars=lambda symbol, start, end, **kwargs: ("bybit", _bundle("bybit").trade_bars),
        )
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
                    payload={"symbol": "BTC", "start_time": "2025-01-01T00:00:00Z", "history_years": 2},
                    max_training_days=1,
                )
        self.assertEqual(response.get_json()["source"], "bybit")
        self.assertEqual(get_bundle.call_args.args[0], "BTCUSDT")
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

        def prepare_chart_bars(symbol, start, end, **kwargs):
            return "binance", _bundle("binance").trade_bars

        with self.client.application.test_request_context():
            with patch.object(app_module, "_get_crypto_universe", return_value=universe), \
                    patch.object(app_module, "_get_crypto_data_service", return_value=SimpleNamespace(
                        get_bundle=get_bundle,
                        prepare_chart_bars=prepare_chart_bars,
                    )), \
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
                    payload={"date_start": "2025-01-01", "date_end": "2025-02-01", "history_years": 2},
                    max_training_days=1,
                )
        self.assertEqual(attempts, ["BADUSDT", "BTCUSDT"])
        self.assertEqual(selections[0]["start"], datetime(2024, 12, 2, tzinfo=timezone.utc))
        self.assertEqual(selections[0]["end"], datetime(2025, 1, 1, 23, 59, tzinfo=timezone.utc))
        self.assertEqual(response.get_json()["symbol"], "BTCUSDT")
        app_module.active_trainings.pop("retry-test", None)

    def test_stale_crypto_period_request_cannot_overwrite_newer_period(self):
        training_id = "period-order-test"
        session = _FakePeriodSession()
        app_module.active_trainings[training_id] = {
            "id": training_id,
            "user": "tester",
            "market_type": "crypto_perpetual",
            "data_mode": "crypto_5m",
            "period": "5m",
            "crypto_session": session,
        }
        try:
            with patch.object(app_module, "_persist_crypto_period") as persist:
                newer = self.client.post(
                    f"/api/training/{training_id}/period",
                    json={"period": "1h", "request_id": 2},
                )
                stale = self.client.post(
                    f"/api/training/{training_id}/period",
                    json={"period": "15m", "request_id": 1},
                )

            self.assertEqual(newer.status_code, 200)
            self.assertEqual(stale.status_code, 200)
            self.assertEqual(session.period, "1h")
            self.assertEqual(app_module.active_trainings[training_id]["period"], "1h")
            persist.assert_called_once_with(app_module.active_trainings[training_id], "1h")
        finally:
            app_module.active_trainings.pop(training_id, None)

    def test_crypto_period_switch_preserves_explicit_loaded_window(self):
        training_id = "period-window-test"
        session = _FakePeriodSession()
        app_module.active_trainings[training_id] = {
            "id": training_id,
            "user": "tester",
            "market_type": "crypto_perpetual",
            "data_mode": "crypto_5m",
            "period": "5m",
            "crypto_session": session,
        }
        try:
            with patch.object(app_module, "_persist_crypto_period"):
                response = self.client.post(
                    f"/api/training/{training_id}/period",
                    json={
                        "period": "15m",
                        "range_start": datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp(),
                        "range_end": datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp(),
                    },
                )

            self.assertEqual(response.status_code, 200, response.get_json())
            self.assertIsNone(session.max_bars)
        finally:
            app_module.active_trainings.pop(training_id, None)
    def test_loaded_crypto_chart_window_is_remembered_for_period_switch(self):
        training_id = "remembered-window-test"
        session = _FakePeriodSession()
        training = {
            "id": training_id,
            "user": "tester",
            "market_type": "crypto_perpetual",
            "data_mode": "crypto_5m",
            "period": "daily",
            "crypto_session": session,
            "symbol": "BTCUSDT",
            "source": "binance",
            "training_start": "2025-01-01 00:00:00",
            "training_end": "2025-12-31 00:00:00",
            "trade_markers": [],
        }
        app_module.active_trainings[training_id] = training
        remembered_start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        current_time = datetime(2025, 7, 22, 23, 55, tzinfo=timezone.utc)
        result = SimpleNamespace(
            window_start=remembered_start,
            window_end=current_time,
            has_earlier=False,
            to_dict=lambda: {
                "source": "binance",
                "symbol": "BTCUSDT",
                "period": "daily",
                "window_start": "2024-01-01 00:00:00",
                "window_end": "2025-07-22 23:55:00",
                "kline_data": [],
                "volume_data": [],
                "has_earlier": False,
                "has_later": False,
                "read_only": False,
            },
        )
        service = SimpleNamespace(load=lambda **kwargs: result)
        try:
            with patch("backend.crypto.chart_window.CryptoChartWindowService", return_value=service):
                loaded = self.client.get(
                    f"/api/training/{training_id}/chart-window"
                    "?period=daily&range_start=2024-01-01T00:00:00Z"
                    "&range_end=2025-07-22T23:55:00Z"
                )
            self.assertEqual(loaded.status_code, 200, loaded.get_json())

            with patch.object(app_module, "_persist_crypto_period"):
                switched = self.client.post(
                    f"/api/training/{training_id}/period",
                    json={"period": "4h"},
                )

            self.assertEqual(switched.status_code, 200, switched.get_json())
            self.assertEqual(session.max_bars, app_module.CRYPTO_PERIOD_SNAPSHOT_BAR_LIMIT)
            self.assertIsNone(session.range_start)
            self.assertIsNone(session.range_end)
        finally:
            app_module.active_trainings.pop(training_id, None)
    def test_period_switch_uses_offline_window_beyond_session_context(self):
        training_id = "extended-period-window-test"
        old_start = datetime(2024, 6, 22, tzinfo=timezone.utc)
        session_start = datetime(2025, 6, 22, tzinfo=timezone.utc)
        recent_times = pd.date_range(session_start, periods=30 * 24 * 12 + 1, freq="5min", tz="UTC")
        old_times = pd.date_range(old_start, periods=12, freq="5min", tz="UTC")
        future_time = recent_times[-1] + pd.Timedelta(minutes=5)

        def bars(times):
            return pd.DataFrame([
                {
                    "timestamp": timestamp,
                    "open": 100 + index,
                    "high": 102 + index,
                    "low": 99 + index,
                    "close": 101 + index,
                    "volume": 10 + index,
                    "turnover": 1000 + index,
                }
                for index, timestamp in enumerate(times)
            ])

        session_bars = bars(recent_times)
        cached_bars = pd.concat([
            bars(old_times),
            session_bars,
            bars(pd.DatetimeIndex([future_time])),
        ], ignore_index=True)
        current_time = recent_times[-1].to_pydatetime()
        session = CryptoReplaySession(
            session_bars,
            initial_time=current_time,
            symbol="BTCUSDT",
            source="binance",
            active_period="daily",
        )

        class Cache:
            def coverage(self, source, symbol, kind):
                return CryptoRange(old_start, future_time.to_pydatetime())

        class DataService:
            cache = Cache()

            def __init__(self):
                self.chart_load_calls = 0

            def get_chart_bars(self, symbol, start, end, *, source=None):
                self.chart_load_calls += 1
                visible = cached_bars.loc[
                    (cached_bars["timestamp"] >= pd.Timestamp(start))
                    & (cached_bars["timestamp"] <= pd.Timestamp(end))
                ].reset_index(drop=True)
                return source or "binance", visible

        training = {
            "id": training_id,
            "user": "tester",
            "market_type": "crypto_perpetual",
            "data_mode": "crypto_5m",
            "period": "daily",
            "crypto_session": session,
            "symbol": "BTCUSDT",
            "source": "binance",
            "training_start": session_start.strftime("%Y-%m-%d %H:%M:%S"),
            "training_end": current_time.strftime("%Y-%m-%d %H:%M:%S"),
            "trade_markers": [],
        }
        app_module.active_trainings[training_id] = training
        data_service = DataService()
        try:
            with patch.object(app_module, "_get_crypto_data_service", return_value=data_service):
                loaded = self.client.get(
                    f"/api/training/{training_id}/chart-window"
                    f"?period=daily&range_start={old_start.strftime('%Y-%m-%dT%H:%M:%SZ')}"
                    f"&range_end={current_time.strftime('%Y-%m-%dT%H:%M:%SZ')}"
                )
                self.assertEqual(loaded.status_code, 200, loaded.get_json())
                with patch.object(app_module, "_persist_crypto_period"):
                    for request_id, period in enumerate(("4h", "1h", "15m"), start=1):
                        switched = self.client.post(
                            f"/api/training/{training_id}/period",
                            json={"period": period, "request_id": request_id, "compact_chart": True},
                        )
                        payload = switched.get_json()
                        self.assertEqual(switched.status_code, 200, payload)
                        self.assertEqual(payload["active_period"], period)
                        self.assertEqual(payload["current_time"], current_time.strftime("%Y-%m-%d %H:%M:%S"))
                        self.assertEqual(payload["window_start"], old_start.strftime("%Y-%m-%d %H:%M:%S"))
                        if period in app_module.CRYPTO_FINE_PERIOD_SECONDS:
                            self.assertTrue(payload["has_earlier_render"])
                            self.assertGreater(payload["render_start"], payload["history_start"])
                        else:
                            self.assertTrue(payload["kline_data"][0]["time"].startswith("2024-06-22"))
                        self.assertLessEqual(payload["kline_data"][-1]["time"], payload["current_time"])
                        self.assertEqual(
                            set(payload["kline_data"][0]),
                            {"time", "open", "high", "low", "close", "volume"},
                        )
                        self.assertEqual(payload["volume_data"], [])
                self.assertEqual(data_service.chart_load_calls, 1)
                self.assertIn("_crypto_chart_base_frame", training)
        finally:
            app_module.active_trainings.pop(training_id, None)

    def test_period_switch_repairs_missing_session_tail_before_aggregation(self):
        training_id = "repair-session-tail-test"
        current_time = datetime(2025, 1, 1, 0, 55, tzinfo=timezone.utc)
        session_bars = pd.DataFrame([
            {
                "timestamp": datetime(2025, 1, 1, 0, minute, tzinfo=timezone.utc),
                "open": 100 + index,
                "high": 102 + index,
                "low": 99 + index,
                "close": 101 + index,
                "volume": 10,
                "turnover": 1000,
            }
            for index, minute in enumerate(range(0, 60, 5))
        ])
        session = CryptoReplaySession(
            session_bars,
            initial_time=current_time,
            symbol="BTCUSDT",
            source="binance",
            active_period="1h",
        )

        class Cache:
            def coverage(self, source, symbol, kind):
                return CryptoRange(session_bars.iloc[0]["timestamp"].to_pydatetime(), current_time)

        training = {
            "id": training_id,
            "user": "tester",
            "market_type": "crypto_perpetual",
            "data_mode": "crypto_5m",
            "period": "1h",
            "crypto_session": session,
            "symbol": "BTCUSDT",
            "source": "binance",
            "training_start": "2025-01-01 00:00:00",
            "training_end": "2025-01-02 00:00:00",
            "trade_markers": [],
            "_crypto_chart_window_start": datetime(2024, 1, 1, tzinfo=timezone.utc),
            "_crypto_chart_window_end": current_time,
            "_crypto_chart_base_frame": session_bars.iloc[[0, -1]].copy(),
        }
        app_module.active_trainings[training_id] = training
        try:
            with patch.object(app_module, "_get_crypto_data_service", return_value=SimpleNamespace(cache=Cache())), \
                    patch.object(app_module, "_persist_crypto_period"):
                response = self.client.post(
                    f"/api/training/{training_id}/period",
                    json={"period": "1h", "request_id": 1},
                )

            self.assertEqual(response.status_code, 200, response.get_json())
            payload = response.get_json()
            self.assertEqual(payload["kline_data"][-1]["source_bar_count"], 12)
            self.assertTrue(payload["kline_data"][-1]["complete"])
            self.assertEqual(len(training["_crypto_chart_base_frame"]), 12)
        finally:
            app_module.active_trainings.pop(training_id, None)
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

    def test_crypto_period_switch_skips_full_checkpoint_and_persists_period_only(self):
        training_id = "period-cache-test"
        app_module.active_trainings[training_id] = {
            "id": training_id,
            "user": "tester",
            "market_type": "crypto_perpetual",
            "data_mode": "crypto_5m",
            "period": "5m",
            "crypto_session": _FakePeriodSession(),
        }
        try:
            with patch.object(
                app_module,
                "_checkpoint_crypto_futures",
                side_effect=AssertionError("period switch must not export the full runtime"),
            ), patch(
                "backend.crypto.persistence.CryptoFuturesRepository.update_runtime_period",
                create=True,
            ) as update_runtime_period, patch.object(
                app_module.user_manager.history_manager,
                "_get_user_db_path",
                return_value=":memory:",
            ):
                response = self.client.post(
                    f"/api/training/{training_id}/period",
                    json={"period": "15m"},
                )

            self.assertEqual(response.status_code, 200, response.get_json())
            self.assertEqual(response.get_json()["active_period"], "15m")
            self.assertEqual(app_module.active_trainings[training_id]["period"], "15m")
            self.assertEqual(
                app_module.active_trainings[training_id]["crypto_session"].max_bars,
                app_module.CRYPTO_PERIOD_SNAPSHOT_BAR_LIMIT,
            )
            update_runtime_period.assert_called_once_with(training_id, "15m")
        finally:
            app_module.active_trainings.pop(training_id, None)


if __name__ == "__main__":
    unittest.main()
