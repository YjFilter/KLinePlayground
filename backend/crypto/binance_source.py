from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from .models import CryptoBar, CryptoInstrument, FundingEvent
from .source import CryptoSourceError, HttpCryptoSource, from_milliseconds, milliseconds

class BinanceCryptoSource(HttpCryptoSource):
    name = "binance"
    base_url = "https://fapi.binance.com"

    def list_instruments(self) -> list[CryptoInstrument]:
        info = self._get_json(f"{self.base_url}/fapi/v1/exchangeInfo", params={}, endpoint="exchangeInfo")
        tickers = self._get_json(f"{self.base_url}/fapi/v1/ticker/24hr", params={}, endpoint="ticker/24hr")
        if not isinstance(info, dict) or not isinstance(info.get("symbols"), list):
            raise CryptoSourceError("binance schema error for exchangeInfo: missing symbols")
        if not isinstance(tickers, list):
            raise CryptoSourceError("binance schema error for ticker/24hr: expected list")
        turnover = {row.get("symbol"): Decimal(str(row.get("quoteVolume", "0"))) for row in tickers if isinstance(row, dict)}
        result = []
        for row in info["symbols"]:
            filters = {item.get("filterType"): item for item in row.get("filters", [])}
            price = filters.get("PRICE_FILTER", {})
            lot = filters.get("LOT_SIZE", {})
            notional = filters.get("MIN_NOTIONAL", {})
            try:
                result.append(CryptoInstrument(
                    symbol=row["symbol"], source=self.name, base_asset=row["baseAsset"], quote_asset=row["quoteAsset"],
                    contract_type=row.get("contractType", ""), status=row.get("status", ""), listed_at=from_milliseconds(row["onboardDate"]),
                    tick_size=Decimal(str(price["tickSize"])), quantity_step=Decimal(str(lot["stepSize"])),
                    min_quantity=Decimal(str(lot.get("minQty", "0"))), min_notional=Decimal(str(notional.get("notional", notional.get("minNotional", "0")))),
                    quote_turnover_24h=turnover.get(row["symbol"], Decimal("0")),
                ))
            except (KeyError, TypeError, ValueError) as exc:
                raise CryptoSourceError(f"binance schema error for exchangeInfo symbol: {exc}") from exc
        return result

    def fetch_trade_bars(self, symbol: str, start: datetime, end: datetime) -> list[CryptoBar]:
        return self._fetch_bars("/fapi/v1/klines", "klines", symbol, start, end, "trade")

    def fetch_mark_bars(self, symbol: str, start: datetime, end: datetime) -> list[CryptoBar]:
        return self._fetch_bars("/fapi/v1/markPriceKlines", "markPriceKlines", symbol, start, end, "mark")

    def _fetch_bars(self, path, endpoint, symbol, start, end, kind):
        cursor = milliseconds(start)
        end_ms = milliseconds(end)
        rows = []
        for _ in range(self.max_pages):
            payload = self._get_json(f"{self.base_url}{path}", params={"symbol": symbol, "interval": "5m", "startTime": cursor, "endTime": end_ms, "limit": 1500}, endpoint=endpoint)
            if not isinstance(payload, list):
                raise CryptoSourceError(f"binance schema error for {endpoint}: expected list")
            if not payload:
                break
            rows.extend(payload)
            next_cursor = int(payload[-1][0]) + 300000
            if next_cursor <= cursor:
                raise CryptoSourceError(f"binance pagination stalled for {endpoint}")
            cursor = next_cursor
            if len(payload) < 1500 or cursor > end_ms:
                break
        else:
            raise CryptoSourceError(f"binance pagination exceeded {self.max_pages} pages for {endpoint}")
        result = []
        for row in rows:
            try:
                timestamp = from_milliseconds(row[0])
                if timestamp < from_milliseconds(milliseconds(start)) or timestamp > from_milliseconds(end_ms):
                    continue
                result.append(CryptoBar(self.name, symbol, kind, timestamp, Decimal(str(row[1])), Decimal(str(row[2])), Decimal(str(row[3])), Decimal(str(row[4])), Decimal(str(row[5])) if kind == "trade" else None, Decimal(str(row[7])) if kind == "trade" and len(row) > 7 else None))
            except (IndexError, TypeError, ValueError) as exc:
                raise CryptoSourceError(f"binance schema error for {endpoint} row: {exc}") from exc
        return sorted({bar.timestamp: bar for bar in result}.values(), key=lambda bar: bar.timestamp)

    def fetch_funding(self, symbol: str, start: datetime, end: datetime) -> list[FundingEvent]:
        cursor = milliseconds(start)
        end_ms = milliseconds(end)
        events = []
        for _ in range(self.max_pages):
            payload = self._get_json(f"{self.base_url}/fapi/v1/fundingRate", params={"symbol": symbol, "startTime": cursor, "endTime": end_ms, "limit": 1000}, endpoint="fundingRate")
            if not isinstance(payload, list):
                raise CryptoSourceError("binance schema error for fundingRate: expected list")
            if not payload:
                break
            for row in payload:
                events.append(FundingEvent(self.name, symbol, from_milliseconds(row["fundingTime"]), Decimal(str(row["fundingRate"])), Decimal(str(row["markPrice"])) if row.get("markPrice") is not None else None))
            next_cursor = int(payload[-1]["fundingTime"]) + 1
            if next_cursor <= cursor:
                raise CryptoSourceError("binance pagination stalled for fundingRate")
            cursor = next_cursor
            if len(payload) < 1000 or cursor > end_ms:
                break
        else:
            raise CryptoSourceError(f"binance pagination exceeded {self.max_pages} pages for fundingRate")
        return sorted({event.timestamp: event for event in events}.values(), key=lambda event: event.timestamp)
