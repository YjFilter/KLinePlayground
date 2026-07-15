from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Final

BASE_INTERVAL_MINUTES: Final[int] = 5

class CryptoPeriod(str, Enum):
    MINUTE_5 = "5m"
    MINUTE_15 = "15m"
    MINUTE_30 = "30m"
    HOUR_1 = "1h"
    HOUR_4 = "4h"
    DAILY = "daily"
    WEEKLY = "weekly"

    @classmethod
    def parse(cls, value: "CryptoPeriod | str") -> "CryptoPeriod":
        return value if isinstance(value, cls) else cls(value)

@dataclass(frozen=True)
class CryptoInstrument:
    symbol: str
    source: str
    base_asset: str
    quote_asset: str
    contract_type: str
    status: str
    listed_at: datetime
    tick_size: Decimal
    quantity_step: Decimal
    min_quantity: Decimal
    min_notional: Decimal
    quote_turnover_24h: Decimal = Decimal("0")

    @property
    def active(self) -> bool:
        return self.status.lower() in {"trading", "active"}

@dataclass(frozen=True)
class CryptoBar:
    source: str
    symbol: str
    kind: str
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal | None = None
    turnover: Decimal | None = None

@dataclass(frozen=True)
class FundingEvent:
    source: str
    symbol: str
    timestamp: datetime
    rate: Decimal
    mark_price: Decimal | None = None

@dataclass(frozen=True)
class SourceStatus:
    source: str
    available: bool
    message: str = ""
    checked_at: datetime | None = None
    latency_ms: int | None = None

@dataclass(frozen=True)
class CryptoRange:
    start: datetime
    end: datetime

    def covers(self, start: datetime, end: datetime) -> bool:
        return self.start <= start and self.end >= end

@dataclass(frozen=True)
class CryptoReplayAdvance:
    period: CryptoPeriod
    current_time: datetime
    target_time: datetime | None
    base_bar_times: tuple[datetime, ...]
    revision: int = 0

    @property
    def finished(self) -> bool:
        return self.target_time is None

def utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
