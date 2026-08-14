"""Backend crypto offline data manager.

Provides scanning of local offline data cache status and downloading/synchronizing
historical archives (1m klines, mark price, funding rates) from official Binance archives.
"""

from __future__ import annotations

import io
import os
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import zipfile
import requests
import pandas as pd

from backend.crypto.cache import CryptoMonthlyCache
from backend.crypto.models import FundingEvent
from backend.crypto.validator import validate_crypto_frame

DEFAULT_CACHE_ROOT = Path("data/crypto")

ALL_ARCHIVE_YEARS = [2024, 2025, 2026]


def _get_target_months(year: str | int | None = None) -> list[str]:
    months = []
    years = ALL_ARCHIVE_YEARS if not year or str(year).lower() in ("all", "0", "") else [int(year)]
    for y in years:
        for m in range(1, 13):
            if y == 2026 and m > 8:
                break
            months.append(f"{y}-{m:02d}")
    return months


def scan_crypto_offline_status(cache_root: Path | None = None) -> dict:
    root = Path(cache_root) if cache_root else DEFAULT_CACHE_ROOT
    if not root.exists():
        return {"total_symbols": 0, "total_size_mb": 0.0, "symbols": []}

    symbols_list = []
    total_size_bytes = 0

    for source_dir in sorted(root.iterdir()):
        if not source_dir.is_dir():
            continue
        source = source_dir.name
        for sym_dir in sorted(source_dir.iterdir()):
            if not sym_dir.is_dir():
                continue
            symbol = sym_dir.name

            sym_size = sum(f.stat().st_size for f in sym_dir.rglob("*") if f.is_file())
            total_size_bytes += sym_size

            # Trade 1m months
            trade_dir = sym_dir / "trade" / "1m"
            if not trade_dir.exists():
                trade_dir = sym_dir / "trade"
            trade_months = sorted([f.stem.replace(".csv", "") for f in trade_dir.glob("*.csv.gz")]) if trade_dir.exists() else []

            # Mark 1m months
            mark_dir = sym_dir / "mark" / "1m"
            if not mark_dir.exists():
                mark_dir = sym_dir / "mark"
            mark_months = sorted([f.stem.replace(".csv", "") for f in mark_dir.glob("*.csv.gz")]) if mark_dir.exists() else []

            # Funding months
            funding_dir = sym_dir / "funding"
            funding_months = sorted([f.stem.replace(".csv", "") for f in funding_dir.glob("*.csv.gz")]) if funding_dir.exists() else []

            # Only report if there is actual data or instrument
            has_data = len(trade_months) > 0 or len(mark_months) > 0 or len(funding_months) > 0
            if not has_data and sym_size < 1024:
                continue

            symbols_list.append({
                "source": source,
                "symbol": symbol,
                "size_mb": round(sym_size / (1024 * 1024), 2),
                "trade_months": trade_months,
                "trade_range": f"{trade_months[0]} ~ {trade_months[-1]}" if trade_months else "--",
                "trade_count": len(trade_months),
                "mark_count": len(mark_months),
                "funding_count": len(funding_months),
                "is_complete_2024_now": len(trade_months) >= 32 and len(mark_months) >= 32 and len(funding_months) >= 32,
            })

    # Sort so symbols with most data appear first
    symbols_list.sort(key=lambda s: (s["trade_count"] + s["mark_count"]), reverse=True)

    return {
        "total_symbols": len(symbols_list),
        "total_size_mb": round(total_size_bytes / (1024 * 1024), 2),
        "symbols": symbols_list,
    }


def download_binance_month_trade(symbol: str, month: str, cache: CryptoMonthlyCache) -> tuple[bool, str]:
    target_path = cache._data_path("binance", symbol, "trade", month)
    if target_path.exists():
        return True, "already cached"

    url = f"https://data.binance.vision/data/futures/um/monthly/klines/{symbol}/1m/{symbol}-1m-{month}.zip"
    try:
        r = requests.get(url, timeout=40)
        if r.status_code != 200:
            return False, f"HTTP {r.status_code}"

        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            csv_name = z.namelist()[0]
            with z.open(csv_name) as f:
                df = pd.read_csv(f, header=None)
                if df.iloc[0, 0] == "open_time" or str(df.iloc[0, 0]).isalpha():
                    df = df.iloc[1:].copy()
                cols = ["open_time", "open", "high", "low", "close", "volume", "close_time", "quote_volume"]
                df.columns = cols + list(range(len(df.columns) - len(cols)))

        frame = pd.DataFrame({
            "timestamp": pd.to_datetime(df["open_time"].astype(int), unit="ms", utc=True),
            "open": df["open"],
            "high": df["high"],
            "low": df["low"],
            "close": df["close"],
            "volume": df["volume"],
            "turnover": df["quote_volume"]
        })
        cache.save("binance", symbol, "trade", frame)
        return True, f"saved ({len(frame)} bars)"
    except Exception as e:
        return False, str(e)


def download_binance_month_mark(symbol: str, month: str, cache: CryptoMonthlyCache) -> tuple[bool, str]:
    target_path = cache._data_path("binance", symbol, "mark", month)
    if target_path.exists():
        return True, "already cached"

    url = f"https://data.binance.vision/data/futures/um/monthly/markPriceKlines/{symbol}/1m/{symbol}-1m-{month}.zip"
    try:
        r = requests.get(url, timeout=40)
        if r.status_code != 200:
            return False, f"HTTP {r.status_code}"

        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            csv_name = z.namelist()[0]
            with z.open(csv_name) as f:
                df = pd.read_csv(f, header=None)
                if df.iloc[0, 0] == "open_time" or str(df.iloc[0, 0]).isalpha():
                    df = df.iloc[1:].copy()
                cols = ["open_time", "open", "high", "low", "close"]
                df.columns = cols + list(range(len(df.columns) - len(cols)))

        frame = pd.DataFrame({
            "timestamp": pd.to_datetime(df["open_time"].astype(int), unit="ms", utc=True),
            "open": df["open"],
            "high": df["high"],
            "low": df["low"],
            "close": df["close"],
            "volume": 0,
            "turnover": 0
        })
        cache.save("binance", symbol, "mark", frame)
        return True, f"saved ({len(frame)} bars)"
    except Exception as e:
        return False, str(e)


def download_binance_month_funding(symbol: str, month: str, cache: CryptoMonthlyCache) -> tuple[bool, str]:
    target_path = cache._data_path("binance", symbol, "funding", month)
    if target_path.exists():
        return True, "already cached"

    url = f"https://data.binance.vision/data/futures/um/monthly/fundingRate/{symbol}/{symbol}-fundingRate-{month}.zip"
    try:
        r = requests.get(url, timeout=40)
        if r.status_code != 200:
            return False, f"HTTP {r.status_code}"

        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            csv_name = z.namelist()[0]
            with z.open(csv_name) as f:
                df = pd.read_csv(f)

        time_col = "calc_time" if "calc_time" in df.columns else df.columns[0]
        rate_col = "funding_rate" if "funding_rate" in df.columns else df.columns[2]

        events = []
        for _, row in df.iterrows():
            ts = pd.to_datetime(int(row[time_col]), unit="ms", utc=True).to_pydatetime()
            rate = Decimal(str(row[rate_col]))
            events.append(FundingEvent("binance", symbol, ts, rate))

        start_dt = datetime.strptime(f"{month}-01", "%Y-%m-%d").replace(tzinfo=timezone.utc)
        if int(month.split("-")[1]) == 12:
            end_dt = datetime(int(month.split("-")[0]) + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end_dt = datetime(int(month.split("-")[0]), int(month.split("-")[1]) + 1, 1, tzinfo=timezone.utc)

        cache.save_funding("binance", symbol, events, start_dt, end_dt)
        return True, f"saved ({len(events)} events)"
    except Exception as e:
        return False, str(e)


def sync_crypto_offline_data(
    symbol: str,
    year: str | int | None = None,
    source: str = "binance",
    kinds: tuple[str, ...] = ("trade", "mark", "funding"),
    cache_root: Path | None = None,
    progress_callback=None,
) -> dict:
    symbol = symbol.strip().upper()
    cache = CryptoMonthlyCache(cache_root if cache_root else DEFAULT_CACHE_ROOT)
    months = _get_target_months(year)

    results = {
        "symbol": symbol,
        "source": source,
        "year": str(year) if year else "all",
        "total_tasks": len(months) * len(kinds),
        "downloaded": 0,
        "already_cached": 0,
        "failed": 0,
        "details": [],
    }

    step = 0
    total_steps = len(months) * len(kinds)

    for month in months:
        for kind in kinds:
            step += 1
            if progress_callback:
                progress_callback(step, total_steps, f"正在处理 {symbol} {kind} {month}")

            if kind == "trade":
                success, msg = download_binance_month_trade(symbol, month, cache)
            elif kind == "mark":
                success, msg = download_binance_month_mark(symbol, month, cache)
            elif kind == "funding":
                success, msg = download_binance_month_funding(symbol, month, cache)
            else:
                success, msg = False, f"unknown kind: {kind}"

            if success:
                if "already" in msg:
                    results["already_cached"] += 1
                else:
                    results["downloaded"] += 1
            else:
                results["failed"] += 1

            results["details"].append({
                "kind": kind,
                "month": month,
                "success": success,
                "message": msg,
            })

    return results
