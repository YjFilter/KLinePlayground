from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from backend.crypto.binance_source import BinanceCryptoSource
from backend.crypto.bybit_source import BybitCryptoSource
from backend.crypto.source import CryptoSourceError

FIXTURES = Path(__file__).parent / "fixtures" / "crypto"

class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code
        self.text = json.dumps(payload)

    def json(self):
        return self.payload

class FixtureRequester:
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.calls = []

    def get(self, url, *, params=None, timeout=None):
        self.calls.append((url, dict(params or {}), timeout))
        payload = self.payloads.pop(0)
        if isinstance(payload, tuple):
            return FakeResponse(payload[1], payload[0])
        return FakeResponse(payload)

def fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))

class BinanceSourceTests(unittest.TestCase):
    def test_normalizes_instruments_with_exact_decimal_rules(self):
        requester = FixtureRequester([fixture("binance_exchange_info.json"), fixture("binance_ticker.json")])
        instrument = BinanceCryptoSource(requester=requester).list_instruments()[0]
        self.assertEqual(instrument.symbol, "BTCUSDT")
        self.assertEqual(instrument.source, "binance")
        self.assertEqual(instrument.tick_size, Decimal("0.10"))
        self.assertEqual(instrument.quantity_step, Decimal("0.001"))
        self.assertEqual(instrument.min_notional, Decimal("5"))
        self.assertEqual(instrument.quote_turnover_24h, Decimal("123456789.12345678"))
        self.assertEqual(instrument.listed_at.tzinfo, timezone.utc)

    def test_normalizes_trade_mark_and_funding_rows(self):
        requester = FixtureRequester([fixture("binance_trade_bars.json"), fixture("binance_mark_bars.json"), fixture("binance_funding.json")])
        source = BinanceCryptoSource(requester=requester)
        start = datetime(2024, 3, 9, 16, 0, tzinfo=timezone.utc)
        end = datetime(2024, 3, 9, 16, 10, tzinfo=timezone.utc)
        trade = source.fetch_trade_bars("BTCUSDT", start, end)
        mark = source.fetch_mark_bars("BTCUSDT", start, end)
        funding = source.fetch_funding("BTCUSDT", start, end)
        self.assertEqual(trade[0].open, Decimal("60000.10"))
        self.assertEqual(trade[0].volume, Decimal("12.345678"))
        self.assertEqual(mark[0].kind, "mark")
        self.assertIsNone(mark[0].volume)
        self.assertEqual(funding[0].rate, Decimal("0.00010000"))
        self.assertTrue(all(item.timestamp.tzinfo is timezone.utc for item in [*trade, *mark, *funding]))
        self.assertEqual(requester.calls[0][1]["startTime"], 1710000000000)
        self.assertEqual(requester.calls[0][1]["interval"], "1m")

class BybitSourceTests(unittest.TestCase):
    def test_candle_pagination_moves_end_cursor_backward(self):
        requester = FixtureRequester([fixture("bybit_trade_bars.json"), fixture("bybit_trade_bars_page2.json")])
        source = BybitCryptoSource(requester=requester)
        source.bar_page_limit = 2
        bars = source.fetch_trade_bars("ETHUSDT", datetime(2024, 3, 9, 15, 55, tzinfo=timezone.utc), datetime(2024, 3, 9, 16, 10, tzinfo=timezone.utc))
        self.assertEqual(len(bars), 3)
        self.assertLess(requester.calls[1][1]["end"], requester.calls[0][1]["end"])
        self.assertEqual(requester.calls[1][1]["end"], 1709999999999)

    def test_normalizes_instruments_and_descending_candles_to_ascending(self):
        requester = FixtureRequester([fixture("bybit_instruments.json"), fixture("bybit_tickers.json"), fixture("bybit_trade_bars.json")])
        source = BybitCryptoSource(requester=requester)
        instrument = source.list_instruments()[0]
        bars = source.fetch_trade_bars("ETHUSDT", datetime(2024, 3, 9, 16, 0, tzinfo=timezone.utc), datetime(2024, 3, 9, 16, 10, tzinfo=timezone.utc))
        self.assertEqual(instrument.quantity_step, Decimal("0.01"))
        self.assertLess(bars[0].timestamp, bars[1].timestamp)
        self.assertEqual(bars[0].open, Decimal("3000.10"))
        self.assertEqual(requester.calls[-1][1]["start"], 1710000000000)
        self.assertEqual(requester.calls[-1][1]["interval"], "1")

    def test_normalizes_mark_and_funding(self):
        requester = FixtureRequester([fixture("bybit_mark_bars.json"), fixture("bybit_funding.json")])
        source = BybitCryptoSource(requester=requester)
        start = datetime(2024, 3, 9, 16, 0, tzinfo=timezone.utc)
        end = datetime(2024, 3, 9, 16, 10, tzinfo=timezone.utc)
        self.assertEqual(source.fetch_mark_bars("ETHUSDT", start, end)[0].kind, "mark")
        self.assertEqual(source.fetch_funding("ETHUSDT", start, end)[0].rate, Decimal("-0.00005000"))

    def test_funding_pagination_moves_end_time_backward_without_cursor(self):
        def funding_page(*timestamps):
            return {
                "retCode": 0,
                "result": {
                    "list": [
                        {
                            "symbol": "ETHUSDT",
                            "fundingRate": "0.0001",
                            "fundingRateTimestamp": str(int(timestamp.timestamp() * 1000)),
                        }
                        for timestamp in timestamps
                    ]
                },
            }

        first = datetime(2024, 3, 9, 16, 0, tzinfo=timezone.utc)
        second = datetime(2024, 3, 9, 17, 0, tzinfo=timezone.utc)
        third = datetime(2024, 3, 9, 18, 0, tzinfo=timezone.utc)
        requester = FixtureRequester([
            funding_page(third, second),
            funding_page(first),
        ])
        source = BybitCryptoSource(requester=requester)
        source.funding_page_limit = 2
        events = source.fetch_funding(
            "ETHUSDT",
            datetime(2024, 3, 9, 15, 0, tzinfo=timezone.utc),
            third,
        )
        self.assertEqual([event.timestamp for event in events], [first, second, third])
        self.assertNotIn("cursor", requester.calls[1][1])
        self.assertEqual(
            requester.calls[1][1]["endTime"],
            int(second.timestamp() * 1000) - 1,
        )

class SourceFailureTests(unittest.TestCase):
    def test_http_failure_is_actionable(self):
        with self.assertRaisesRegex(CryptoSourceError, "binance.*HTTP 429.*exchangeInfo"):
            BinanceCryptoSource(requester=FixtureRequester([(429, {"msg": "rate limited"})])).list_instruments()

    def test_schema_failure_is_actionable(self):
        with self.assertRaisesRegex(CryptoSourceError, "bybit.*schema.*result"):
            BybitCryptoSource(requester=FixtureRequester([{"retCode": 0}])).list_instruments()

if __name__ == "__main__":
    unittest.main()
