from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

import pandas as pd

from .cache import CANDLE_COLUMNS, CryptoMonthlyCache
from .models import BASE_INTERVAL_MINUTES, CryptoBar, CryptoInstrument, FundingEvent, utc_datetime
from .validator import validate_crypto_frame

class CryptoDataUnavailable(RuntimeError):
    pass

class CryptoChartPreparationCancelled(RuntimeError):
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

    def get_chart_bars(self, symbol: str, start: datetime, end: datetime, *, source: str | None = None) -> tuple[str, pd.DataFrame]:
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
                if self._trade_cache_covers(candidate.name, symbol, start, end)
            ]
            cached_names = {candidate.name for candidate in cached}
            candidates = cached + [candidate for candidate in candidates if candidate.name not in cached_names]
        failures = []
        for candidate in candidates:
            try:
                frame = self.cache.load(candidate.name, symbol, "trade", start, end, numeric="float")
                expected = pd.date_range(start=start, end=end, freq=f"{BASE_INTERVAL_MINUTES}min", tz="UTC")
                actual = pd.DatetimeIndex(frame["timestamp"]) if not frame.empty else pd.DatetimeIndex([])
                if actual.equals(expected):
                    return candidate.name, self._decorate(frame, candidate.name, symbol, "trade")
                missing = self._missing_ranges(frame, start, end)
                for range_start, range_end in missing:
                    for chunk_start, chunk_end in self._natural_month_chunks(range_start, range_end):
                        incoming = self._bars_frame(candidate.fetch_trade_bars(symbol, chunk_start, chunk_end))
                        validation = validate_crypto_frame(incoming, kind="trade")
                        if not validation.is_valid:
                            codes = ", ".join(sorted({issue.code for issue in validation.issues}))
                            raise CryptoDataUnavailable(f"{candidate.name} invalid trade data: {codes}")
                        if not incoming.empty:
                            self.cache.save(candidate.name, symbol, "trade", incoming)
                if missing:
                    frame = self.cache.load(candidate.name, symbol, "trade", start, end, numeric="float")
                    actual = pd.DatetimeIndex(frame["timestamp"]) if not frame.empty else pd.DatetimeIndex([])
                if not actual.equals(expected):
                    raise CryptoDataUnavailable(f"{candidate.name} lacks complete trade coverage for {symbol}")
                return candidate.name, self._decorate(frame, candidate.name, symbol, "trade")
            except Exception as exc:
                failures.append(f"{candidate.name}: {exc}")
        raise CryptoDataUnavailable(
            f"crypto chart data unavailable for {symbol} {start.isoformat()}..{end.isoformat()}; "
            + "; ".join(failures)
        )

    def prepare_chart_bars(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        *,
        source: str | None,
        progress_callback=None,
        cancel_check=None,
    ) -> tuple[str, pd.DataFrame]:
        symbol = symbol.upper()
        start = utc_datetime(start)
        end = utc_datetime(end)
        if start > end:
            raise ValueError("crypto data start must not be after end")
        if any(
            value.minute % BASE_INTERVAL_MINUTES or value.second or value.microsecond
            for value in (start, end)
        ):
            raise ValueError(f"crypto chart preparation requires aligned {BASE_INTERVAL_MINUTES}-minute boundaries")

        chunks = self._natural_month_chunks(start, end)
        frames = []
        resolved_source = source
        total_chunks = len(chunks)
        for index, (chunk_start, chunk_end) in enumerate(chunks, start=1):
            if cancel_check is not None and cancel_check():
                raise CryptoChartPreparationCancelled(
                    f"crypto chart preparation cancelled for {symbol} before chunk "
                    f"{index} of {total_chunks}"
                )
            if progress_callback is not None:
                progress_callback({
                    "completed_chunks": index - 1,
                    "total_chunks": total_chunks,
                    "current_start": chunk_start,
                    "current_end": chunk_end,
                    "source": resolved_source,
                    "symbol": symbol,
                })
            chunk_source, frame = self.get_chart_bars(
                symbol,
                chunk_start,
                chunk_end,
                source=resolved_source,
            )
            if resolved_source is None:
                resolved_source = chunk_source
            if chunk_source != resolved_source:
                raise CryptoDataUnavailable(
                    f"crypto chart preparation cannot mix sources for {symbol}: "
                    f"expected {resolved_source}, received {chunk_source}"
                )
            if cancel_check is not None and cancel_check():
                if index < total_chunks:
                    raise CryptoChartPreparationCancelled(
                        f"crypto chart preparation cancelled for {symbol} before chunk "
                        f"{index + 1} of {total_chunks}"
                    )
                raise CryptoChartPreparationCancelled(
                    f"crypto chart preparation cancelled for {symbol} after chunk "
                    f"{index} of {total_chunks}"
                )
            frames.append(frame)
            if progress_callback is not None:
                progress_callback({
                    "completed_chunks": index,
                    "total_chunks": total_chunks,
                    "current_start": chunk_start,
                    "current_end": chunk_end,
                    "source": resolved_source,
                    "symbol": symbol,
                })

        combined = pd.concat(frames, ignore_index=True)
        combined["timestamp"] = pd.to_datetime(combined["timestamp"], utc=True)
        combined = (
            combined.drop_duplicates(subset=["timestamp"], keep="last")
            .sort_values("timestamp")
            .reset_index(drop=True)
        )
        expected = pd.date_range(start=start, end=end, freq=f"{BASE_INTERVAL_MINUTES}min", tz="UTC")
        actual = pd.DatetimeIndex(combined["timestamp"])
        if not actual.equals(expected):
            raise CryptoDataUnavailable(
                f"{resolved_source} lacks continuous {BASE_INTERVAL_MINUTES}-minute chart coverage for "
                f"{symbol} {start.isoformat()}..{end.isoformat()}"
            )
        actual_sources = set(combined["source"].dropna())
        if actual_sources != {resolved_source}:
            raise CryptoDataUnavailable(
                f"crypto chart preparation cannot mix sources for {symbol}: "
                f"expected only {resolved_source}"
            )
        return resolved_source, combined

    @staticmethod
    def _natural_month_chunks(start, end):
        chunks = []
        cursor = start
        while cursor <= end:
            if cursor.month == 12:
                next_month = cursor.replace(
                    year=cursor.year + 1,
                    month=1,
                    day=1,
                    hour=0,
                    minute=0,
                    second=0,
                    microsecond=0,
                )
            else:
                next_month = cursor.replace(
                    month=cursor.month + 1,
                    day=1,
                    hour=0,
                    minute=0,
                    second=0,
                    microsecond=0,
                )
            chunk_end = min(end, next_month - timedelta(minutes=BASE_INTERVAL_MINUTES))
            chunks.append((cursor, chunk_end))
            cursor = chunk_end + timedelta(minutes=BASE_INTERVAL_MINUTES)
        return chunks

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

    def _trade_cache_covers(self, source, symbol, start, end):
        coverage = self.cache.coverage(source, symbol, "trade")
        return bool(coverage and coverage.covers(start, end))

    @staticmethod
    def _missing_ranges(frame, start, end):
        available = set(pd.to_datetime(frame["timestamp"], utc=True).dt.to_pydatetime()) if not frame.empty else set()
        missing = []
        cursor = start
        gap_start = None
        previous = None
        while cursor <= end:
            if cursor not in available:
                gap_start = gap_start or cursor
                previous = cursor
            elif gap_start is not None:
                missing.append((gap_start, previous))
                gap_start = None
            cursor += timedelta(minutes=BASE_INTERVAL_MINUTES)
        if gap_start is not None:
            missing.append((gap_start, previous))
        return missing

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
                for chunk_start, chunk_end in self._natural_month_chunks(range_start, range_end):
                    incoming = self._bars_frame(fetcher(symbol, chunk_start, chunk_end))
                    validation = validate_crypto_frame(incoming, kind=kind)
                    if not validation.is_valid:
                        codes = ", ".join(sorted({issue.code for issue in validation.issues}))
                        raise CryptoDataUnavailable(f"{source.name} invalid {kind} data: {codes}")
                    if not incoming.empty:
                        self.cache.save(source.name, symbol, kind, incoming)
        trade = self.cache.load(source.name, symbol, "trade", start, end)
        mark = self.cache.load(source.name, symbol, "mark", start, end)
        expected = pd.date_range(start=start, end=end, freq=f"{BASE_INTERVAL_MINUTES}min", tz="UTC")
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
