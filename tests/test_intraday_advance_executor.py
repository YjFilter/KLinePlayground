from __future__ import annotations

import unittest
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from backend.intraday.advance_executor import (
    AdvanceCallbacks,
    AdvanceExecutionResult,
    execute_advance,
)
from backend.intraday.models import ReplayAdvance
from backend.intraday.replay_clock import ReplayClock


STANDARD_TIMES = ("10:00", "10:30", "11:00", "11:30", "13:30", "14:00", "14:30", "15:00")


def _day(date_text: str, times: tuple[str, ...] = STANDARD_TIMES) -> list[datetime]:
    return [datetime.fromisoformat(f"{date_text}T{t}:00") for t in times]


def _bar(timestamp: datetime, *, close: float = 10.0) -> dict[str, Any]:
    return {
        "datetime": timestamp,
        "open": close,
        "high": close + 0.1,
        "low": close - 0.1,
        "close": close,
        "volume": 100,
        "amount": 1000.0,
    }


@dataclass
class RecordingCallbacks:
    """Spy implementation of AdvanceCallbacks that records every invocation."""

    bars_by_time: dict[datetime, dict]
    prev_close_by_date: dict[date, float] = field(default_factory=dict)
    events_per_bar: dict[datetime, list[dict]] = field(default_factory=dict)
    fail_steps: dict[tuple[str, Any], Exception] = field(default_factory=dict)
    call_log: list[tuple] = field(default_factory=list)

    def _maybe_fail(self, step: str, key: Any) -> None:
        exc = self.fail_steps.get((step, key))
        if exc is not None:
            raise exc

    def fetch_base_bar(self, timestamp: datetime) -> dict:
        self.call_log.append(("fetch_base_bar", timestamp))
        self._maybe_fail("fetch_base_bar", timestamp)
        return self.bars_by_time[timestamp]

    def update_price_and_state(self, timestamp: datetime, bar: dict) -> None:
        self.call_log.append(("update_price_and_state", timestamp))
        self._maybe_fail("update_price_and_state", timestamp)

    def get_previous_close(self, trade_date: date) -> float | None:
        self.call_log.append(("get_previous_close", trade_date))
        self._maybe_fail("get_previous_close", trade_date)
        return self.prev_close_by_date.get(trade_date)

    def process_pending_orders(
        self,
        timestamp: datetime,
        bar: dict,
        prev_close: float | None,
    ) -> list[dict]:
        self.call_log.append(("process_pending_orders", timestamp))
        self._maybe_fail("process_pending_orders", timestamp)
        return [dict(event) for event in self.events_per_bar.get(timestamp, [])]


def _build_callbacks(timeline: list[datetime]) -> RecordingCallbacks:
    bars = {ts: _bar(ts, close=10.0 + i) for i, ts in enumerate(timeline)}
    prev_close = {ts.date(): 9.5 for ts in timeline}
    events_per_bar = {
        ts: [{"bar": ts, "label": f"event-{i}"}] for i, ts in enumerate(timeline)
    }
    return RecordingCallbacks(
        bars_by_time=bars,
        prev_close_by_date=prev_close,
        events_per_bar=events_per_bar,
    )


class FinishedPlanTests(unittest.TestCase):
    def test_finished_plan_returns_explicit_finished_result_without_work(self):
        timeline = _day("2025-01-02")
        clock = ReplayClock(timeline, initial_time=timeline[-1], active_period="weekly")
        plan = clock.plan_next()
        self.assertTrue(plan.finished)

        callbacks = _build_callbacks(timeline)
        before_log = list(callbacks.call_log)

        result = execute_advance(plan, callbacks, clock=clock)

        self.assertTrue(result.success)
        self.assertTrue(result.finished)
        self.assertEqual(result.completed_times, ())
        self.assertEqual(result.events, ())
        self.assertIsNone(result.failed_time)
        self.assertIsNone(result.error)
        # No callback work was performed.
        self.assertEqual(callbacks.call_log, before_log)
        # Clock position is untouched.
        self.assertEqual(clock.current_time, timeline[-1])


class SingleStepAdvanceTests(unittest.TestCase):
    def test_single_30m_step_invokes_callbacks_in_required_order_and_commits_clock(self):
        timeline = _day("2025-01-02")
        clock = ReplayClock(timeline, initial_time=timeline[1], active_period="30m")
        plan = clock.plan_next()

        self.assertEqual(plan.target_time, datetime(2025, 1, 2, 11, 0))
        self.assertEqual(plan.base_bar_times, (datetime(2025, 1, 2, 11, 0),))

        callbacks = _build_callbacks(timeline)
        result = execute_advance(plan, callbacks, clock=clock)

        self.assertTrue(result.success)
        self.assertFalse(result.finished)
        self.assertEqual(result.completed_times, (datetime(2025, 1, 2, 11, 0),))
        self.assertEqual(len(result.events), 1)
        self.assertEqual(result.events[0]["bar"], datetime(2025, 1, 2, 11, 0))
        self.assertIsNone(result.failed_time)
        self.assertIsNone(result.error)

        expected_log = [
            ("fetch_base_bar", datetime(2025, 1, 2, 11, 0)),
            ("update_price_and_state", datetime(2025, 1, 2, 11, 0)),
            ("get_previous_close", date(2025, 1, 2)),
            ("process_pending_orders", datetime(2025, 1, 2, 11, 0)),
        ]
        self.assertEqual(callbacks.call_log, expected_log)
        # Clock was committed only after the single base bar succeeded.
        self.assertEqual(clock.current_time, datetime(2025, 1, 2, 11, 0))


class LargeStepAdvanceTests(unittest.TestCase):
    def test_daily_advance_processes_each_base_bar_in_order_with_event_order_preserved(self):
        timeline = _day("2025-01-02")
        clock = ReplayClock(timeline, initial_time=timeline[1], active_period="daily")
        plan = clock.plan_next()

        expected_times = tuple(timeline[2:])
        self.assertEqual(plan.base_bar_times, expected_times)

        callbacks = _build_callbacks(timeline)
        result = execute_advance(plan, callbacks, clock=clock)

        self.assertTrue(result.success)
        self.assertEqual(result.completed_times, expected_times)
        self.assertEqual(
            [event["bar"] for event in result.events],
            list(expected_times),
        )
        self.assertEqual(clock.current_time, timeline[-1])

        # Verify per-bar callback order: fetch -> update -> prev_close -> orders.
        log = callbacks.call_log
        idx = 0
        for ts in expected_times:
            self.assertEqual(log[idx], ("fetch_base_bar", ts))
            self.assertEqual(log[idx + 1], ("update_price_and_state", ts))
            self.assertEqual(log[idx + 2], ("get_previous_close", ts.date()))
            self.assertEqual(log[idx + 3], ("process_pending_orders", ts))
            idx += 4
        self.assertEqual(idx, len(log))


class StepByStepEquivalenceTests(unittest.TestCase):
    def test_large_period_advance_visits_same_base_bar_sequence_as_step_by_step_30m(self):
        timeline = _day("2025-01-02")

        # Scenario A: one daily advance from 10:30 to 15:00.
        clock_a = ReplayClock(timeline, initial_time=timeline[1], active_period="daily")
        plan_a = clock_a.plan_next()
        callbacks_a = _build_callbacks(timeline)
        execute_advance(plan_a, callbacks_a, clock=clock_a)

        # Scenario B: six sequential 30m advances covering the same span.
        clock_b = ReplayClock(timeline, initial_time=timeline[1], active_period="30m")
        callbacks_b = _build_callbacks(timeline)
        while clock_b.has_next():
            step_plan = clock_b.plan_next()
            execute_advance(step_plan, callbacks_b, clock=clock_b)

        sequence_a = [ts for step, ts in callbacks_a.call_log if step == "fetch_base_bar"]
        sequence_b = [ts for step, ts in callbacks_b.call_log if step == "fetch_base_bar"]

        self.assertEqual(sequence_a, sequence_b)
        self.assertEqual(sequence_a, list(plan_a.base_bar_times))
        # The full ordered (step, key) trace must match between the two scenarios.
        self.assertEqual(callbacks_a.call_log, callbacks_b.call_log)
        # Both clocks end at the same committed position.
        self.assertEqual(clock_a.current_time, clock_b.current_time)
        self.assertEqual(clock_a.current_time, timeline[-1])


class CallbackFailureTests(unittest.TestCase):
    def _build_daily_plan(self):
        timeline = _day("2025-01-02")
        clock = ReplayClock(timeline, initial_time=timeline[1], active_period="daily")
        plan = clock.plan_next()
        return timeline, clock, plan

    def _assert_failure_result(
        self,
        result: AdvanceExecutionResult,
        *,
        failed_time: datetime,
        completed_times: tuple[datetime, ...],
        clock: ReplayClock,
        initial_time: datetime,
    ) -> None:
        self.assertFalse(result.success)
        self.assertFalse(result.finished)
        self.assertEqual(result.failed_time, failed_time)
        self.assertEqual(result.completed_times, completed_times)
        self.assertIsNotNone(result.error)
        self.assertIn("RuntimeError", result.error or "")
        # Clock must NOT have been committed.
        self.assertEqual(clock.current_time, initial_time)

    def test_fetch_base_bar_failure_does_not_commit_clock_and_reports_failure(self):
        timeline, clock, plan = self._build_daily_plan()
        callbacks = _build_callbacks(timeline)
        failed_ts = plan.base_bar_times[2]
        callbacks.fail_steps[("fetch_base_bar", failed_ts)] = RuntimeError("bar missing")

        result = execute_advance(plan, callbacks, clock=clock)

        self._assert_failure_result(
            result,
            failed_time=failed_ts,
            completed_times=plan.base_bar_times[:2],
            clock=clock,
            initial_time=timeline[1],
        )
        # Partial events from completed bars are preserved in order.
        self.assertEqual(
            [event["bar"] for event in result.events],
            list(plan.base_bar_times[:2]),
        )

    def test_update_price_and_state_failure_does_not_commit_clock_and_reports_failure(self):
        timeline, clock, plan = self._build_daily_plan()
        callbacks = _build_callbacks(timeline)
        failed_ts = plan.base_bar_times[2]
        callbacks.fail_steps[("update_price_and_state", failed_ts)] = RuntimeError("state update failed")

        result = execute_advance(plan, callbacks, clock=clock)

        self._assert_failure_result(
            result,
            failed_time=failed_ts,
            completed_times=plan.base_bar_times[:2],
            clock=clock,
            initial_time=timeline[1],
        )

    def test_get_previous_close_failure_does_not_commit_clock_and_reports_failure(self):
        # Use a weekly plan that spans two trading days so that
        # get_previous_close is invoked with a different date on the second
        # day. Failing on the second day's date lets us verify that the first
        # day's bars were completed and the clock was not committed.
        timeline = _day("2025-01-02") + _day("2025-01-03")
        initial_time = datetime(2025, 1, 2, 10, 30)
        clock = ReplayClock(timeline, initial_time=initial_time, active_period="weekly")
        plan = clock.plan_next()

        failed_date = date(2025, 1, 3)
        failed_ts = next(ts for ts in plan.base_bar_times if ts.date() == failed_date)
        completed = tuple(ts for ts in plan.base_bar_times if ts < failed_ts)

        callbacks = _build_callbacks(timeline)
        callbacks.fail_steps[("get_previous_close", failed_date)] = RuntimeError("prev close missing")

        result = execute_advance(plan, callbacks, clock=clock)

        self._assert_failure_result(
            result,
            failed_time=failed_ts,
            completed_times=completed,
            clock=clock,
            initial_time=initial_time,
        )

    def test_process_pending_orders_failure_does_not_commit_clock_and_reports_failure(self):
        timeline, clock, plan = self._build_daily_plan()
        callbacks = _build_callbacks(timeline)
        failed_ts = plan.base_bar_times[2]
        callbacks.fail_steps[("process_pending_orders", failed_ts)] = RuntimeError("order processor crashed")

        result = execute_advance(plan, callbacks, clock=clock)

        self._assert_failure_result(
            result,
            failed_time=failed_ts,
            completed_times=plan.base_bar_times[:2],
            clock=clock,
            initial_time=timeline[1],
        )

    def test_failure_on_first_bar_keeps_empty_completed_times_and_events(self):
        timeline, clock, plan = self._build_daily_plan()
        callbacks = _build_callbacks(timeline)
        failed_ts = plan.base_bar_times[0]
        callbacks.fail_steps[("fetch_base_bar", failed_ts)] = RuntimeError("immediate failure")

        result = execute_advance(plan, callbacks, clock=clock)

        self.assertFalse(result.success)
        self.assertEqual(result.failed_time, failed_ts)
        self.assertEqual(result.completed_times, ())
        self.assertEqual(result.events, ())
        self.assertEqual(clock.current_time, timeline[1])


class NoClockTests(unittest.TestCase):
    def test_no_clock_does_not_attempt_commit_but_still_runs_callbacks(self):
        timeline = _day("2025-01-02")
        clock = ReplayClock(timeline, initial_time=timeline[1], active_period="daily")
        plan = clock.plan_next()

        callbacks = _build_callbacks(timeline)
        result = execute_advance(plan, callbacks, clock=None)

        self.assertTrue(result.success)
        self.assertEqual(result.completed_times, plan.base_bar_times)
        # The supplied clock was not passed in, so it must not be advanced.
        self.assertEqual(clock.current_time, timeline[1])
        # Callbacks were still invoked for every base bar.
        self.assertGreater(len(callbacks.call_log), 0)
        self.assertEqual(
            len([entry for entry in callbacks.call_log if entry[0] == "fetch_base_bar"]),
            len(plan.base_bar_times),
        )


class ImmutabilityTests(unittest.TestCase):
    def test_plan_is_not_mutated_by_executor(self):
        timeline = _day("2025-01-02")
        clock = ReplayClock(timeline, initial_time=timeline[1], active_period="daily")
        plan = clock.plan_next()
        original = ReplayAdvance(
            period=plan.period,
            current_time=plan.current_time,
            target_time=plan.target_time,
            base_bar_times=plan.base_bar_times,
        )

        callbacks = _build_callbacks(timeline)
        execute_advance(plan, callbacks, clock=clock)

        self.assertEqual(plan, original)

    def test_result_fields_are_immutable_tuples(self):
        timeline = _day("2025-01-02")
        clock = ReplayClock(timeline, initial_time=timeline[1], active_period="30m")
        plan = clock.plan_next()

        callbacks = _build_callbacks(timeline)
        result = execute_advance(plan, callbacks, clock=clock)

        self.assertIsInstance(result.completed_times, tuple)
        self.assertIsInstance(result.events, tuple)


class EventOrderTests(unittest.TestCase):
    def test_events_returned_in_strict_base_bar_processing_order(self):
        timeline = _day("2025-01-02") + _day("2025-01-03")
        clock = ReplayClock(timeline, initial_time=timeline[1], active_period="weekly")
        plan = clock.plan_next()

        callbacks = _build_callbacks(timeline)
        # Multiple events per bar to verify intra-bar order as well.
        for ts in plan.base_bar_times:
            callbacks.events_per_bar[ts] = [
                {"bar": ts, "seq": 0},
                {"bar": ts, "seq": 1},
            ]

        result = execute_advance(plan, callbacks, clock=clock)

        expected: list[dict] = []
        for ts in plan.base_bar_times:
            expected.extend([{"bar": ts, "seq": 0}, {"bar": ts, "seq": 1}])

        self.assertEqual(list(result.events), expected)


class PublicSurfaceTests(unittest.TestCase):
    def test_protocol_and_result_and_function_are_exported(self):
        from backend.intraday import advance_executor as module

        self.assertTrue(hasattr(module, "AdvanceCallbacks"))
        self.assertTrue(hasattr(module, "AdvanceExecutionResult"))
        self.assertTrue(hasattr(module, "execute_advance"))

    def test_executor_does_not_import_flask_or_simulator_modules(self):
        import ast
        import inspect

        from backend.intraday import advance_executor as module

        tree = ast.parse(inspect.getsource(module))
        imported_modules: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_modules.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imported_modules.add(node.module)

        for forbidden in ("flask", "trade_simulator_enhanced", "order_manager", "app_enhanced"):
            self.assertFalse(
                any(forbidden == name or name.startswith(forbidden + ".") for name in imported_modules),
                f"{forbidden} should not be imported by advance_executor, got: {sorted(imported_modules)}",
            )


if __name__ == "__main__":
    unittest.main()
