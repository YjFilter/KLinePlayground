from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd

from .cache import IntradayCache
from .validator import validate_30m_frame


class IntradayDataUnavailable(RuntimeError):
    pass


class IntradayDataService:
    def __init__(self, source, cache: IntradayCache):
        self.source = source
        self.cache = cache

    @staticmethod
    def _slice(frame: pd.DataFrame, start: datetime, end: datetime) -> pd.DataFrame:
        if frame.empty:
            return frame.copy()
        mask = (frame["datetime"] >= pd.Timestamp(start)) & (frame["datetime"] <= pd.Timestamp(end))
        return frame.loc[mask].reset_index(drop=True)

    @staticmethod
    def _covers_requested_start(coverage, start: datetime) -> bool:
        return coverage.start.date() <= start.date()

    @classmethod
    def _covers_request(cls, coverage, start: datetime, end: datetime) -> bool:
        return cls._covers_requested_start(coverage, start) and coverage.end >= end

    def get_30m(self, stock_code: str, start: datetime, end: datetime) -> pd.DataFrame:
        coverage = self.cache.coverage(stock_code)
        if coverage and self._covers_request(coverage, start, end):
            return self._slice(self.cache.load(stock_code), start, end)
        return self.sync_30m(stock_code, start, end)

    def sync_30m(self, stock_code: str, start: datetime, end: datetime) -> pd.DataFrame:
        existing = self.cache.load(stock_code)
        coverage = self.cache.coverage(stock_code)
        ranges: list[tuple[datetime, datetime]] = []
        step = timedelta(minutes=30)
        if coverage is None:
            ranges.append((start, end))
        else:
            if start.date() < coverage.start.date():
                ranges.append((start, coverage.start - step))
            if end > coverage.end:
                ranges.append((coverage.end + step, end))
        combined = existing
        try:
            for range_start, range_end in ranges:
                incoming = self.source.fetch_30m(stock_code, range_start, range_end)
                validation = validate_30m_frame(incoming)
                if not validation.is_valid:
                    codes = sorted({issue.code for issue in validation.issues})
                    raise IntradayDataUnavailable(
                        f"intraday validation failed for {stock_code}: {', '.join(codes)}"
                    )
                combined = self.cache.merge(combined, incoming)
            if ranges and not combined.empty:
                final_validation = validate_30m_frame(combined)
                if not final_validation.is_valid:
                    codes = sorted({issue.code for issue in final_validation.issues})
                    raise IntradayDataUnavailable(
                        f"merged intraday validation failed for {stock_code}: {', '.join(codes)}"
                    )
                self.cache.save(stock_code, combined, source="baostock", validation=final_validation)
        except IntradayDataUnavailable:
            raise
        except Exception as exc:
            coverage = self.cache.coverage(stock_code)
            cached = self.cache.load(stock_code)
            available = self._slice(cached, start, end)
            if coverage and self._covers_requested_start(coverage, start) and not available.empty:
                return available
            coverage_text = "none" if coverage is None else f"{coverage.start.isoformat()}..{coverage.end.isoformat()}"
            raise IntradayDataUnavailable(
                f"30m data unavailable for {stock_code} {start.date()}..{end.date()}; "
                f"cache={coverage_text}; source_error={exc}"
            ) from exc

        cached = self.cache.load(stock_code)
        available = self._slice(cached, start, end)
        if available.empty:
            final_coverage = self.cache.coverage(stock_code)
            coverage_text = "none" if final_coverage is None else f"{final_coverage.start.isoformat()}..{final_coverage.end.isoformat()}"
            raise IntradayDataUnavailable(
                f"30m data unavailable for {stock_code} {start.date()}..{end.date()}; cache={coverage_text}"
            )
        return available
