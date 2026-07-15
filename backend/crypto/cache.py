from __future__ import annotations

import gzip
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pandas as pd

from .models import CryptoInstrument, CryptoRange, FundingEvent, utc_datetime
from .validator import validate_crypto_frame

CANDLE_COLUMNS = ["timestamp", "open", "high", "low", "close", "volume", "turnover"]

class CryptoCacheCorruption(RuntimeError):
    pass

class CryptoMonthlyCache:
    def __init__(self, root: Path):
        self.root = Path(root)

    def _directory(self, source: str, symbol: str, kind: str) -> Path:
        return self.root / source / symbol.upper() / kind

    def _data_path(self, source: str, symbol: str, kind: str, month: str) -> Path:
        return self._directory(source, symbol, kind) / f"{month}.csv.gz"

    def _instrument_path(self, source: str, symbol: str) -> Path:
        return self.root / source / symbol.upper() / "instrument.json"

    @staticmethod
    def _paths_for_range(directory: Path, start: datetime | None, end: datetime | None) -> list[Path]:
        paths = sorted(directory.glob("*.csv.gz")) if directory.exists() else []
        start_month = utc_datetime(start).strftime("%Y-%m") if start is not None else None
        end_month = utc_datetime(end).strftime("%Y-%m") if end is not None else None
        return [
            path for path in paths
            if (start_month is None or path.name[:7] >= start_month)
            and (end_month is None or path.name[:7] <= end_month)
        ]

    def save_instrument(self, instrument: CryptoInstrument) -> None:
        path = self._instrument_path(instrument.source, instrument.symbol)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(path.name + ".tmp")
        payload = {
            "symbol": instrument.symbol, "source": instrument.source,
            "base_asset": instrument.base_asset, "quote_asset": instrument.quote_asset,
            "contract_type": instrument.contract_type, "status": instrument.status,
            "listed_at": utc_datetime(instrument.listed_at).isoformat(),
            "tick_size": str(instrument.tick_size), "quantity_step": str(instrument.quantity_step),
            "min_quantity": str(instrument.min_quantity), "min_notional": str(instrument.min_notional),
            "quote_turnover_24h": str(instrument.quote_turnover_24h),
        }
        temp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        temp.replace(path)

    def load_instrument(self, source: str, symbol: str) -> CryptoInstrument | None:
        path = self._instrument_path(source, symbol)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return CryptoInstrument(
                payload["symbol"], payload["source"], payload["base_asset"], payload["quote_asset"],
                payload["contract_type"], payload["status"], datetime.fromisoformat(payload["listed_at"]),
                Decimal(payload["tick_size"]), Decimal(payload["quantity_step"]),
                Decimal(payload["min_quantity"]), Decimal(payload["min_notional"]),
                Decimal(payload["quote_turnover_24h"]),
            )
        except Exception as exc:
            raise CryptoCacheCorruption(f"corrupt crypto instrument cache for {source}/{symbol}: {exc}") from exc

    def save_funding(self, source: str, symbol: str, events: list[FundingEvent], start: datetime, end: datetime) -> None:
        start = utc_datetime(start)
        end = utc_datetime(end)
        cursor = datetime(start.year, start.month, 1, tzinfo=timezone.utc)
        while cursor <= end:
            next_month = datetime(cursor.year + (cursor.month == 12), 1 if cursor.month == 12 else cursor.month + 1, 1, tzinfo=timezone.utc)
            month = cursor.strftime("%Y-%m")
            month_start = max(start, cursor)
            month_end = min(end, next_month - timedelta(microseconds=1))
            path = self._data_path(source, symbol, "funding", month)
            existing = self._load_funding_path(source, symbol, path)
            incoming = [event for event in events if cursor <= utc_datetime(event.timestamp) < next_month]
            merged = sorted({event.timestamp: event for event in [*existing, *incoming]}.values(), key=lambda event: event.timestamp)
            path.parent.mkdir(parents=True, exist_ok=True)
            data_temp = path.with_name(path.name + ".tmp")
            with gzip.open(data_temp, "wt", encoding="utf-8", newline="") as handle:
                pd.DataFrame([{"timestamp": event.timestamp.isoformat(), "rate": str(event.rate), "mark_price": "" if event.mark_price is None else str(event.mark_price)} for event in merged], columns=["timestamp", "rate", "mark_price"]).to_csv(handle, index=False)
            metadata_path = path.with_name(f"{month}.json")
            ranges = []
            if metadata_path.exists():
                ranges = json.loads(metadata_path.read_text(encoding="utf-8")).get("coverage_ranges", [])
            ranges.append([month_start.isoformat(), month_end.isoformat()])
            metadata_temp = metadata_path.with_name(metadata_path.name + ".tmp")
            metadata_temp.write_text(json.dumps({"source": source, "symbol": symbol.upper(), "kind": "funding", "coverage_ranges": self._merge_ranges(ranges), "rows": len(merged), "synchronized_at": datetime.now(timezone.utc).isoformat()}, indent=2, sort_keys=True), encoding="utf-8")
            data_temp.replace(path)
            metadata_temp.replace(metadata_path)
            cursor = next_month

    def load_funding(self, source: str, symbol: str, start: datetime | None = None, end: datetime | None = None) -> list[FundingEvent]:
        directory = self._directory(source, symbol, "funding")
        events = []
        for path in self._paths_for_range(directory, start, end):
            events.extend(self._load_funding_path(source, symbol, path))
        deduplicated = sorted({event.timestamp: event for event in events}.values(), key=lambda event: event.timestamp)
        if start is not None:
            start = utc_datetime(start)
            deduplicated = [event for event in deduplicated if event.timestamp >= start]
        if end is not None:
            end = utc_datetime(end)
            deduplicated = [event for event in deduplicated if event.timestamp <= end]
        return deduplicated

    def funding_covers(self, source: str, symbol: str, start: datetime, end: datetime) -> bool:
        start = utc_datetime(start)
        end = utc_datetime(end)
        directory = self._directory(source, symbol, "funding")
        ranges = []
        if directory.exists():
            for path in sorted(directory.glob("*.json")):
                ranges.extend(json.loads(path.read_text(encoding="utf-8")).get("coverage_ranges", []))
        merged = self._merge_ranges(ranges)
        return any(datetime.fromisoformat(left) <= start and datetime.fromisoformat(right) >= end for left, right in merged)

    def _load_funding_path(self, source: str, symbol: str, path: Path) -> list[FundingEvent]:
        if not path.exists():
            return []
        try:
            with gzip.open(path, "rt", encoding="utf-8") as handle:
                frame = pd.read_csv(handle, dtype=str, keep_default_na=False)
            return [FundingEvent(source, symbol.upper(), pd.Timestamp(row["timestamp"]).to_pydatetime(), Decimal(row["rate"]), Decimal(row["mark_price"]) if row["mark_price"] else None) for _, row in frame.iterrows()]
        except Exception as exc:
            raise CryptoCacheCorruption(f"corrupt crypto funding cache for {source}/{symbol}/{path.stem}: {exc}") from exc

    @staticmethod
    def _merge_ranges(ranges):
        parsed = sorted((datetime.fromisoformat(left), datetime.fromisoformat(right)) for left, right in ranges)
        merged = []
        for left, right in parsed:
            if merged and left <= merged[-1][1] + timedelta(microseconds=1):
                merged[-1] = (merged[-1][0], max(merged[-1][1], right))
            else:
                merged.append((left, right))
        return [[left.isoformat(), right.isoformat()] for left, right in merged]

    @staticmethod
    def merge(existing: pd.DataFrame, incoming: pd.DataFrame) -> pd.DataFrame:
        frames = [value for value in (existing, incoming) if value is not None and not value.empty]
        if not frames:
            return pd.DataFrame(columns=CANDLE_COLUMNS)
        merged = pd.concat(frames, ignore_index=True)
        merged["timestamp"] = pd.to_datetime(merged["timestamp"], utc=True)
        columns = [column for column in CANDLE_COLUMNS if column in merged.columns]
        return merged[columns].drop_duplicates("timestamp", keep="last").sort_values("timestamp").reset_index(drop=True)

    def save(self, source: str, symbol: str, kind: str, frame: pd.DataFrame) -> None:
        validation = validate_crypto_frame(frame, kind=kind)
        if not validation.is_valid:
            codes = ", ".join(sorted({issue.code for issue in validation.issues}))
            raise ValueError(f"invalid crypto {kind} frame for {source}/{symbol}: {codes}")
        normalized = frame.copy()
        normalized["timestamp"] = pd.to_datetime(normalized["timestamp"], utc=True)
        normalized["month"] = normalized["timestamp"].dt.strftime("%Y-%m")
        for month, incoming in normalized.groupby("month", sort=True):
            incoming = incoming.drop(columns="month")
            existing = self._load_path(source, symbol, kind, self._data_path(source, symbol, kind, month), missing_ok=True)
            merged = self.merge(existing, incoming)
            data_path = self._data_path(source, symbol, kind, month)
            data_path.parent.mkdir(parents=True, exist_ok=True)
            data_temp = data_path.with_name(data_path.name + ".tmp")
            metadata_path = data_path.with_name(f"{month}.json")
            metadata_temp = metadata_path.with_name(metadata_path.name + ".tmp")
            serial = merged.copy()
            serial["timestamp"] = serial["timestamp"].map(lambda value: value.isoformat())
            with gzip.open(data_temp, "wt", encoding="utf-8", newline="") as handle:
                serial.to_csv(handle, index=False)
            metadata = {
                "source": source, "symbol": symbol.upper(), "kind": kind, "interval": "5m",
                "first_timestamp": merged["timestamp"].min().isoformat(), "last_timestamp": merged["timestamp"].max().isoformat(),
                "rows": int(len(merged)), "validation": "valid", "synchronized_at": datetime.now(timezone.utc).isoformat(),
            }
            metadata_temp.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")
            data_temp.replace(data_path)
            metadata_temp.replace(metadata_path)

    def _load_path(self, source, symbol, kind, path, *, missing_ok=False):
        if not path.exists():
            if missing_ok:
                return pd.DataFrame(columns=CANDLE_COLUMNS)
            return pd.DataFrame(columns=CANDLE_COLUMNS)
        try:
            with gzip.open(path, "rt", encoding="utf-8") as handle:
                frame = pd.read_csv(handle, dtype=str)
            if "timestamp" not in frame.columns:
                raise ValueError("missing timestamp")
            frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
            for column in ("open", "high", "low", "close", "volume", "turnover"):
                if column in frame.columns:
                    frame[column] = frame[column].map(lambda value: Decimal(value) if pd.notna(value) and value != "" else None)
            validation = validate_crypto_frame(frame, kind=kind)
            if not validation.is_valid:
                raise ValueError(", ".join(issue.code for issue in validation.issues))
            return frame
        except Exception as exc:
            raise CryptoCacheCorruption(f"corrupt crypto cache for {source}/{symbol}/{kind}/{path.stem.replace('.csv', '')}: {exc}") from exc

    def load(self, source: str, symbol: str, kind: str, start: datetime | None = None, end: datetime | None = None) -> pd.DataFrame:
        directory = self._directory(source, symbol, kind)
        frames = [
            self._load_path(source, symbol, kind, path)
            for path in self._paths_for_range(directory, start, end)
        ]
        result = self.merge(pd.DataFrame(columns=CANDLE_COLUMNS), pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=CANDLE_COLUMNS))
        if result.empty:
            return result
        if start is not None:
            result = result.loc[result["timestamp"] >= pd.Timestamp(utc_datetime(start))]
        if end is not None:
            result = result.loc[result["timestamp"] <= pd.Timestamp(utc_datetime(end))]
        return result.reset_index(drop=True)

    def coverage(self, source: str, symbol: str, kind: str) -> CryptoRange | None:
        directory = self._directory(source, symbol, kind)
        metadata_paths = sorted(directory.glob("*.json")) if directory.exists() else []
        starts = []
        ends = []
        try:
            for path in metadata_paths:
                data_path = path.with_suffix(".csv.gz")
                if not data_path.exists():
                    continue
                metadata = json.loads(path.read_text(encoding="utf-8"))
                if metadata.get("validation") != "valid":
                    continue
                starts.append(utc_datetime(datetime.fromisoformat(metadata["first_timestamp"])))
                ends.append(utc_datetime(datetime.fromisoformat(metadata["last_timestamp"])))
        except Exception as exc:
            raise CryptoCacheCorruption(f"corrupt crypto cache metadata for {source}/{symbol}/{kind}: {exc}") from exc
        if starts:
            return CryptoRange(min(starts), max(ends))
        frame = self.load(source, symbol, kind)
        if frame.empty:
            return None
        return CryptoRange(frame["timestamp"].min().to_pydatetime(), frame["timestamp"].max().to_pydatetime())

    def missing_ranges(self, source: str, symbol: str, kind: str, start: datetime, end: datetime) -> list[tuple[datetime, datetime]]:
        start = utc_datetime(start)
        end = utc_datetime(end)
        timestamps = pd.to_datetime(self.load(source, symbol, kind, start, end)["timestamp"], utc=True)
        available = set(timestamps.dt.to_pydatetime())
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
            cursor += timedelta(minutes=5)
        if gap_start is not None:
            missing.append((gap_start, previous))
        return missing
