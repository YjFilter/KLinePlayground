from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.intraday.baostock_source import BaoStockSource, IntradaySourceError
from backend.intraday.cache import IntradayCache
from backend.intraday.validator import validate_30m_frame


def subtract_years(value: datetime, years: int) -> datetime:
    try:
        return value.replace(year=value.year - years)
    except ValueError:
        return value.replace(year=value.year - years, day=28)


def verify_stock(
    source: BaoStockSource, stock_code: str, start: datetime, end: datetime, years: int
) -> tuple[dict[str, object], object]:
    frame = source.fetch_30m(stock_code, start, end)
    validation = validate_30m_frame(frame)
    issue_counts = Counter(issue.code for issue in validation.issues)
    first = None if frame.empty else frame["datetime"].min()
    last = None if frame.empty else frame["datetime"].max()
    trading_days = 0 if frame.empty else int(frame["datetime"].dt.date.nunique())
    coverage_days = 0 if first is None or last is None else int((last - first).days)
    summary = {
        "stock_code": stock_code,
        "rows": int(len(frame)),
        "first": None if first is None else first.isoformat(),
        "last": None if last is None else last.isoformat(),
        "trading_days": trading_days,
        "coverage_days": coverage_days,
        "issues": dict(sorted(issue_counts.items())),
    }
    minimum_days = years_to_minimum_days(years)
    if frame.empty or not validation.is_valid or coverage_days < minimum_days:
        summary["valid"] = False
    else:
        summary["valid"] = True
    return summary, frame


def years_to_minimum_days(years: int) -> int:
    return years * 365 - 21


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify live BaoStock 30-minute history.")
    parser.add_argument("stock_codes", nargs="+")
    parser.add_argument("--years", type=int, default=5)
    parser.add_argument("--save-cache", action="store_true")
    parser.add_argument("--cache-root", type=Path, default=Path("data/intraday"))
    args = parser.parse_args(argv)
    end = datetime.now().replace(hour=23, minute=59, second=59, microsecond=0) - timedelta(days=1)
    start = subtract_years(end, args.years)
    source = BaoStockSource()
    cache = IntradayCache(args.cache_root)
    exit_code = 0
    for stock_code in args.stock_codes:
        try:
            summary, frame = verify_stock(source, stock_code, start, end, args.years)
            print(json.dumps(summary, ensure_ascii=False))
            if not summary["valid"]:
                exit_code = 1
                continue
            if args.save_cache:
                validation = validate_30m_frame(frame)
                cache.save(stock_code, frame, source="baostock", validation=validation)
        except Exception as exc:
            print(json.dumps({"stock_code": stock_code, "valid": False, "error": str(exc)}, ensure_ascii=False))
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
