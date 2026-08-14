from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from backend.crypto.replay_clock import CryptoReplayClock

UTC = timezone.utc

def timeline(start, count):
    return [start + timedelta(minutes=1 * index) for index in range(count)]

class CryptoReplayClockTests(unittest.TestCase):
    def test_rejects_invalid_timeline_and_normalizes_utc(self):
        with self.assertRaisesRegex(ValueError, "empty"):
            CryptoReplayClock([])
        with self.assertRaisesRegex(ValueError, "strictly increasing"):
            CryptoReplayClock([datetime(2024, 1, 1, tzinfo=UTC)] * 2)
        with self.assertRaisesRegex(ValueError, "align"):
            CryptoReplayClock([datetime(2024, 1, 1, 0, 0, 30, tzinfo=UTC)])

    def test_rejects_misaligned_step_for_legacy_base(self):
        # 旧 5m 会话恢复：base_step_minutes=5 时非 5 分钟对齐的时间戳应被拒绝
        values = timeline(datetime(2024, 1, 1, 0, 0, tzinfo=UTC), 8)
        with self.assertRaisesRegex(ValueError, "align"):
            CryptoReplayClock(values, base_step_minutes=5)

    def test_accepts_legacy_five_minute_timeline_with_base_step(self):
        values = [datetime(2024, 1, 1, 0, 0, tzinfo=UTC) + timedelta(minutes=5 * index) for index in range(8)]
        clock = CryptoReplayClock(values, initial_time=values[0], active_period="15m", base_step_minutes=5)
        self.assertEqual(clock.current_time, values[0])
        self.assertEqual(clock.plan_next().target_time, values[2])

    def test_plan_is_pure_and_rejects_stale_plan(self):
        values = timeline(datetime(2024, 1, 1, 0, 0, tzinfo=UTC), 20)
        clock = CryptoReplayClock(values, initial_time=values[0], active_period="15m")
        first = clock.plan_next()
        self.assertEqual(clock.current_time, values[0])
        self.assertEqual(first.target_time, values[14])
        self.assertEqual(first.base_bar_times, tuple(values[1:15]))
        clock.advance(first)
        with self.assertRaisesRegex(ValueError, "stale"):
            clock.advance(first)

    def test_identity_period_advances_one_bar(self):
        values = timeline(datetime(2024, 1, 1, 0, 0, tzinfo=UTC), 6)
        clock = CryptoReplayClock(values, initial_time=values[0], active_period="1m")
        plan = clock.plan_next()
        self.assertEqual(plan.target_time, values[1])
        self.assertEqual(plan.base_bar_times, (values[1],))

    def test_crosses_midnight_weekend_and_year_without_calendar_gaps(self):
        values = timeline(datetime(2023, 12, 31, 23, 50, tzinfo=UTC), 20)
        clock = CryptoReplayClock(values, active_period="5m")
        observed = []
        while clock.has_next():
            plan = clock.plan_next()
            observed.extend(plan.base_bar_times)
            clock.advance(plan)
        self.assertEqual(observed, values[1:])
        self.assertEqual(clock.current_time, datetime(2024, 1, 1, 0, 9, tzinfo=UTC))

    def test_period_switching_preserves_time_and_targets_boundaries(self):
        values = timeline(datetime(2024, 1, 7, 23, 45, tzinfo=UTC), 60)
        clock = CryptoReplayClock(values, initial_time=values[0], active_period="daily")
        self.assertEqual(clock.plan_next().target_time, datetime(2024, 1, 7, 23, 59, tzinfo=UTC))
        clock.set_period("4h")
        self.assertEqual(clock.current_time, values[0])
        self.assertEqual(clock.plan_next().target_time, datetime(2024, 1, 7, 23, 59, tzinfo=UTC))
        clock.set_period("weekly")
        self.assertEqual(clock.plan_next().target_time, datetime(2024, 1, 7, 23, 59, tzinfo=UTC))

    def test_two_day_period_boundary_aligned_to_epoch(self):
        # 2d 周期：桶按 epoch 对齐（1970-01-01 起算）。2024-01-01 距 epoch 19723 天（奇数），
        # floor("2D") → 2023-12-31；首根完整桶边界 = 2024-01-01 23:59。
        values = timeline(datetime(2024, 1, 1, 0, 0, tzinfo=UTC), 60 * 24 * 4)
        clock = CryptoReplayClock(values, initial_time=values[0], active_period="2d")
        plan = clock.plan_next()
        self.assertEqual(plan.target_time, datetime(2024, 1, 1, 23, 59, tzinfo=UTC))

if __name__ == "__main__":
    unittest.main()
