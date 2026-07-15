from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Protocol, runtime_checkable

import requests

from .models import CryptoBar, CryptoInstrument, FundingEvent, SourceStatus, utc_datetime

class CryptoSourceError(RuntimeError):
    pass

@runtime_checkable
class CryptoMarketSource(Protocol):
    name: str

    def list_instruments(self) -> list[CryptoInstrument]: ...
    def fetch_trade_bars(self, symbol: str, start: datetime, end: datetime) -> list[CryptoBar]: ...
    def fetch_mark_bars(self, symbol: str, start: datetime, end: datetime) -> list[CryptoBar]: ...
    def fetch_funding(self, symbol: str, start: datetime, end: datetime) -> list[FundingEvent]: ...
    def status(self) -> SourceStatus: ...

class HttpCryptoSource:
    name = "unknown"

    def __init__(self, *, requester=None, timeout: float = 10.0, max_pages: int = 100):
        self.requester = requester or requests
        self.timeout = timeout
        self.max_pages = max_pages

    def _get_json(self, url: str, *, params: dict[str, Any], endpoint: str):
        try:
            response = self.requester.get(url, params=params, timeout=self.timeout)
        except Exception as exc:
            raise CryptoSourceError(f"{self.name} request failed for {endpoint}: {exc}") from exc
        status_code = getattr(response, "status_code", 200)
        if status_code < 200 or status_code >= 300:
            detail = getattr(response, "text", "")
            raise CryptoSourceError(f"{self.name} HTTP {status_code} for {endpoint}: {detail}")
        try:
            return response.json()
        except Exception as exc:
            raise CryptoSourceError(f"{self.name} invalid JSON for {endpoint}: {exc}") from exc

    def status(self) -> SourceStatus:
        try:
            self.list_instruments()
        except Exception as exc:
            return SourceStatus(self.name, False, str(exc), datetime.now(timezone.utc))
        return SourceStatus(self.name, True, "ok", datetime.now(timezone.utc))

def milliseconds(value: datetime) -> int:
    return int(utc_datetime(value).timestamp() * 1000)

def from_milliseconds(value: int | str) -> datetime:
    return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)
