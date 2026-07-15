from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

import pandas as pd

from .cache import CANDLE_COLUMNS, CryptoMonthlyCache
from .models import CryptoBar, CryptoInstrument, FundingEvent, utc_datetime
from .validator import validate_crypto_frame

class CryptoDataUnavailable(RuntimeError):
    pass

@dataclass(frozen=True)
class CryptoDataBundle:
    source: str
    symbol: str
    start: datetime
    end: datetime
    trade_bars: pd.DataFrame
    mark_bars: pd.DataFrame
    funding: tuple[FundingEvent, ...]
    instrument: CryptoInstrument

class CryptoDataService:
    def __init__(self, sources, cache: CryptoMonthlyCache):
        self.sources = list(sources)
        self.cache = cache
        self._instrument_cache = {}
        self._funding_cache = {}

    def get_bundle(self, symbol: str, start: datetime, end: datetime, *, source: str | None = None) -> CryptoDataBundle:
        symbol = symbol.upper()
        start = utc_datetime(start)
        end = utc_datetime(end)
        if start > end:
            raise ValueError("crypto data start must not be after end")
        candidates = [item for item in self.sources if source is None or item.name == source]
        if not candidates:
            raise CryptoDataUnavailable(f"unknown crypto source: {source}")
        if source is None:
            cached = [
                candidate for candidate in candidates
                if self._has_complete_cache(candidate.name, symbol, start, end)
            ]
            if cached:
                cached_names = {candidate.name for candidate in cached}
                candidates = cached + [
                    candidate for candidate in candidates if candidate.name not in cached_names
                ]
        failures = []
        for candidate in candidates:
            try:
                return self._bundle_from_source(candidate, symbol, start, end)
            except Exception as exc:
                failures.append(f"{candidate.name}: {exc}")
        raise CryptoDataUnavailable(f"crypto data unavailable for {symbol} {start.isoformat()}..{end.isoformat()}; " + "; ".join(failures))

    def _has_complete_cache(self, source, symbol, start, end):
        if self.cache.load_instrument(source, symbol) is None:
            return False
        trade = self.cache.coverage(source, symbol, "trade")
        mark = self.cache.coverage(source, symbol, "mark")
        return bool(
            trade and trade.covers(start, end)
            and mark and mark.covers(start, end)
            and self.cache.funding_covers(source, symbol, start, end)
        )

    def sync(self, symbol: str, start: datetime, end: datetime, *, source: str | None = None) -> CryptoDataBundle:
        return self.get_bundle(symbol, start, end, source=source)

    def _bundle_from_source(self, source, symbol, start, end):
        instrument_key = (source.name, symbol)
        instrument = self.cache.load_instrument(source.name, symbol) or self._instrument_cache.get(instrument_key)
        if instrument is None:
            instruments = source.list_instruments()
            for item in instruments:
                key = (source.name, item.symbol.upper())
                self._instrument_cache[key] = item
                self.cache.save_instrument(item)
            instrument = self._instrument_cache.get(instrument_key)
        if instrument is None:
            raise CryptoDataUnavailable(f"{symbol} is not listed by {source.name}")
        for kind, fetcher in (("trade", source.fetch_trade_bars), ("mark", source.fetch_mark_bars)):
            for range_start, range_end in self.cache.missing_ranges(source.name, symbol, kind, start, end):
                incoming = self._bars_frame(fetcher(symbol, range_start, range_end))
                validation = validate_crypto_frame(incoming, kind=kind)
                if not validation.is_valid:
                    codes = ", ".join(sorted({issue.code for issue in validation.issues}))
                    raise CryptoDataUnavailable(f"{source.name} invalid {kind} data: {codes}")
                if not incoming.empty:
                    self.cache.save(source.name, symbol, kind, incoming)
        trade = self.cache.load(source.name, symbol, "trade", start, end)
        mark = self.cache.load(source.name, symbol, "mark", start, end)
        expected = pd.date_range(start=start, end=end, freq="5min", tz="UTC")
        trade_index = pd.DatetimeIndex(trade["timestamp"]) if not trade.empty else pd.DatetimeIndex([])
        mark_index = pd.DatetimeIndex(mark["timestamp"]) if not mark.empty else pd.DatetimeIndex([])
        if not trade_index.equals(expected) or not mark_index.equals(expected) or not trade_index.equals(mark_index):
            raise CryptoDataUnavailable(f"{source.name} lacks complete aligned trade/mark coverage for {symbol}")
        trade = self._decorate(trade, source.name, symbol, "trade")
        mark = self._decorate(mark, source.name, symbol, "mark")
        funding_key = (source.name, symbol)
        if self.cache.funding_covers(source.name, symbol, start, end):
            self._funding_cache[funding_key] = tuple(
                self.cache.load_funding(source.name, symbol, start, end)
            )
        else:
            funding_events = source.fetch_funding(symbol, start, end)
            combined_funding = [*self._funding_cache.get(funding_key, ()), *funding_events]
            self._funding_cache[funding_key] = tuple(sorted({event.timestamp: event for event in combined_funding}.values(), key=lambda event: event.timestamp))
            self.cache.save_funding(source.name, symbol, list(self._funding_cache[funding_key]), start, end)
        funding = tuple(event for event in self._funding_cache[funding_key] if start <= event.timestamp <= end)
        return CryptoDataBundle(source.name, symbol, start, end, trade, mark, funding, instrument)

    @staticmethod
    def _bars_frame(bars: list[CryptoBar]) -> pd.DataFrame:
        rows = [{
            "timestamp": bar.timestamp, "open": bar.open, "high": bar.high, "low": bar.low, "close": bar.close,
            "volume": bar.volume if bar.volume is not None else Decimal("0"),
            "turnover": bar.turnover if bar.turnover is not None else Decimal("0"),
        } for bar in bars]
        return pd.DataFrame(rows, columns=CANDLE_COLUMNS)

    @staticmethod
    def _decorate(frame, source, symbol, kind):
        result = frame.copy()
        result["source"] = source
        result["symbol"] = symbol
        result["kind"] = kind
        return result
