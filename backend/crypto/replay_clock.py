from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable

from .models import CryptoPeriod, CryptoReplayAdvance, utc_datetime

_PERIOD_MINUTES = {
    CryptoPeriod.MINUTE_5: 5,
    CryptoPeriod.MINUTE_15: 15,
    CryptoPeriod.MINUTE_30: 30,
    CryptoPeriod.HOUR_1: 60,
    CryptoPeriod.HOUR_4: 240,
    CryptoPeriod.DAILY: 1440,
    CryptoPeriod.WEEKLY: 10080,
}

class CryptoReplayClock:
    def __init__(self, timestamps: Iterable[datetime], initial_time: datetime | None = None, active_period: CryptoPeriod | str = CryptoPeriod.MINUTE_5):
        normalized = tuple(self._normalize(value) for value in timestamps)
        if not normalized:
            raise ValueError("timestamps cannot be empty")
        if any(current >= following for current, following in zip(normalized, normalized[1:])):
            raise ValueError("timestamps must be strictly increasing without duplicates")
        if any(value.minute % 5 or value.second or value.microsecond for value in normalized):
            raise ValueError("timestamps must align to five-minute UTC boundaries")
        if any(following - current != timedelta(minutes=5) for current, following in zip(normalized, normalized[1:])):
            raise ValueError("timestamps must form a continuous five-minute timeline")
        self._timestamps = normalized
        self._index = {value: index for index, value in enumerate(normalized)}
        selected = normalized[0] if initial_time is None else self._normalize(initial_time)
        if selected not in self._index:
            raise ValueError("initial_time must exist in the replay timeline")
        self._initial_index = self._index[selected]
        self._initial_period = CryptoPeriod.parse(active_period)
        self._current_index = self._initial_index
        self._active_period = self._initial_period

    @property
    def timestamps(self):
        return self._timestamps

    @property
    def current_time(self):
        return self._timestamps[self._current_index]

    @property
    def current_index(self):
        return self._current_index

    @property
    def active_period(self):
        return self._active_period

    def set_period(self, period):
        self._active_period = CryptoPeriod.parse(period)

    def reset(self):
        self._current_index = self._initial_index
        self._active_period = self._initial_period

    def has_next(self):
        return self._target_index() is not None

    def plan_next(self):
        target_index = self._target_index()
        if target_index is None:
            return CryptoReplayAdvance(self._active_period, self.current_time, None, (), self._current_index)
        return CryptoReplayAdvance(self._active_period, self.current_time, self._timestamps[target_index], self._timestamps[self._current_index + 1:target_index + 1], self._current_index)

    def advance(self, plan_or_target):
        if isinstance(plan_or_target, CryptoReplayAdvance):
            plan = plan_or_target
            if plan.current_time != self.current_time or plan.revision != self._current_index:
                raise ValueError("cannot advance a stale replay plan")
            if plan.finished:
                raise ValueError("cannot advance a finished replay plan")
            if plan.period != self._active_period:
                raise ValueError("replay plan period does not match the active period")
            if plan != self.plan_next():
                raise ValueError("replay plan does not match the current timeline")
            target = plan.target_time
        else:
            target = self._normalize(plan_or_target)
        if target not in self._index:
            raise ValueError("advance target must exist in the replay timeline")
        target_index = self._index[target]
        if target_index <= self._current_index:
            raise ValueError("advance target must move replay time forward")
        self._current_index = target_index

    def _target_index(self):
        if self._current_index >= len(self._timestamps) - 1:
            return None
        period_minutes = _PERIOD_MINUTES[self._active_period]
        if period_minutes == 5:
            return self._current_index + 1
        for index in range(self._current_index + 1, len(self._timestamps)):
            if self._is_boundary(self._timestamps[index], self._active_period):
                return index
        return len(self._timestamps) - 1

    @staticmethod
    def _is_boundary(value, period):
        if period == CryptoPeriod.WEEKLY:
            return value.weekday() == 6 and value.hour == 23 and value.minute == 55
        if period == CryptoPeriod.DAILY:
            return value.hour == 23 and value.minute == 55
        minutes = _PERIOD_MINUTES[period]
        minute_of_day = value.hour * 60 + value.minute
        return minute_of_day % minutes == minutes - 5

    @staticmethod
    def _normalize(value):
        if hasattr(value, "to_pydatetime"):
            value = value.to_pydatetime()
        if isinstance(value, str):
            value = datetime.fromisoformat(value)
        if not isinstance(value, datetime):
            raise TypeError("replay timestamps must be datetime-like values")
        return utc_datetime(value)

ReplayClock = CryptoReplayClock
