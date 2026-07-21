from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from backend.crypto.models import CryptoInstrument
from backend.crypto.universe import CryptoUniverse, CryptoUniverseError

UTC = timezone.utc
NOW = datetime(2024, 7, 1, tzinfo=UTC)

def make(symbol, turnover, *, age=365, status="TRADING", quote="USDT", contract="PERPETUAL"):
    return CryptoInstrument(symbol, "binance", symbol.removesuffix(quote), quote, contract, status, NOW - timedelta(days=age), Decimal("0.1"), Decimal("0.001"), Decimal("0.001"), Decimal("5"), Decimal(str(turnover)))

class Source:
    name = "binance"
    def __init__(self, instruments):
        self.instruments = instruments
        self.calls = 0
    def list_instruments(self):
        self.calls += 1
        return list(self.instruments)

class SequenceRng:
    def __init__(self, indexes):
        self.indexes = iter(indexes)
    def choice(self, values):
        return values[next(self.indexes)]

class CryptoUniverseTests(unittest.TestCase):
    def test_filters_and_ranks_top_fifty_but_searches_all_eligible(self):
        eligible = [make(f"COIN{index:02d}USDT", 1000 - index) for index in range(55)]
        source = Source(eligible + [make("YOUNGUSDT", 9999, age=10), make("INACTIVEUSDT", 9999, status="SETTLING"), make("BTCUSD", 9999, quote="USD")])
        universe = CryptoUniverse([source], now=lambda: NOW)
        top = universe.top_instruments()
        self.assertEqual(len(top), 50)
        self.assertEqual(top[0].symbol, "COIN00USDT")
        self.assertNotIn("COIN54USDT", {item.symbol for item in top})
        self.assertEqual(universe.search("coin54")[0].symbol, "COIN54USDT")
        self.assertEqual(source.calls, 1)

    def test_select_random_uses_injected_rng_and_bounded_retries(self):
        candidates = [make("AAAUSDT", 3), make("BBBUSDT", 2), make("CCCUSDT", 1)]
        checked = []
        requested_start = NOW - timedelta(days=30)
        requested_end = NOW - timedelta(days=1)
        def available(item, start, end):
            checked.append((item.symbol, start, end))
            return item.symbol == "BBBUSDT"
        universe = CryptoUniverse([Source(candidates)], now=lambda: NOW, rng=SequenceRng([0, 1]), availability_checker=available)
        self.assertEqual(universe.select_random(start=requested_start, end=requested_end, max_retries=2).symbol, "BBBUSDT")
        self.assertEqual(checked, [("AAAUSDT", requested_start, requested_end), ("BBBUSDT", requested_start, requested_end)])

    def test_availability_checker_requires_requested_date_range(self):
        universe = CryptoUniverse([Source([make("AAAUSDT", 1)])], now=lambda: NOW, availability_checker=lambda item, start, end: True)
        with self.assertRaisesRegex(ValueError, "start and end"):
            universe.select_random()

    def test_empty_or_exhausted_universe_has_useful_error(self):
        empty = CryptoUniverse([Source([make("NEWUSDT", 1, age=1)])], now=lambda: NOW)
        with self.assertRaisesRegex(CryptoUniverseError, "no active USDT perpetual.*180 days"):
            empty.select_random()
        exhausted = CryptoUniverse([Source([make("AAAUSDT", 1)])], now=lambda: NOW, rng=SequenceRng([0, 0]), availability_checker=lambda item, start, end: False)
        with self.assertRaisesRegex(CryptoUniverseError, "after 2 attempts"):
            exhausted.select_random(start=NOW - timedelta(days=10), end=NOW, max_retries=2)

    def test_eligible_deduplicates_same_source_symbol_pairs(self):
        dup1 = CryptoInstrument("BTCUSDT", "binance", "BTC", "USDT", "PERPETUAL", "TRADING", NOW - timedelta(days=400), Decimal("0.1"), Decimal("0.001"), Decimal("0.001"), Decimal("5"), Decimal("200"))
        dup2 = CryptoInstrument("BTCUSDT", "binance", "BTC", "USDT", "PERPETUAL", "TRADING", NOW - timedelta(days=400), Decimal("0.1"), Decimal("0.001"), Decimal("0.001"), Decimal("5"), Decimal("100"))
        source = Source([dup1, dup2])
        universe = CryptoUniverse([source], now=lambda: NOW)
        result = universe.eligible_instruments()
        symbols = [item.symbol for item in result]
        self.assertEqual(symbols.count("BTCUSDT"), 1)
        self.assertEqual(len(result), 1)

    def test_search_deduplicates_same_symbol_across_sources(self):
        binance_btc = CryptoInstrument("BTCUSDT", "binance", "BTC", "USDT", "PERPETUAL", "TRADING", NOW - timedelta(days=400), Decimal("0.1"), Decimal("0.001"), Decimal("0.001"), Decimal("5"), Decimal("500"))
        bybit_btc = CryptoInstrument("BTCUSDT", "bybit", "BTC", "USDT", "PERPETUAL", "TRADING", NOW - timedelta(days=400), Decimal("0.1"), Decimal("0.001"), Decimal("0.001"), Decimal("5"), Decimal("300"))
        eth = CryptoInstrument("ETHUSDT", "binance", "ETH", "USDT", "PERPETUAL", "TRADING", NOW - timedelta(days=400), Decimal("0.01"), Decimal("0.01"), Decimal("0.01"), Decimal("5"), Decimal("100"))
        source = Source([binance_btc, bybit_btc, eth])
        universe = CryptoUniverse([source], now=lambda: NOW)
        result = universe.search("BTC")
        btc_results = [item for item in result if item.symbol == "BTCUSDT"]
        self.assertEqual(len(btc_results), 1)
        self.assertEqual(btc_results[0].source, "binance")

    def test_duplicate_symbol_keeps_highest_turnover_record(self):
        lower = CryptoInstrument("BTCUSDT", "bybit", "BTC", "USDT", "PERPETUAL", "TRADING", NOW - timedelta(days=400), Decimal("0.1"), Decimal("0.001"), Decimal("0.001"), Decimal("5"), Decimal("300"))
        higher = CryptoInstrument("BTCUSDT", "binance", "BTC", "USDT", "PERPETUAL", "TRADING", NOW - timedelta(days=400), Decimal("0.1"), Decimal("0.001"), Decimal("0.001"), Decimal("5"), Decimal("500"))
        universe = CryptoUniverse([Source([lower, higher])], now=lambda: NOW)

        result = universe.search("BTC")

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].source, "binance")
        self.assertEqual(result[0].quote_turnover_24h, Decimal("500"))

    def test_search_uses_source_specific_search_without_loading_full_snapshot(self):
        btc = make("BTCUSDT", 500)

        class SearchSource:
            name = "offline-cache"

            def search_instruments(self, query):
                self.query = query
                return [btc]

            def list_instruments(self):
                raise AssertionError("full snapshot must not load for a targeted search")

        source = SearchSource()
        universe = CryptoUniverse([source], now=lambda: NOW)

        result = universe.search("BTC")

        self.assertEqual([item.symbol for item in result], ["BTCUSDT"])
        self.assertEqual(source.query, "BTC")

    def test_search_returns_multiple_distinct_symbols(self):
        instruments = [
            make("BTCUSDT", 500),
            make("ETHUSDT", 300),
            make("SOLUSDT", 100),
        ]
        source = Source(instruments)
        universe = CryptoUniverse([source], now=lambda: NOW)
        result = universe.search("")
        self.assertEqual([item.symbol for item in result], ["BTCUSDT", "ETHUSDT", "SOLUSDT"])

if __name__ == "__main__":
    unittest.main()
