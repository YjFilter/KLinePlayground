from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import random

import pandas as pd


_BSE_PREFIXES = ("43", "83", "87", "92")


@dataclass(frozen=True)
class RandomIntradaySelection:
    stock_code: str
    start_time: datetime
    context_start: datetime
    available_training_days: int
    base_bars: pd.DataFrame


class IntradayRandomSelector:
    def __init__(self, candidate_provider, data_service, rng=None, max_attempts=20):
        if max_attempts <= 0:
            raise ValueError("max_attempts must be positive")
        self.candidate_provider = candidate_provider
        self.data_service = data_service
        self.rng = rng if rng is not None else random.Random()
        self.max_attempts = max_attempts

    def select(self, *, sector, date_start, date_end, max_training_days):
        range_start = self._normalize_date(date_start, "date_start")
        range_end = self._normalize_date(date_end, "date_end")
        if range_end < range_start:
            raise ValueError("date_end must not be earlier than date_start")
        if max_training_days < 0:
            raise ValueError("max_training_days must be non-negative")

        requested_context_start = (range_start - pd.DateOffset(years=2)).to_pydatetime()
        requested_end = max(
            range_end + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1),
            pd.Timestamp(datetime.now()),
        ).to_pydatetime()
        failure_counts: dict[str, int] = {}

        for _ in range(self.max_attempts):
            try:
                stock_code = str(self.candidate_provider(sector, date_start, date_end)).strip()
            except Exception:
                self._record_failure(failure_counts, "candidate provider error")
                continue

            if not stock_code:
                self._record_failure(failure_counts, "invalid stock code")
                continue
            if stock_code.startswith(_BSE_PREFIXES):
                self._record_failure(failure_counts, "BSE stock excluded")
                continue

            try:
                frame = self.data_service.get_30m(stock_code, requested_context_start, requested_end)
            except Exception:
                self._record_failure(failure_counts, "data source error")
                continue

            normalized = self._normalize_frame(frame)
            if normalized is None:
                self._record_failure(failure_counts, "empty or invalid 30m data")
                continue

            eligible = self._eligible_start_times(
                normalized,
                range_start,
                range_end,
                max_training_days,
            )
            if not eligible:
                self._record_failure(failure_counts, "insufficient history or future trading dates")
                continue

            selected = pd.Timestamp(self.rng.choice(eligible))
            trading_dates = normalized["datetime"].dt.normalize().drop_duplicates()
            available_training_days = int((trading_dates >= selected.normalize()).sum())
            return RandomIntradaySelection(
                stock_code=stock_code,
                start_time=selected.to_pydatetime(),
                context_start=(selected - pd.DateOffset(years=2)).to_pydatetime(),
                available_training_days=available_training_days,
                base_bars=normalized,
            )

        details = ", ".join(f"{reason}: {count}" for reason, count in sorted(failure_counts.items()))
        suffix = f" Failures: {details}." if details else ""
        raise ValueError(
            f"no valid intraday blind-box candidate after {self.max_attempts} attempts."
            f"{suffix} widen the date range, reduce max_training_days, or change sector or data source."
        )

    @staticmethod
    def _normalize_date(value, name):
        try:
            timestamp = pd.Timestamp(value)
        except Exception as exc:
            raise ValueError(f"{name} must be a valid date") from exc
        if pd.isna(timestamp):
            raise ValueError(f"{name} must be a valid date")
        return timestamp.normalize()

    @staticmethod
    def _normalize_frame(frame):
        if frame is None or not isinstance(frame, pd.DataFrame) or frame.empty:
            return None
        if "datetime" not in frame.columns:
            return None
        normalized = frame.copy()
        normalized["datetime"] = pd.to_datetime(normalized["datetime"], errors="coerce")
        if normalized["datetime"].isna().any():
            return None
        return normalized.sort_values("datetime", kind="stable").reset_index(drop=True)

    @staticmethod
    def _eligible_start_times(frame, range_start, range_end, max_training_days):
        trading_dates = frame["datetime"].dt.normalize().drop_duplicates().reset_index(drop=True)
        earliest_timestamp = frame["datetime"].iloc[0]
        eligible = []

        for index, trading_date in enumerate(trading_dates):
            if trading_date < range_start or trading_date > range_end:
                continue
            day_rows = frame.loc[frame["datetime"].dt.normalize() == trading_date, "datetime"]
            start_time = day_rows.iloc[0]
            context_start = start_time - pd.DateOffset(years=2)
            if earliest_timestamp.normalize() > context_start.normalize():
                continue
            remaining_days = len(trading_dates) - index
            if max_training_days and remaining_days < max_training_days:
                continue
            eligible.append(start_time.to_pydatetime())

        return eligible

    @staticmethod
    def _record_failure(failure_counts, reason):
        failure_counts[reason] = failure_counts.get(reason, 0) + 1
