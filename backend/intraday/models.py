from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Final


@dataclass(frozen=True)
class IntradayRange:
    start: datetime
    end: datetime

    def covers(self, start: datetime, end: datetime) -> bool:
        return self.start <= start and self.end >= end


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    timestamp: datetime | None = None


@dataclass
class ValidationResult:
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not self.issues


class ReplayPeriod(str, Enum):
    MINUTE_30 = "30m"
    SESSION_4H = "4h_session"
    DAILY = "daily"
    WEEKLY = "weekly"

    @classmethod
    def parse(cls, value: "ReplayPeriod | str") -> "ReplayPeriod":
        return value if isinstance(value, cls) else cls(value)


BASE_INTERVAL: Final[ReplayPeriod] = ReplayPeriod.MINUTE_30
AGGREGATED_COLUMNS: Final[tuple[str, ...]] = (
    "period",
    "start_time",
    "end_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "amount",
    "source_bar_count",
    "complete",
)


@dataclass(frozen=True)
class PeriodBoundaryIndex:
    timestamps: tuple[datetime, ...]
    session_ends: frozenset[datetime]
    week_ends: frozenset[datetime]
    incomplete_sessions: frozenset[object] = frozenset()


@dataclass(frozen=True)
class ReplayAdvance:
    period: ReplayPeriod
    current_time: datetime
    target_time: datetime | None
    base_bar_times: tuple[datetime, ...]

    @property
    def finished(self) -> bool:
        return self.target_time is None
