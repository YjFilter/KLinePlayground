from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


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
