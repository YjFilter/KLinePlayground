from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from urllib.parse import quote

from .models import BASE_INTERVAL_MINUTES, CryptoBar, CryptoInstrument, FundingEvent
from .source import CryptoSourceError, HttpCryptoSource, from_milliseconds, milliseconds

class BybitCryptoSource(HttpCryptoSource):
    name = "bybit"
    base_url = "https://api.bybit.com"
    base_interval = str(BASE_INTERVAL_MINUTES)
    bar_page_limit = 1000
    funding_page_limit = 200

    def _result(self, payload, endpoint):
        if not isinstance(payload, dict) or payload.get("retCode") != 0:
            message = payload.get("retMsg") if isinstance(payload, dict) else "invalid payload"
            raise CryptoSourceError(f"bybit API error for {endpoint}: {message}")
        result = payload.get("result")
        if not isinstance(result, dict):
            raise CryptoSourceError(f"bybit schema error for {endpoint}: missing result")
        return result

    def list_instruments(self) -> list[CryptoInstrument]:
        rows = self._paged_list("/v5/market/instruments-info", "instruments-info", {"category": "linear", "limit": 1000})
        ticker_result = self._result(self._get_json(f"{self.base_url}/v5/market/tickers", params={"category": "linear"}, endpoint="tickers"), "tickers")
        tickers = ticker_result.get("list")
        if not isinstance(tickers, list):
            raise CryptoSourceError("bybit schema error for tickers: missing list")
        turnover = {row.get("symbol"): Decimal(str(row.get("turnover24h", "0"))) for row in tickers if isinstance(row, dict)}
        instruments = []
        for row in rows:
            price = row.get("priceFilter", {})
            lot = row.get("lotSizeFilter", {})
            try:
                instruments.append(CryptoInstrument(
                    symbol=row["symbol"], source=self.name, base_asset=row["baseCoin"], quote_asset=row["quoteCoin"],
                    contract_type=row.get("contractType", ""), status=row.get("status", ""), listed_at=from_milliseconds(row["launchTime"]),
                    tick_size=Decimal(str(price["tickSize"])), quantity_step=Decimal(str(lot["qtyStep"])),
                    min_quantity=Decimal(str(lot.get("minOrderQty", "0"))), min_notional=Decimal(str(lot.get("minNotionalValue", "0"))),
                    quote_turnover_24h=turnover.get(row["symbol"], Decimal("0")),
                ))
            except (KeyError, TypeError, ValueError) as exc:
                raise CryptoSourceError(f"bybit schema error for instruments-info row: {exc}") from exc
        return instruments

    def _paged_list(self, path, endpoint, params):
        cursor = None
        rows = []
        for _ in range(self.max_pages):
            request_params = dict(params)
            if cursor:
                request_params["cursor"] = cursor
            result = self._result(self._get_json(f"{self.base_url}{path}", params=request_params, endpoint=endpoint), endpoint)
            page = result.get("list")
            if not isinstance(page, list):
                raise CryptoSourceError(f"bybit schema error for {endpoint}: missing list")
            rows.extend(page)
            next_cursor = result.get("nextPageCursor") or ""
            if not next_cursor:
                break
            if next_cursor == cursor:
                raise CryptoSourceError(f"bybit pagination stalled for {endpoint}")
            cursor = next_cursor
        else:
            raise CryptoSourceError(f"bybit pagination exceeded {self.max_pages} pages for {endpoint}")
        return rows

    def fetch_trade_bars(self, symbol: str, start: datetime, end: datetime) -> list[CryptoBar]:
        return self._fetch_bars("/v5/market/kline", "kline", symbol, start, end, "trade")

    def fetch_mark_bars(self, symbol: str, start: datetime, end: datetime) -> list[CryptoBar]:
        return self._fetch_bars("/v5/market/mark-price-kline", "mark-price-kline", symbol, start, end, "mark")

    def _fetch_bars(self, path, endpoint, symbol, start, end, kind):
        start_ms = milliseconds(start)
        end_ms = milliseconds(end)
        cursor_end = end_ms
        rows = []
        for _ in range(self.max_pages):
            result = self._result(self._get_json(f"{self.base_url}{path}", params={"category": "linear", "symbol": symbol, "interval": self.base_interval, "start": start_ms, "end": cursor_end, "limit": self.bar_page_limit}, endpoint=endpoint), endpoint)
            page = result.get("list")
            if not isinstance(page, list):
                raise CryptoSourceError(f"bybit schema error for {endpoint}: missing list")
            if not page:
                break
            rows.extend(page)
            oldest = min(int(row[0]) for row in page)
            next_cursor = oldest - 1
            if next_cursor >= cursor_end:
                raise CryptoSourceError(f"bybit pagination stalled for {endpoint}")
            cursor_end = next_cursor
            if len(page) < self.bar_page_limit or cursor_end < start_ms:
                break
        else:
            raise CryptoSourceError(f"bybit pagination exceeded {self.max_pages} pages for {endpoint}")
        bars = []
        for row in rows:
            try:
                timestamp = from_milliseconds(row[0])
                if not start_ms <= int(row[0]) <= end_ms:
                    continue
                bars.append(CryptoBar(self.name, symbol, kind, timestamp, Decimal(str(row[1])), Decimal(str(row[2])), Decimal(str(row[3])), Decimal(str(row[4])), Decimal(str(row[5])) if kind == "trade" and len(row) > 5 else None, Decimal(str(row[6])) if kind == "trade" and len(row) > 6 else None))
            except (IndexError, TypeError, ValueError) as exc:
                raise CryptoSourceError(f"bybit schema error for {endpoint} row: {exc}") from exc
        return sorted({bar.timestamp: bar for bar in bars}.values(), key=lambda bar: bar.timestamp)

    def fetch_funding(self, symbol: str, start: datetime, end: datetime) -> list[FundingEvent]:
        start_ms = milliseconds(start)
        end_ms = milliseconds(end)
        cursor_end = end_ms
        rows = []
        for _ in range(self.max_pages):
            result = self._result(self._get_json(
                f"{self.base_url}/v5/market/funding/history",
                params={
                    "category": "linear",
                    "symbol": symbol,
                    "startTime": start_ms,
                    "endTime": cursor_end,
                    "limit": self.funding_page_limit,
                },
                endpoint="funding/history",
            ), "funding/history")
            page = result.get("list")
            if not isinstance(page, list):
                raise CryptoSourceError("bybit schema error for funding/history: missing list")
            if not page:
                break
            rows.extend(page)
            oldest = min(int(row["fundingRateTimestamp"]) for row in page)
            next_cursor = oldest - 1
            if next_cursor >= cursor_end:
                raise CryptoSourceError("bybit pagination stalled for funding/history")
            cursor_end = next_cursor
            if len(page) < self.funding_page_limit or cursor_end < start_ms:
                break
        else:
            raise CryptoSourceError(f"bybit pagination exceeded {self.max_pages} pages for funding/history")
        events = []
        for row in rows:
            timestamp = from_milliseconds(row["fundingRateTimestamp"])
            if start <= timestamp <= end:
                events.append(FundingEvent(self.name, symbol, timestamp, Decimal(str(row["fundingRate"]))))
        return sorted({event.timestamp: event for event in events}.values(), key=lambda event: event.timestamp)
