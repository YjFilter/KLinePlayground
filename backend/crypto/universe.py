from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import random
from typing import Protocol

from .models import CryptoInstrument, utc_datetime

class CryptoUniverseError(RuntimeError):
    pass

class CryptoAvailabilityChecker(Protocol):
    def __call__(self, instrument: CryptoInstrument, start: datetime, end: datetime) -> bool: ...

@dataclass(frozen=True)
class InstrumentSnapshot:
    source: str
    captured_at: datetime
    instruments: tuple[CryptoInstrument, ...]

class CryptoUniverse:
    def __init__(self, sources, *, now=None, rng=None, snapshot_ttl: timedelta = timedelta(minutes=5), availability_checker: CryptoAvailabilityChecker | None = None):
        self.sources = list(sources)
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.rng = rng or random.SystemRandom()
        self.snapshot_ttl = snapshot_ttl
        self.availability_checker = availability_checker
        self._snapshot = None

    def snapshot(self, *, refresh: bool = False) -> InstrumentSnapshot:
        current = utc_datetime(self.now())
        if not refresh and self._snapshot is not None and current - self._snapshot.captured_at <= self.snapshot_ttl:
            return self._snapshot
        failures = []
        for source in self.sources:
            try:
                instruments = tuple(source.list_instruments())
                self._snapshot = InstrumentSnapshot(source.name, current, instruments)
                return self._snapshot
            except Exception as exc:
                failures.append(f"{source.name}: {exc}")
        raise CryptoUniverseError("unable to load crypto instrument universe; " + "; ".join(failures))

    def eligible_instruments(self, *, refresh: bool = False) -> list[CryptoInstrument]:
        current = utc_datetime(self.now())
        minimum_listing = current - timedelta(days=180)
        result = []
        for instrument in self.snapshot(refresh=refresh).instruments:
            perpetual = "perpetual" in instrument.contract_type.lower()
            if instrument.active and instrument.quote_asset.upper() == "USDT" and perpetual and utc_datetime(instrument.listed_at) <= minimum_listing:
                result.append(instrument)
        return sorted(result, key=lambda item: (-item.quote_turnover_24h, item.symbol))

    def top_instruments(self, limit: int = 50, *, refresh: bool = False) -> list[CryptoInstrument]:
        if limit < 0:
            raise ValueError("limit must be non-negative")
        return self.eligible_instruments(refresh=refresh)[:limit]

    def search(self, query: str = "", limit: int = 20, *, refresh: bool = False) -> list[CryptoInstrument]:
        term = query.strip().upper()
        matches = [item for item in self.eligible_instruments(refresh=refresh) if not term or term in item.symbol.upper() or term in item.base_asset.upper()]
        return matches[:limit]

    def select_random(self, *, start=None, end=None, max_retries: int = 10) -> CryptoInstrument:
        candidates = self.top_instruments()
        if not candidates:
            raise CryptoUniverseError("no active USDT perpetual instruments with at least 180 days of history")
        if max_retries <= 0:
            raise ValueError("max_retries must be positive")
        if self.availability_checker is not None:
            if start is None or end is None:
                raise ValueError("availability_checker requires requested start and end")
            start = utc_datetime(start)
            end = utc_datetime(end)
            if start > end:
                raise ValueError("availability start must not be after end")
        for _ in range(max_retries):
            candidate = self.rng.choice(candidates)
            if self.availability_checker is None:
                return candidate
            available = self.availability_checker(candidate, start, end)
            if available:
                return candidate
        raise CryptoUniverseError(f"unable to select an available crypto instrument after {max_retries} attempts")
