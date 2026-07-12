import unittest
from datetime import datetime

from backend.intraday.models import ReplayPeriod
from backend.intraday.replay_clock import ReplayClock


STANDARD_TIMES = ("10:00", "10:30", "11:00", "11:30", "13:30", "14:00", "14:30", "15:00")


def day(date_text, times=STANDARD_TIMES):
    return [datetime.fromisoformat(f"{date_text}T{time_text}:00") for time_text in times]


class ReplayClockTests(unittest.TestCase):
    def timeline(self):
        return tuple(
            day("2025-01-02")
            + day("2025-01-03")
            + day("2025-01-06")
            + day("2025-01-07")
            + day("2025-01-08")
            + day("2025-01-10")
            + day("2025-01-13")
        )

    def test_rejects_empty_unsorted_duplicate_and_missing_initial_time(self):
        first, second = day("2025-01-02")[:2]
        with self.assertRaisesRegex(ValueError, "empty"):
            ReplayClock(())
        with self.assertRaisesRegex(ValueError, "strictly increasing"):
            ReplayClock((second, first))
        with self.assertRaisesRegex(ValueError, "duplicate|strictly increasing"):
            ReplayClock((first, first))
        with self.assertRaisesRegex(ValueError, "initial_time"):
            ReplayClock((first, second), initial_time=datetime(2025, 1, 2, 10, 15))

    def test_normalizes_datetime_like_values_and_builds_boundary_index(self):
        clock = ReplayClock([value.isoformat() for value in self.timeline()])

        self.assertEqual(clock.boundary_index.timestamps, self.timeline())
        self.assertIn(datetime(2025, 1, 2, 15), clock.boundary_index.session_ends)
        self.assertIn(datetime(2025, 1, 10, 15), clock.boundary_index.week_ends)
        self.assertNotIn(datetime(2025, 1, 8, 15), clock.boundary_index.week_ends)
        self.assertEqual(clock.boundary_index.incomplete_sessions, frozenset())

    def test_incomplete_session_is_recorded_even_when_it_has_close_bar(self):
        incomplete = tuple(day("2025-01-02", STANDARD_TIMES[:-2] + ("15:00",)))
        clock = ReplayClock(incomplete)

        self.assertEqual(clock.boundary_index.session_ends, frozenset({datetime(2025, 1, 2, 15)}))
        self.assertEqual(clock.boundary_index.incomplete_sessions, frozenset({datetime(2025, 1, 2).date()}))

    def test_initial_position_set_period_and_reset(self):
        timeline = self.timeline()
        clock = ReplayClock(timeline, initial_time=timeline[3], active_period="daily")

        self.assertEqual(clock.current_time, timeline[3])
        self.assertEqual(clock.current_index, 3)
        self.assertEqual(clock.active_period, ReplayPeriod.DAILY)
        clock.set_period("weekly")
        self.assertEqual(clock.current_time, timeline[3])
        self.assertEqual(clock.current_index, 3)
        self.assertEqual(clock.active_period, ReplayPeriod.WEEKLY)
        clock.advance(timeline[5])
        clock.reset()
        self.assertEqual(clock.current_time, timeline[3])
        self.assertEqual(clock.active_period, ReplayPeriod.DAILY)

    def test_30m_plan_uses_next_real_bar_across_lunch(self):
        timeline = tuple(day("2025-01-02"))
        clock = ReplayClock(timeline, initial_time=datetime(2025, 1, 2, 11, 30), active_period="30m")

        plan = clock.plan_next()

        self.assertEqual(plan.target_time, datetime(2025, 1, 2, 13, 30))
        self.assertEqual(plan.base_bar_times, (datetime(2025, 1, 2, 13, 30),))
        self.assertEqual(clock.current_time, datetime(2025, 1, 2, 11, 30))

    def test_30m_plan_crosses_weekend_to_next_real_bar(self):
        timeline = tuple(day("2025-01-03") + day("2025-01-06"))
        clock = ReplayClock(timeline, initial_time=datetime(2025, 1, 3, 15), active_period="30m")

        self.assertEqual(clock.plan_next().target_time, datetime(2025, 1, 6, 10))

    def test_daily_and_session_plan_to_current_day_end_then_next_day_end(self):
        timeline = tuple(day("2025-01-02") + day("2025-01-03"))
        for period in (ReplayPeriod.SESSION_4H, ReplayPeriod.DAILY):
            with self.subTest(period=period):
                clock = ReplayClock(timeline, initial_time=datetime(2025, 1, 2, 11), active_period=period)
                plan = clock.plan_next()
                self.assertEqual(plan.target_time, datetime(2025, 1, 2, 15))
                self.assertEqual(plan.base_bar_times, tuple(day("2025-01-02")[3:]))
                clock.advance(plan)
                next_plan = clock.plan_next()
                self.assertEqual(next_plan.target_time, datetime(2025, 1, 3, 15))
                self.assertEqual(next_plan.base_bar_times, tuple(day("2025-01-03")))

    def test_weekly_uses_actual_short_week_end_then_next_week_end(self):
        timeline = self.timeline()
        clock = ReplayClock(timeline, initial_time=datetime(2025, 1, 6, 11), active_period="weekly")

        plan = clock.plan_next()
        self.assertEqual(plan.target_time, datetime(2025, 1, 10, 15))
        self.assertNotIn(datetime(2025, 1, 9, 15), plan.base_bar_times)
        clock.advance(plan)
        self.assertEqual(clock.plan_next().target_time, datetime(2025, 1, 13, 15))

    def test_plan_next_is_pure_and_returns_strict_open_closed_interval(self):
        timeline = tuple(day("2025-01-02"))
        clock = ReplayClock(timeline, initial_time=timeline[1], active_period="daily")

        first = clock.plan_next()
        second = clock.plan_next()

        self.assertEqual(first, second)
        self.assertEqual(clock.current_index, 1)
        self.assertNotIn(timeline[1], first.base_bar_times)
        self.assertEqual(first.base_bar_times, timeline[2:])

    def test_advance_rejects_stale_or_foreign_plan_and_non_timeline_target(self):
        timeline = tuple(day("2025-01-02"))
        clock = ReplayClock(timeline, initial_time=timeline[0])
        plan = clock.plan_next()
        clock.advance(plan)

        with self.assertRaisesRegex(ValueError, "stale"):
            clock.advance(plan)
        with self.assertRaisesRegex(ValueError, "timeline"):
            clock.advance(datetime(2025, 1, 2, 10, 15))
        with self.assertRaisesRegex(ValueError, "forward"):
            clock.advance(timeline[0])

    def test_has_next_and_finished_plan_at_timeline_end(self):
        timeline = tuple(day("2025-01-02"))
        clock = ReplayClock(timeline, initial_time=timeline[-1], active_period="weekly")

        self.assertFalse(clock.has_next())
        plan = clock.plan_next()
        self.assertTrue(plan.finished)
        self.assertIsNone(plan.target_time)
        self.assertEqual(plan.base_bar_times, ())
        with self.assertRaisesRegex(ValueError, "finished"):
            clock.advance(plan)



if __name__ == "__main__":
    unittest.main()


