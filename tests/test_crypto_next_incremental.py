from __future__ import annotations

import threading
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import backend.app_enhanced as app_module
from tests.test_crypto_futures_api import _training


UTC = timezone.utc
START = datetime(2025, 1, 1, tzinfo=UTC)


def _contains_key(value, key):
    if isinstance(value, dict):
        return key in value or any(_contains_key(item, key) for item in value.values())
    if isinstance(value, list):
        return any(_contains_key(item, key) for item in value)
    return False


def _parse_time(value):
    return datetime.fromisoformat(value).replace(tzinfo=UTC)


class _AdvanceProbe:
    def __init__(self, advance):
        self._advance = advance
        self._overlap_gate = threading.Barrier(2)
        self._lock = threading.Lock()
        self.active = 0
        self.max_active = 0

    def __call__(self, *args, **kwargs):
        with self._lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        try:
            try:
                self._overlap_gate.wait(timeout=0.3)
            except threading.BrokenBarrierError:
                pass
            return self._advance(*args, **kwargs)
        finally:
            with self._lock:
                self.active -= 1


class CryptoNextIncrementalTests(unittest.TestCase):
    def setUp(self):
        app_module.app.config['TESTING'] = True
        self.training_id = 'crypto-next-incremental'
        self.training = _training(self.training_id)
        app_module.active_trainings[self.training_id] = self.training
        self.checkpoint_patcher = patch.object(app_module, '_checkpoint_crypto_futures')
        self.checkpoint_patcher.start()

    def tearDown(self):
        app_module.active_trainings.pop(self.training_id, None)
        self.checkpoint_patcher.stop()

    def test_next_returns_a_small_incremental_delta_with_trading_state(self):
        with app_module.app.test_client() as client:
            response = client.post(f'/api/training/{self.training_id}/next')

        self.assertEqual(response.status_code, 200, response.get_json())
        payload = response.get_json()
        self.assertIn('delta', payload)
        self.assertFalse(_contains_key(payload, 'kline_data'))
        delta = payload['delta']
        expected_keys = {
            'bars', 'current_time', 'progress', 'account', 'positions',
            'pending_orders', 'fills', 'trade_markers',
        }
        self.assertTrue(expected_keys.issubset(delta))
        self.assertGreaterEqual(len(delta['bars']), 1)
        self.assertLessEqual(len(delta['bars']), 2)

    def test_next_delta_contains_only_revealed_aggregated_bars(self):
        with app_module.app.test_client() as client:
            response = client.post(f'/api/training/{self.training_id}/next')

        self.assertEqual(response.status_code, 200, response.get_json())
        delta = response.get_json()['delta']
        current_time = _parse_time(delta['current_time'])
        revealed_times = []
        for bar in delta['bars']:
            bar_time = _parse_time(bar.get('end_time', bar['time']))
            revealed_times.append(bar_time)
            self.assertLessEqual(bar_time, current_time)

        self.assertEqual(max(revealed_times), current_time)
        self.assertEqual(current_time, START + timedelta(minutes=5))
        self.assertEqual(delta['bars'][-1]['close'], 101)

    def test_concurrent_next_requests_do_not_advance_the_same_step_twice(self):
        session = self.training['crypto_session']
        probe = _AdvanceProbe(session.advance_delta)
        session.advance_delta = probe
        start_gate = threading.Barrier(3)
        result_lock = threading.Lock()
        results = []

        def request_next():
            start_gate.wait()
            with app_module.app.test_client() as client:
                response = client.post(f'/api/training/{self.training_id}/next')
            with result_lock:
                results.append((response.status_code, response.get_json()))

        threads = [threading.Thread(target=request_next) for _ in range(2)]
        for thread in threads:
            thread.start()
        start_gate.wait()
        for thread in threads:
            thread.join(timeout=5)

        self.assertTrue(all(not thread.is_alive() for thread in threads))
        statuses = sorted(status for status, _payload in results)
        self.assertIn(statuses, ([200, 200], [200, 409]))
        self.assertEqual(probe.max_active, 1)

        successful_times = [
            payload['delta']['current_time']
            for status, payload in results
            if status == 200
        ]
        self.assertEqual(len(successful_times), len(set(successful_times)))
        expected_time = START + timedelta(minutes=5 * len(successful_times))
        self.assertEqual(session.clock.current_time, expected_time)
