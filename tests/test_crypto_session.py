from __future__ import annotations

import json
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

import pandas as pd

from backend.crypto.aggregator import aggregate_bars
from backend.crypto.session import CryptoReplaySession, _detect_base_step_minutes

UTC = timezone.utc

def make_frame(start, count):
    return pd.DataFrame([{"timestamp": start + timedelta(minutes=1 * index), "open": 10 + index, "high": 12 + index, "low": 9 + index, "close": 11 + index, "volume": 1 + index, "turnover": 20 + index} for index in range(count)])

class CryptoReplaySessionTests(unittest.TestCase):
    def test_snapshot_and_period_switch_preserve_canonical_time(self):
        frame = make_frame(datetime(2024, 1, 1, 0, 0, tzinfo=UTC), 12)
        session = CryptoReplaySession(frame, initial_time=frame.iloc[2]["timestamp"], symbol="BTCUSDT", source="binance", active_period="1m")
        snapshot = session.snapshot()
        self.assertEqual(snapshot["market_type"], "crypto_perpetual")
        self.assertEqual(snapshot["data_mode"], "crypto_5m")
        self.assertEqual(snapshot["current_time"], "2024-01-01 00:02:00")
        self.assertEqual(len(snapshot["kline_data"]), 3)
        switched = session.set_period("5m")
        self.assertEqual(switched["current_time"], snapshot["current_time"])
        self.assertEqual(switched["current_base_bar"]["close"], snapshot["current_base_bar"]["close"])
        json.dumps(switched)

    def test_advance_processes_hidden_base_bars_then_commits(self):
        frame = make_frame(datetime(2024, 1, 1, 0, 0, tzinfo=UTC), 20)
        completed = []
        session = CryptoReplaySession(frame, active_period="15m", on_bar=lambda timestamp, row: completed.append(timestamp))
        result = session.advance()
        self.assertEqual(completed, [datetime(2024, 1, 1, 0, 1, tzinfo=UTC), datetime(2024, 1, 1, 0, 2, tzinfo=UTC), datetime(2024, 1, 1, 0, 3, tzinfo=UTC), datetime(2024, 1, 1, 0, 4, tzinfo=UTC), datetime(2024, 1, 1, 0, 5, tzinfo=UTC), datetime(2024, 1, 1, 0, 6, tzinfo=UTC), datetime(2024, 1, 1, 0, 7, tzinfo=UTC), datetime(2024, 1, 1, 0, 8, tzinfo=UTC), datetime(2024, 1, 1, 0, 9, tzinfo=UTC), datetime(2024, 1, 1, 0, 10, tzinfo=UTC), datetime(2024, 1, 1, 0, 11, tzinfo=UTC), datetime(2024, 1, 1, 0, 12, tzinfo=UTC), datetime(2024, 1, 1, 0, 13, tzinfo=UTC), datetime(2024, 1, 1, 0, 14, tzinfo=UTC)])
        self.assertEqual(result["current_time"], "2024-01-01 00:14:00")
        self.assertEqual(result["completed_times"][0], "2024-01-01 00:01:00")
        self.assertEqual(result["completed_times"][-1], "2024-01-01 00:14:00")

    def test_advance_delta_returns_only_the_changed_one_minute_bar(self):
        frame = make_frame(datetime(2024, 1, 1, 0, 0, tzinfo=UTC), 8)
        session = CryptoReplaySession(frame, active_period="1m")

        result = session.advance_delta(max_bars=120)

        self.assertNotIn("kline_data", result)
        self.assertEqual(result["new_bar"]["time"], "2024-01-01 00:01:00")
        self.assertEqual(result["new_volume"], {"time": "2024-01-01 00:01:00", "value": 2.0})
        self.assertFalse(result["requires_full_refresh"])
        self.assertEqual(result["completed_times"], ["2024-01-01 00:01:00"])

    def test_advance_delta_requires_full_refresh_within_same_bucket(self):
        # 1m 底座 + 5m 周期：从桶内推进到桶末需要整桶刷新
        frame = make_frame(datetime(2024, 1, 1, 0, 0, tzinfo=UTC), 8)
        session = CryptoReplaySession(frame, active_period="5m")

        result = session.advance_delta(max_bars=120)

        self.assertTrue(result["requires_full_refresh"])
        self.assertIn("refresh_snapshot", result)
        self.assertEqual(result["new_bar"]["time"], "2024-01-01 00:04:00")

    def test_advance_delta_does_not_build_a_full_snapshot(self):
        frame = make_frame(datetime(2024, 1, 1, 0, 0, tzinfo=UTC), 1000)
        session = CryptoReplaySession(frame, active_period="1m")

        with patch.object(session, "snapshot", side_effect=AssertionError("full snapshot is too expensive")):
            result = session.advance_delta(max_bars=120)

        self.assertEqual(result["new_bar"]["time"], "2024-01-01 00:01:00")

    def test_callback_failure_does_not_commit_and_reset_restores_state(self):
        frame = make_frame(datetime(2024, 1, 1, 0, 0, tzinfo=UTC), 5)
        session = CryptoReplaySession(frame, on_bar=lambda timestamp, row: (_ for _ in ()).throw(RuntimeError("boom")))
        with self.assertRaisesRegex(RuntimeError, "boom"):
            session.advance()
        self.assertEqual(session.snapshot()["current_time"], "2024-01-01 00:00:00")
        session = CryptoReplaySession(frame, active_period="15m")
        session.advance()
        reset = session.reset()
        self.assertEqual(reset["current_time"], "2024-01-01 00:00:00")
        self.assertEqual(reset["active_period"], "15m")

    def test_max_training_days_uses_utc_calendar_day_cutoff(self):
        frame = make_frame(datetime(2024, 1, 1, 23, 50, tzinfo=UTC), 6)
        session = CryptoReplaySession(frame, active_period="daily", max_training_days=1)
        result = session.advance()
        self.assertEqual(result["current_time"], "2024-01-01 23:55:00")
        self.assertTrue(result["finished"])
        self.assertEqual(len(result["kline_data"]), 1)

    def test_snapshot_does_not_use_dataframe_row_iteration(self):
        frame = make_frame(datetime(2024, 1, 1, 0, 0, tzinfo=UTC), 100)
        session = CryptoReplaySession(frame, initial_time=frame.iloc[-1]["timestamp"])
        with patch.object(pd.DataFrame, "iterrows", side_effect=AssertionError("row iteration is too slow")):
            snapshot = session.snapshot()
        self.assertEqual(len(snapshot["kline_data"]), 100)

    def test_initialization_normalizes_timestamps_and_numeric_values_once(self):
        frame = make_frame(datetime(2024, 1, 1, 0, 0, tzinfo=UTC), 4)
        frame["timestamp"] = frame["timestamp"].astype(str)
        for column in ("open", "high", "low", "close", "volume", "turnover"):
            frame[column] = frame[column].map(lambda value: Decimal(str(value)))

        session = CryptoReplaySession(frame)

        self.assertIsInstance(session.base_bars["timestamp"].dtype, pd.DatetimeTZDtype)
        for column in ("open", "high", "low", "close", "volume", "turnover"):
            self.assertTrue(pd.api.types.is_float_dtype(session.base_bars[column].dtype))
        with patch.object(pd, "to_datetime", side_effect=AssertionError("timestamps must not be normalized again")):
            session.snapshot()
            session.set_period("15m")

    def test_snapshot_and_aggregation_cache_reuse_by_time_and_period(self):
        frame = make_frame(datetime(2024, 1, 1, 0, 0, tzinfo=UTC), 60 * 24 * 12)
        session = CryptoReplaySession(frame)

        with patch("backend.crypto.session.aggregate_bars", wraps=aggregate_bars) as aggregate:
            first = session.snapshot()
            repeated = session.snapshot()
            session.set_period("15m")
            session.set_period("1m")

            self.assertEqual(aggregate.call_count, 2)
            self.assertEqual(repeated, first)
            self.assertIsNot(repeated, first)

            session.advance()
            self.assertEqual(aggregate.call_count, 3)

    def test_period_snapshot_can_limit_visible_bars_without_reaggregating(self):
        frame = make_frame(datetime(2024, 1, 1, 0, 0, tzinfo=UTC), 1000)
        session = CryptoReplaySession(frame, initial_time=frame.iloc[-1]["timestamp"])

        with patch("backend.crypto.session.aggregate_bars", wraps=aggregate_bars) as aggregate:
            full = session.snapshot()
            limited = session.snapshot(max_bars=120)

        self.assertEqual(len(full["kline_data"]), 1000)
        self.assertEqual(len(limited["kline_data"]), 120)
        self.assertEqual(limited["kline_data"][-1], full["kline_data"][-1])
        self.assertEqual(aggregate.call_count, 1)

    def test_period_snapshot_limit_tracks_requested_visible_range(self):
        frame = make_frame(datetime(2024, 1, 1, 0, 0, tzinfo=UTC), 1000)
        session = CryptoReplaySession(frame, initial_time=frame.iloc[-1]["timestamp"])
        visible_start = frame.iloc[200]["timestamp"].to_pydatetime()
        visible_end = frame.iloc[260]["timestamp"].to_pydatetime()

        snapshot = session.snapshot(
            max_bars=120, range_start=visible_start, range_end=visible_end
        )

        times = [item["time"] for item in snapshot["kline_data"]]
        self.assertLessEqual(len(times), 120)
        self.assertIn(visible_start.strftime("%Y-%m-%d %H:%M:%S"), times)
        self.assertIn(visible_end.strftime("%Y-%m-%d %H:%M:%S"), times)

    def test_explicit_unbounded_range_returns_exact_loaded_window(self):
        frame = make_frame(datetime(2024, 1, 1, 0, 0, tzinfo=UTC), 1000)
        session = CryptoReplaySession(frame, initial_time=frame.iloc[-1]["timestamp"])
        range_start = frame.iloc[100]["timestamp"].to_pydatetime()
        range_end = frame.iloc[800]["timestamp"].to_pydatetime()

        snapshot = session.snapshot(
            max_bars=None, range_start=range_start, range_end=range_end
        )

        times = [item["time"] for item in snapshot["kline_data"]]
        self.assertEqual(len(times), 701)
        self.assertEqual(times[0], range_start.strftime("%Y-%m-%d %H:%M:%S"))
        self.assertEqual(times[-1], range_end.strftime("%Y-%m-%d %H:%M:%S"))
    def test_reset_invalidates_snapshot_cache_even_at_initial_key(self):
        frame = make_frame(datetime(2024, 1, 1, 0, 0, tzinfo=UTC), 4)
        session = CryptoReplaySession(frame)

        with patch("backend.crypto.session.aggregate_bars", wraps=aggregate_bars) as aggregate:
            session.snapshot()
            session.reset()
            self.assertEqual(aggregate.call_count, 2)


class BaseStepDetectionTests(unittest.TestCase):
    """_detect_base_step_minutes 应该在底座时间戳前 20 根向量上判定，避免全量扫描。"""

    def test_detects_one_minute_base_from_uniform_one_minute_frame(self):
        frame = make_frame(datetime(2024, 1, 1, tzinfo=UTC), 200)
        self.assertEqual(_detect_base_step_minutes(frame["timestamp"]), 1)

    def test_detects_five_minute_base_from_uniform_legacy_frame(self):
        legacy_rows = [{"timestamp": datetime(2024, 1, 1, 0, 0, tzinfo=UTC) + timedelta(minutes=5 * index),
                        "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0, "turnover": 1.0}
                       for index in range(200)]
        frame = pd.DataFrame(legacy_rows)
        self.assertEqual(_detect_base_step_minutes(frame["timestamp"]), 5)

    def test_does_not_scan_full_million_row_frame(self):
        # 100 万根 1m 帧时，新实现只读前 20 根，总耗时 < 100ms；
        # 旧实现会在 1m 步长均匀下遍历到底。
        frame = make_frame(datetime(2025, 1, 1, tzinfo=UTC), 1_000_000)
        import time
        start = time.perf_counter()
        step = _detect_base_step_minutes(frame["timestamp"])
        elapsed = time.perf_counter() - start
        self.assertEqual(step, 1)
        self.assertLess(elapsed, 0.2, f"detect took {elapsed:.3f}s — should be sub-200ms for 1m frame")

    def test_handles_short_and_empty_inputs(self):
        # 单根或空 => 返回 1（保守默认 1m 底座）
        single = make_frame(datetime(2024, 1, 1, tzinfo=UTC), 1)
        self.assertEqual(_detect_base_step_minutes(single["timestamp"]), 1)
        empty = pd.DataFrame(columns=["timestamp"])
        self.assertEqual(_detect_base_step_minutes(empty["timestamp"]), 1)


if __name__ == "__main__":
    unittest.main()
