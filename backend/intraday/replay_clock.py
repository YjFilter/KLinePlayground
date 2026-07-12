from __future__ import annotations

from bisect import bisect_right
from collections import defaultdict
from datetime import date, datetime, time
from typing import Iterable

from .models import PeriodBoundaryIndex, ReplayAdvance, ReplayPeriod


_STANDARD_SESSION_TIMES = (
    time(10, 0),
    time(10, 30),
    time(11, 0),
    time(11, 30),
    time(13, 30),
    time(14, 0),
    time(14, 30),
    time(15, 0),
)


class ReplayClock:
    def __init__(
        self,
        timestamps: Iterable[datetime],
        initial_time: datetime | None = None,
        active_period: ReplayPeriod | str = ReplayPeriod.MINUTE_30,
    ) -> None:
        normalized = tuple(self._normalize_timestamp(value) for value in timestamps)
        if not normalized:
            raise ValueError("timestamps cannot be empty")
        if any(current >= following for current, following in zip(normalized, normalized[1:])):
            raise ValueError("timestamps must be strictly increasing without duplicates")

        self._timestamps = normalized
        self._timestamp_to_index = {value: index for index, value in enumerate(normalized)}
        self._boundary_index = self._build_boundary_index(normalized)
        self._session_end_indices = tuple(
            self._timestamp_to_index[value]
            for value in sorted(self._boundary_index.session_ends)
        )
        self._week_end_indices = tuple(
            self._timestamp_to_index[value]
            for value in sorted(self._boundary_index.week_ends)
        )

        selected_initial_time = normalized[0] if initial_time is None else self._normalize_timestamp(initial_time)
        if selected_initial_time not in self._timestamp_to_index:
            raise ValueError("initial_time must exist in the replay timeline")

        self._initial_index = self._timestamp_to_index[selected_initial_time]
        self._initial_period = ReplayPeriod.parse(active_period)
        self._current_index = self._initial_index
        self._active_period = self._initial_period

    @property
    def boundary_index(self) -> PeriodBoundaryIndex:
        return self._boundary_index

    @property
    def current_time(self) -> datetime:
        return self._timestamps[self._current_index]

    @property
    def current_index(self) -> int:
        return self._current_index

    @property
    def active_period(self) -> ReplayPeriod:
        return self._active_period

    def set_period(self, period: ReplayPeriod | str) -> None:
        self._active_period = ReplayPeriod.parse(period)

    def reset(self) -> None:
        self._current_index = self._initial_index
        self._active_period = self._initial_period

    def has_next(self) -> bool:
        return self._target_index(self._active_period) is not None

    def plan_next(self) -> ReplayAdvance:
        target_index = self._target_index(self._active_period)
        if target_index is None:
            return ReplayAdvance(
                period=self._active_period,
                current_time=self.current_time,
                target_time=None,
                base_bar_times=(),
            )
        return ReplayAdvance(
            period=self._active_period,
            current_time=self.current_time,
            target_time=self._timestamps[target_index],
            base_bar_times=self._timestamps[self._current_index + 1 : target_index + 1],
        )

    def advance(self, plan_or_target: ReplayAdvance | datetime) -> None:
        if isinstance(plan_or_target, ReplayAdvance):
            plan = plan_or_target
            if plan.finished:
                raise ValueError("cannot advance a finished replay plan")
            if plan.current_time != self.current_time:
                raise ValueError("cannot advance a stale replay plan")
            if plan.period != self._active_period:
                raise ValueError("replay plan period does not match the active period")
            expected = self.plan_next()
            if plan != expected:
                raise ValueError("replay plan does not match the current timeline")
            target = plan.target_time
        else:
            target = self._normalize_timestamp(plan_or_target)

        if target not in self._timestamp_to_index:
            raise ValueError("advance target must exist in the replay timeline")
        target_index = self._timestamp_to_index[target]
        if target_index <= self._current_index:
            raise ValueError("advance target must move replay time forward")
        self._current_index = target_index

    def _target_index(self, period: ReplayPeriod) -> int | None:
        if period == ReplayPeriod.MINUTE_30:
            candidate = self._current_index + 1
            return candidate if candidate < len(self._timestamps) else None
        if period in (ReplayPeriod.SESSION_4H, ReplayPeriod.DAILY):
            return self._next_boundary_index(self._session_end_indices)
        if period == ReplayPeriod.WEEKLY:
            return self._next_boundary_index(self._week_end_indices)
        raise ValueError(f"unsupported replay period: {period}")

    def _next_boundary_index(self, boundary_indices: tuple[int, ...]) -> int | None:
        position = bisect_right(boundary_indices, self._current_index)
        return boundary_indices[position] if position < len(boundary_indices) else None

    @classmethod
    def _build_boundary_index(cls, timestamps: tuple[datetime, ...]) -> PeriodBoundaryIndex:
        sessions: dict[date, list[datetime]] = defaultdict(list)
        for timestamp in timestamps:
            sessions[timestamp.date()].append(timestamp)

        session_ends = frozenset(values[-1] for values in sessions.values())
        incomplete_sessions = frozenset(
            session_date
            for session_date, values in sessions.items()
            if tuple(value.time() for value in values) != _STANDARD_SESSION_TIMES
        )

        weeks: dict[tuple[int, int], list[date]] = defaultdict(list)
        for session_date in sessions:
            iso = session_date.isocalendar()
            weeks[(iso.year, iso.week)].append(session_date)
        week_ends = frozenset(sessions[max(session_dates)][-1] for session_dates in weeks.values())

        return PeriodBoundaryIndex(
            timestamps=timestamps,
            session_ends=session_ends,
            week_ends=week_ends,
            incomplete_sessions=incomplete_sessions,
        )

    @staticmethod
    def _normalize_timestamp(value: datetime) -> datetime:
        if isinstance(value, datetime):
            return value.to_pydatetime() if hasattr(value, "to_pydatetime") else value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError as error:
                raise ValueError(f"invalid replay timestamp: {value!r}") from error
        if hasattr(value, "to_pydatetime"):
            converted = value.to_pydatetime()
            if isinstance(converted, datetime):
                return converted
        raise TypeError("replay timestamps must be datetime-like values")
