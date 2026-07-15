from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from backend.crypto.replay_clock import CryptoReplayClock

UTC = timezone.utc

def timeline(start, count):
    return [start + timedelta(minutes=5 * index) for index in range(count)]

class CryptoReplayClockTests(unittest.TestCase):
    def test_rejects_invalid_timeline_and_normalizes_utc(self):
        with self.assertRaisesRegex(ValueError, "empty"):
            CryptoReplayClock([])
        with self.assertRaisesRegex(ValueError, "strictly increasing"):
            CryptoReplayClock([datetime(2024, 1, 1, tzinfo=UTC)] * 2)
        with self.assertRaisesRegex(ValueError, "five-minute"):
            CryptoReplayClock([datetime(2024, 1, 1, 0, 1, tzinfo=UTC)])

    def test_plan_is_pure_and_rejects_stale_plan(self):
        values = timeline(datetime(2024, 1, 1, 0, 0, tzinfo=UTC), 8)
        clock = CryptoReplayClock(values, initial_time=values[0], active_period="15m")
        first = clock.plan_next()
        self.assertEqual(clock.current_time, values[0])
        self.assertEqual(first.target_time, values[2])
        self.assertEqual(first.base_bar_times, tuple(values[1:3]))
        clock.advance(first)
        with self.assertRaisesRegex(ValueError, "stale"):
            clock.advance(first)

    def test_crosses_midnight_weekend_and_year_without_calendar_gaps(self):
        values = timeline(datetime(2023, 12, 31, 23, 50, tzinfo=UTC), 5)
        clock = CryptoReplayClock(values, active_period="5m")
        observed = []
        while clock.has_next():
            plan = clock.plan_next()
            observed.extend(plan.base_bar_times)
            clock.advance(plan)
        self.assertEqual(observed, values[1:])
        self.assertEqual(clock.current_time, datetime(2024, 1, 1, 0, 10, tzinfo=UTC))

    def test_period_switching_preserves_time_and_targets_boundaries(self):
        values = timeline(datetime(2024, 1, 7, 23, 45, tzinfo=UTC), 52)
        clock = CryptoReplayClock(values, initial_time=values[0], active_period="daily")
        self.assertEqual(clock.plan_next().target_time, datetime(2024, 1, 7, 23, 55, tzinfo=UTC))
        clock.set_period("4h")
        self.assertEqual(clock.current_time, values[0])
        self.assertEqual(clock.plan_next().target_time, datetime(2024, 1, 7, 23, 55, tzinfo=UTC))
        clock.set_period("weekly")
        self.assertEqual(clock.plan_next().target_time, datetime(2024, 1, 7, 23, 55, tzinfo=UTC))

if __name__ == "__main__":
    unittest.main()
