from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

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

def validate_crypto_frame(frame: pd.DataFrame, *, kind: str = "trade") -> ValidationResult:
    issues = []
    required = {"timestamp", "open", "high", "low", "close"}
    if kind == "trade":
        required |= {"volume", "turnover"}
    missing = sorted(required - set(frame.columns))
    if missing:
        issues.append(ValidationIssue("missing_columns", f"missing required columns: {', '.join(missing)}"))
    if "timestamp" not in frame.columns:
        return ValidationResult(issues)
    timestamps = pd.to_datetime(frame["timestamp"], errors="coerce", utc=True)
    if timestamps.isna().any():
        issues.append(ValidationIssue("invalid_timestamp", "timestamps must be parseable UTC values"))
    else:
        originals = frame["timestamp"]
        for original, timestamp in zip(originals, timestamps):
            tz = getattr(original, "tzinfo", None)
            offset = original.utcoffset() if tz is not None and hasattr(original, "utcoffset") else None
            if tz is None or offset != timedelta(0):
                issues.append(ValidationIssue("non_utc_timestamp", "timestamps must be timezone-aware UTC", timestamp.to_pydatetime()))
                break
        misaligned = timestamps[(timestamps.dt.minute % 5 != 0) | (timestamps.dt.second != 0) | (timestamps.dt.microsecond != 0)]
        if not misaligned.empty:
            issues.append(ValidationIssue("misaligned_timestamp", "timestamps must align to five-minute UTC boundaries", misaligned.iloc[0].to_pydatetime()))
        if timestamps.duplicated().any():
            issues.append(ValidationIssue("duplicate_timestamp", "timestamps must be unique"))
        if not timestamps.is_monotonic_increasing:
            issues.append(ValidationIssue("unordered_timestamp", "timestamps must be ordered"))
    numeric_columns = [column for column in ("open", "high", "low", "close", "volume", "turnover") if column in frame.columns]
    numeric = pd.DataFrame(index=frame.index)
    finite = pd.DataFrame(index=frame.index)
    for column in numeric_columns:
        numeric[column] = pd.to_numeric(frame[column], errors="coerce")
        finite[column] = np.isfinite(numeric[column].to_numpy(dtype=float, na_value=np.nan))
    if numeric_columns and not finite.to_numpy(dtype=bool).all():
        issues.append(ValidationIssue("non_finite", "numeric values must be finite"))
    if all(column in frame.columns for column in ("open", "high", "low", "close")):
        ohlc_columns = ["open", "high", "low", "close"]
        all_finite = finite[ohlc_columns].all(axis=1)
        high_low_finite = finite["high"] & finite["low"]
        invalid_high_low = high_low_finite & (numeric["high"] < numeric["low"])
        invalid_bounds = all_finite & (
            (numeric["low"] < 0)
            | (numeric["open"] < numeric["low"])
            | (numeric["open"] > numeric["high"])
            | (numeric["close"] < numeric["low"])
            | (numeric["close"] > numeric["high"])
        )
        if (invalid_high_low | invalid_bounds).any():
            issues.append(ValidationIssue("invalid_ohlc", "OHLC values violate low <= open/close <= high"))
    if "volume" in frame.columns and (finite["volume"] & (numeric["volume"] < 0)).any():
        issues.append(ValidationIssue("negative_volume", "volume must not be negative"))
    return ValidationResult(issues)
