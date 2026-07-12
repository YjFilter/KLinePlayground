from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path

import pandas as pd

from .baostock_source import NORMALIZED_COLUMNS
from .models import IntradayRange, ValidationResult


class IntradayCache:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.data_dir = self.root / "30m"
        self.metadata_dir = self.root / "metadata"

    def _data_path(self, stock_code: str) -> Path:
        return self.data_dir / f"{stock_code}.csv"

    def _metadata_path(self, stock_code: str) -> Path:
        return self.metadata_dir / f"{stock_code}.json"

    def load(self, stock_code: str) -> pd.DataFrame:
        path = self._data_path(stock_code)
        if not path.exists():
            return pd.DataFrame(columns=NORMALIZED_COLUMNS)
        frame = pd.read_csv(path, parse_dates=["datetime"])
        for column in NORMALIZED_COLUMNS[1:]:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        return frame[NORMALIZED_COLUMNS].sort_values("datetime").reset_index(drop=True)

    def merge(self, existing: pd.DataFrame, incoming: pd.DataFrame) -> pd.DataFrame:
        frames = [frame for frame in (existing, incoming) if frame is not None and not frame.empty]
        if not frames:
            return pd.DataFrame(columns=NORMALIZED_COLUMNS)
        merged = pd.concat(frames, ignore_index=True)
        merged["datetime"] = pd.to_datetime(merged["datetime"])
        return merged[NORMALIZED_COLUMNS].drop_duplicates("datetime", keep="last").sort_values("datetime").reset_index(drop=True)

    def save(self, stock_code: str, frame: pd.DataFrame, *, source: str, validation: ValidationResult) -> None:
        normalized = self.merge(pd.DataFrame(columns=NORMALIZED_COLUMNS), frame)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_dir.mkdir(parents=True, exist_ok=True)
        data_path = self._data_path(stock_code)
        metadata_path = self._metadata_path(stock_code)
        data_tmp = data_path.with_suffix(".csv.tmp")
        metadata_tmp = metadata_path.with_suffix(".json.tmp")
        normalized.to_csv(data_tmp, index=False, date_format="%Y-%m-%d %H:%M:%S")
        counts = Counter(issue.code for issue in validation.issues)
        metadata = {
            "stock_code": stock_code,
            "interval": "30m",
            "source": source,
            "range_start": normalized["datetime"].min().isoformat() if not normalized.empty else None,
            "range_end": normalized["datetime"].max().isoformat() if not normalized.empty else None,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "rows": int(len(normalized)),
            "validation": dict(sorted(counts.items())),
        }
        metadata_tmp.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        data_tmp.replace(data_path)
        metadata_tmp.replace(metadata_path)

    def coverage(self, stock_code: str) -> IntradayRange | None:
        frame = self.load(stock_code)
        if frame.empty:
            return None
        return IntradayRange(
            start=frame["datetime"].min().to_pydatetime(),
            end=frame["datetime"].max().to_pydatetime(),
        )

    def metadata(self, stock_code: str) -> dict[str, object] | None:
        path = self._metadata_path(stock_code)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))
