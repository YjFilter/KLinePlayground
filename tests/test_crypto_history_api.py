import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

import backend.app_enhanced as app_module


UTC = timezone.utc
START = datetime(2025, 1, 1, tzinfo=UTC)


def _bars(start, count):
    timestamps = pd.date_range(start=start, periods=count, freq="5min", tz="UTC")
    return pd.DataFrame({
        "timestamp": timestamps,
        "open": range(count),
        "high": [value + 1 for value in range(count)],
        "low": [value - 1 for value in range(count)],
        "close": [value + 0.5 for value in range(count)],
        "volume": [1.0] * count,
        "turnover": [1.0] * count,
        "source": ["binance"] * count,
        "symbol": ["BTCUSDT"] * count,
        "kind": ["trade"] * count,
    })


class _FakePrepareManager:
    def __init__(self, prepared=None):
        self.prepared = prepared
        self.calls = []

    def create(self, user, payload):
        self.calls.append(("create", user, payload))
        return {"job_id": "job-1", "status": "queued", "percent": 0}

    def get(self, job_id, user):
        self.calls.append(("get", job_id, user))
        return {"job_id": job_id, "status": "downloading", "percent": 50}

    def cancel(self, job_id, user):
        self.calls.append(("cancel", job_id, user))
        return {"job_id": job_id, "status": "cancelled", "percent": 50}

    def consume(self, job_id, user):
        self.calls.append(("consume", job_id, user))
        return self.prepared


class _FakeSession:
    def __init__(self, bars, **kwargs):
        self.base_bars = bars
        self.kwargs = kwargs

    def snapshot(self, **kwargs):
        return {
            "active_period": self.kwargs["active_period"],
            "period": self.kwargs["active_period"],
            "current_time": START.strftime("%Y-%m-%d %H:%M:%S"),
            "current_bar_complete": True,
            "next_boundary": None,
            "current_base_bar": None,
            "finished": False,
            "available_periods": list(app_module.VALID_CRYPTO_PERIODS),
            "base_interval": "5m",
            "kline_data": [],
            "volume_data": [],
        }

    def set_period(self, period, **kwargs):
        self.kwargs["active_period"] = period
        return self.snapshot(**kwargs)


class CryptoHistoryAPITests(unittest.TestCase):
    def setUp(self):
        app_module.app.config["TESTING"] = True
        self.client = app_module.app.test_client()

    def tearDown(self):
        app_module.active_trainings.clear()

    def test_history_years_defaults_to_two_and_accepts_two_through_five(self):
        self.assertEqual(app_module._parse_crypto_history_years({}), 2)
        for value in (2, 3, 4, 5, "2", "5"):
            self.assertEqual(app_module._parse_crypto_history_years({"history_years": value}), int(value))

    def test_history_years_rejects_out_of_range_and_fractional_values(self):
        for value in (1, 6, 2.5, "2.5", True):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "history_years"):
                app_module._parse_crypto_history_years({"history_years": value})

    def test_history_prepare_routes_submit_poll_and_cancel_for_the_same_user(self):
        manager = _FakePrepareManager()
        with patch.object(app_module, "_get_crypto_history_prepare_manager", return_value=manager):
            submitted = self.client.post("/api/crypto/history/prepare", json={
                "user": "tester",
                "market_type": "crypto_perpetual",
                "mode": "specified",
                "symbol": "BTCUSDT",
                "start_time": "2025-01-01T00:00:00Z",
            })
            polled = self.client.get("/api/crypto/history/prepare/job-1?user=tester")
            cancelled = self.client.delete("/api/crypto/history/prepare/job-1?user=tester")

        self.assertEqual(submitted.status_code, 202, submitted.get_json())
        self.assertEqual(submitted.get_json()["job_id"], "job-1")
        self.assertEqual(polled.get_json()["percent"], 50)
        self.assertEqual(cancelled.get_json()["status"], "cancelled")
        submitted_payload = manager.calls[0][2]
        self.assertEqual(submitted_payload["history_years"], 2)

    def test_crypto_start_rejects_invalid_history_years_with_400(self):
        response = self.client.post("/api/training/start", json={
            "user": "tester",
            "market_type": "crypto_perpetual",
            "data_mode": "crypto_5m",
            "mode": "specified",
            "symbol": "BTCUSDT",
            "start_time": "2025-01-01T00:00:00Z",
            "period": "5m",
            "history_years": 1,
        })
        self.assertEqual(response.status_code, 400, response.get_json())
        self.assertIn("history_years", response.get_json()["error"])

    def test_start_consumes_prepared_history_once_and_stores_full_runtime_bounds(self):
        history_start = datetime(2023, 1, 1, tzinfo=UTC)
        history = _bars(START - timedelta(minutes=10), 4)
        bundle = SimpleNamespace(
            source="binance",
            trade_bars=_bars(START - timedelta(minutes=5), 3),
            mark_bars=_bars(START - timedelta(minutes=5), 3),
            funding=(),
            instrument=SimpleNamespace(symbol="BTCUSDT"),
        )
        prepared = {
            "symbol": "BTCUSDT",
            "source": "binance",
            "instrument": bundle.instrument,
            "bundle": bundle,
            "training_start": START,
            "context_start": START - timedelta(days=30),
            "range_end": START + timedelta(days=1) - timedelta(minutes=5),
            "history_start": history_start,
            "history_end": START,
            "history_years": 2,
            "history_frame": history,
            "training_days": 1,
            "summary": {},
        }
        manager = _FakePrepareManager(prepared)
        payload = {
            "symbol": "BTCUSDT",
            "start_time": START.isoformat(),
            "history_years": 2,
            "history_prepare_id": "job-1",
        }
        with self.client.application.test_request_context(), \
                patch.object(app_module, "_get_crypto_history_prepare_manager", return_value=manager), \
                patch.object(app_module, "_initialize_crypto_futures"), \
                patch.object(app_module, "_checkpoint_crypto_futures"), \
                patch.object(app_module.user_manager, "start_training_session", return_value=True), \
                patch("backend.crypto.session.CryptoReplaySession", _FakeSession):
            response = app_module._start_crypto_training(
                user="tester",
                mode="specified",
                period="5m",
                initial_capital=10000,
                training_id="prepared-test",
                payload=payload,
                max_training_days=1,
            )

        self.assertEqual(response.status_code, 200, response.get_json())
        training = app_module.active_trainings["prepared-test"]
        self.assertEqual(manager.calls, [("consume", "job-1", "tester")])
        self.assertEqual(training["history_years"], 2)
        self.assertEqual(training["_crypto_history_start"], history_start)
        self.assertEqual(training["_crypto_history_end"], START)
        self.assertEqual(len(training["_crypto_chart_base_frame"]), 3)
        self.assertLessEqual(
            training["_crypto_chart_base_frame"]["timestamp"].max().to_pydatetime(),
            START,
        )
        self.assertEqual(response.get_json()["history_start"], "2023-01-01 00:00:00")

    def test_fine_period_window_is_capped_and_reports_render_bounds(self):
        history_start = START - timedelta(minutes=5 * 12000)
        frame = _bars(history_start, 12001)
        session = _FakeSession(frame)
        training = {
            "id": "fine-window-test",
            "user": "tester",
            "market_type": "crypto_perpetual",
            "data_mode": "crypto_5m",
            "symbol": "BTCUSDT",
            "source": "binance",
            "period": "5m",
            "training_start": START.strftime("%Y-%m-%d %H:%M:%S"),
            "training_end": START.strftime("%Y-%m-%d %H:%M:%S"),
            "crypto_session": session,
            "_crypto_history_start": history_start,
            "_crypto_history_end": START,
            "_crypto_chart_window_start": history_start,
            "_crypto_chart_window_end": START,
            "_crypto_chart_base_frame": frame,
        }
        app_module.active_trainings[training["id"]] = training
        with patch.object(app_module, "_persist_crypto_period"):
            response = self.client.post(
                "/api/training/fine-window-test/period",
                json={"period": "5m", "request_id": 1, "compact_chart": True},
            )

        self.assertEqual(response.status_code, 200, response.get_json())
        payload = response.get_json()
        self.assertEqual(len(payload["kline_data"]), 12000)
        self.assertEqual(payload["history_start"], history_start.strftime("%Y-%m-%d %H:%M:%S"))
        self.assertEqual(payload["history_end"], START.strftime("%Y-%m-%d %H:%M:%S"))
        self.assertTrue(payload["has_earlier_render"])
        self.assertGreater(payload["render_start"], payload["history_start"])

    def test_fine_period_earlier_segment_end_is_aligned_after_one_second_offset(self):
        history_start = START - timedelta(minutes=5 * 24000)
        training = {
            "_crypto_history_start": history_start,
            "_crypto_history_end": START,
        }

        _, _, render_start, render_end = app_module._crypto_render_bounds(
            training,
            "5m",
            START,
            visible_start=history_start,
            visible_end=START - timedelta(seconds=1),
        )

        self.assertEqual(render_end, START - timedelta(minutes=5))
        self.assertEqual(render_start.second, 0)
        self.assertEqual(render_start.minute % 5, 0)

    def test_prepared_chart_window_reads_runtime_frame_without_network(self):
        history_start = START - timedelta(hours=1)
        frame = _bars(history_start, 13)
        training = {
            "id": "runtime-chart-window",
            "user": "tester",
            "market_type": "crypto_perpetual",
            "data_mode": "crypto_5m",
            "symbol": "BTCUSDT",
            "source": "binance",
            "period": "5m",
            "training_start": START.strftime("%Y-%m-%d %H:%M:%S"),
            "training_end": START.strftime("%Y-%m-%d %H:%M:%S"),
            "trade_markers": [],
            "crypto_session": _FakeSession(frame, active_period="5m"),
            "_crypto_history_start": history_start,
            "_crypto_history_end": START,
            "_crypto_chart_window_start": history_start,
            "_crypto_chart_window_end": START,
            "_crypto_chart_base_frame": frame,
        }
        app_module.active_trainings[training["id"]] = training
        network_service = SimpleNamespace(
            get_chart_bars=lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("prepared chart windows must not call the network service")
            ),
        )
        with patch.object(app_module, "_get_crypto_data_service", return_value=network_service):
            response = self.client.get(
                "/api/training/runtime-chart-window/chart-window"
                f"?period=5m&range_start={history_start.strftime('%Y-%m-%dT%H:%M:%SZ')}"
                f"&range_end={START.strftime('%Y-%m-%dT%H:%M:%SZ')}"
            )

        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(len(response.get_json()["kline_data"]), 13)
        self.assertEqual(response.get_json()["history_start"], history_start.strftime("%Y-%m-%d %H:%M:%S"))


if __name__ == "__main__":
    unittest.main()
