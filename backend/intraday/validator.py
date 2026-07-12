from __future__ import annotations

from datetime import datetime

import pandas as pd

from .models import ValidationIssue, ValidationResult

VALID_30M_TIMES = {
    "10:00", "10:30", "11:00", "11:30",
    "13:30", "14:00", "14:30", "15:00",
}


def validate_30m_frame(frame: pd.DataFrame) -> ValidationResult:
    issues: list[ValidationIssue] = []
    required = {"datetime", "open", "high", "low", "close", "volume", "amount"}
    missing = sorted(required.difference(frame.columns))
    if missing:
        return ValidationResult([ValidationIssue("missing_columns", f"missing columns: {', '.join(missing)}")])
    if frame.empty:
        return ValidationResult([])

    working = frame.copy()
    working["datetime"] = pd.to_datetime(working["datetime"], errors="coerce")
    duplicate_mask = working["datetime"].duplicated(keep=False)
    for timestamp in working.loc[duplicate_mask, "datetime"].dropna().drop_duplicates():
        issues.append(ValidationIssue("duplicate_timestamp", f"duplicate timestamp: {timestamp}", timestamp.to_pydatetime()))

    invalid_ohlc = (
        (working["high"] < working[["open", "close", "low"]].max(axis=1))
        | (working["low"] > working[["open", "close", "high"]].min(axis=1))
        | working[["open", "high", "low", "close"]].isna().any(axis=1)
    )
    for timestamp in working.loc[invalid_ohlc, "datetime"].dropna():
        issues.append(ValidationIssue("invalid_ohlc", "invalid OHLC relationship", timestamp.to_pydatetime()))

    for column, negative_code, invalid_code in (
        ("volume", "negative_volume", "invalid_volume"),
        ("amount", "negative_amount", "invalid_amount"),
    ):
        numeric = pd.to_numeric(working[column], errors="coerce")
        invalid_numeric = numeric.isna()
        for timestamp in working.loc[invalid_numeric, "datetime"].dropna():
            issues.append(ValidationIssue(invalid_code, f"{column} must be numeric", timestamp.to_pydatetime()))
        negative = numeric < 0
        for timestamp in working.loc[negative, "datetime"].dropna():
            issues.append(ValidationIssue(negative_code, f"{column} must be non-negative", timestamp.to_pydatetime()))

    valid_datetimes = working["datetime"].dropna()
    illegal = valid_datetimes[~valid_datetimes.dt.strftime("%H:%M").isin(VALID_30M_TIMES)]
    for timestamp in illegal:
        issues.append(ValidationIssue("illegal_session_time", f"illegal 30m timestamp: {timestamp}", timestamp.to_pydatetime()))

    for trading_date, day_frame in working.dropna(subset=["datetime"]).groupby(working["datetime"].dt.date):
        observed = set(day_frame["datetime"].dt.strftime("%H:%M"))
        if observed != VALID_30M_TIMES:
            missing_times = sorted(VALID_30M_TIMES.difference(observed))
            extra_times = sorted(observed.difference(VALID_30M_TIMES))
            issues.append(
                ValidationIssue(
                    "incomplete_trading_day",
                    f"{trading_date}: missing={missing_times}, extra={extra_times}",
                    datetime.combine(trading_date, datetime.min.time()),
                )
            )

    return ValidationResult(issues)
