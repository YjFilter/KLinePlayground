from __future__ import annotations

import bisect
from datetime import datetime, timedelta, timezone
from typing import Iterable

import numpy as np
import pandas as pd

from .aggregator import _bucket_start_series, _PERIOD_MINUTES
from .models import BASE_INTERVAL_MINUTES, CryptoPeriod, CryptoReplayAdvance, utc_datetime

class CryptoReplayClock:
    def __init__(self, timestamps: Iterable[datetime], initial_time: datetime | None = None, active_period: CryptoPeriod | str = CryptoPeriod.MINUTE_1, base_step_minutes: int = BASE_INTERVAL_MINUTES):
        normalized = tuple(self._normalize(value) for value in timestamps)
        if not normalized:
            raise ValueError("timestamps cannot be empty")
        if any(current >= following for current, following in zip(normalized, normalized[1:])):
            raise ValueError("timestamps must be strictly increasing without duplicates")
        if any(value.minute % base_step_minutes or value.second or value.microsecond for value in normalized):
            raise ValueError(f"timestamps must align to {base_step_minutes}-minute UTC boundaries")
        if any(following - current != timedelta(minutes=base_step_minutes) for current, following in zip(normalized, normalized[1:])):
            raise ValueError(f"timestamps must form a continuous {base_step_minutes}-minute timeline")
        self._timestamps = normalized
        self._base_step_minutes = base_step_minutes
        self._index = {value: index for index, value in enumerate(normalized)}
        self._timestamps_index = pd.DatetimeIndex(normalized)
        # 按周期懒计算的“桶末边界索引”（含最后一根作为末尾不完整桶的兜底目标）。
        self._boundary_cache: dict[CryptoPeriod, tuple[int, ...]] = {}
        self._boundary_set_cache: dict[CryptoPeriod, set[int]] = {}
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
        if period_minutes == self._base_step_minutes:
            return self._current_index + 1
        boundaries = self._boundary_indices(self._active_period)
        pos = bisect.bisect_right(boundaries, self._current_index)
        return boundaries[pos] if pos < len(boundaries) else None

    def _boundary_indices(self, period):
        cached = self._boundary_cache.get(period)
        if cached is not None:
            return cached
        timestamps = self._timestamps_index
        buckets = _bucket_start_series(timestamps, period)
        shifted = timestamps + pd.Timedelta(minutes=self._base_step_minutes)
        buckets_next = _bucket_start_series(shifted, period)
        mask = np.asarray(buckets != buckets_next)
        indices = np.flatnonzero(mask).astype(int)
        # 最后一根始终是合法目标（处理末尾不完整桶）。
        if len(indices) == 0 or indices[-1] != len(timestamps) - 1:
            indices = np.append(indices, len(timestamps) - 1)
        result = tuple(int(i) for i in indices)
        self._boundary_cache[period] = result
        return result

    def _boundary_set(self, period):
        cached = self._boundary_set_cache.get(period)
        if cached is None:
            cached = set(self._boundary_indices(period))
            self._boundary_set_cache[period] = cached
        return cached

    def is_boundary_time(self, value) -> bool:
        """当前周期下，该时间戳是否是桶末边界（即该周期最后一根 base bar）。

        供权益快照按显示周期降采样使用：只在边界记录一条快照。
        """
        normalized = self._normalize(value)
        return self._index[normalized] in self._boundary_set(self._active_period)

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
