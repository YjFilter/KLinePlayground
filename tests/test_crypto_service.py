from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from backend.crypto.cache import CryptoMonthlyCache
from backend.crypto.models import CryptoBar, CryptoInstrument, FundingEvent
from backend.crypto.service import CryptoDataService, CryptoDataUnavailable

UTC = timezone.utc
START = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
END = datetime(2024, 1, 1, 0, 10, tzinfo=UTC)
MONTH_START = datetime(2024, 1, 31, 23, 59, tzinfo=UTC)
MONTH_END = datetime(2024, 2, 1, 0, 10, tzinfo=UTC)

def instrument(source):
    return CryptoInstrument("BTCUSDT", source, "BTC", "USDT", "PERPETUAL", "TRADING", datetime(2020, 1, 1, tzinfo=UTC), Decimal("0.1"), Decimal("0.001"), Decimal("0.001"), Decimal("5"), Decimal("100"))

def bars(source, kind, start=START, end=END):
    result = []
    cursor = start
    while cursor <= end:
        result.append(CryptoBar(source, "BTCUSDT", kind, cursor, Decimal("10"), Decimal("12"), Decimal("9"), Decimal("11"), Decimal("1") if kind == "trade" else None, Decimal("11") if kind == "trade" else None))
        cursor += timedelta(minutes=1)
    return result

class FakeSource:
    def __init__(self, name, *, fail=False, trade=None, mark=None, funding=None):
        self.name = name
        self.fail = fail
        self.trade = bars(name, "trade") if trade is None else trade
        self.mark = bars(name, "mark") if mark is None else mark
        self.funding = [] if funding is None else funding
        self.calls = []

    def list_instruments(self):
        self.calls.append("instruments")
        if self.fail:
            raise RuntimeError(f"{self.name} unavailable")
        return [instrument(self.name)]

    def fetch_trade_bars(self, symbol, start, end):
        self.calls.append(("trade", start, end))
        if self.fail:
            raise RuntimeError(f"{self.name} unavailable")
        return [bar for bar in self.trade if start <= bar.timestamp <= end]

    def fetch_mark_bars(self, symbol, start, end):
        self.calls.append(("mark", start, end))
        if self.fail:
            raise RuntimeError(f"{self.name} unavailable")
        return [bar for bar in self.mark if start <= bar.timestamp <= end]

    def fetch_funding(self, symbol, start, end):
        self.calls.append(("funding", start, end))
        if self.fail:
            raise RuntimeError(f"{self.name} unavailable")
        return self.funding

class CryptoDataServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.cache = CryptoMonthlyCache(Path(self.temp.name))

    def tearDown(self):
        self.temp.cleanup()

    def test_prefers_binance_and_returns_source_pinned_aligned_bundle(self):
        funding = FundingEvent("binance", "BTCUSDT", START, Decimal("0.001"))
        primary = FakeSource("binance", funding=[funding, funding])
        fallback = FakeSource("bybit")
        bundle = CryptoDataService([primary, fallback], self.cache).get_bundle("BTCUSDT", START, END)
        self.assertEqual(bundle.source, "binance")
        self.assertEqual(list(bundle.trade_bars["timestamp"]), list(bundle.mark_bars["timestamp"]))
        self.assertEqual(len(bundle.funding), 1)
        self.assertFalse(fallback.calls)

    def test_falls_back_wholly_to_bybit_without_mixing_ranges(self):
        primary = FakeSource("binance", fail=True)
        fallback = FakeSource("bybit")
        bundle = CryptoDataService([primary, fallback], self.cache).get_bundle("BTCUSDT", START, END)
        self.assertEqual(bundle.source, "bybit")
        self.assertTrue(all(value == "bybit" for value in bundle.trade_bars["source"]))
        self.assertTrue(all(value == "bybit" for value in bundle.mark_bars["source"]))

    def test_complete_cache_avoids_bar_network_calls(self):
        source = FakeSource("binance")
        service = CryptoDataService([source], self.cache)
        service.get_bundle("BTCUSDT", START, END)
        source.calls.clear()
        source.fail = True
        bundle = service.get_bundle("BTCUSDT", START, END)
        self.assertEqual(bundle.source, "binance")
        self.assertFalse(any(isinstance(call, tuple) and call[0] in {"trade", "mark"} for call in source.calls))

    def test_chart_bars_load_trade_only_and_reuse_offline_cache(self):
        source = FakeSource("binance")
        service = CryptoDataService([source], self.cache)

        source_name, first = service.get_chart_bars("BTCUSDT", START, END, source="binance")

        self.assertEqual(source_name, "binance")
        self.assertEqual(len(first), 11)
        self.assertEqual(source.calls, [("trade", START, END)])

        source.calls.clear()
        source.fail = True
        cached_source, cached = service.get_chart_bars("BTCUSDT", START, END, source="binance")

        self.assertEqual(cached_source, "binance")
        self.assertEqual(len(cached), 11)
        self.assertEqual(source.calls, [])

    def test_prepare_chart_bars_splits_requests_at_natural_month_boundaries(self):
        source = FakeSource(
            "binance",
            trade=bars("binance", "trade", MONTH_START, MONTH_END),
        )

        source_name, frame = CryptoDataService([source], self.cache).prepare_chart_bars(
            "btcusdt",
            MONTH_START,
            MONTH_END,
            source="binance",
        )

        self.assertEqual(source_name, "binance")
        self.assertEqual(
            source.calls,
            [
                ("trade", MONTH_START, MONTH_START),
                ("trade", datetime(2024, 2, 1, tzinfo=UTC), MONTH_END),
            ],
        )
        self.assertEqual(list(frame["timestamp"]), [bar.timestamp for bar in source.trade])
        self.assertEqual(frame["timestamp"].is_unique, True)

    def test_prepare_chart_bars_reuses_cached_month_chunks_without_network(self):
        source = FakeSource(
            "binance",
            trade=bars("binance", "trade", MONTH_START, MONTH_END),
        )
        service = CryptoDataService([source], self.cache)
        service.get_chart_bars("BTCUSDT", MONTH_START, MONTH_START, source="binance")
        service.get_chart_bars(
            "BTCUSDT",
            datetime(2024, 2, 1, tzinfo=UTC),
            MONTH_END,
            source="binance",
        )
        source.calls.clear()
        source.fail = True

        source_name, frame = service.prepare_chart_bars(
            "BTCUSDT",
            MONTH_START,
            MONTH_END,
            source="binance",
        )

        self.assertEqual(source_name, "binance")
        self.assertEqual(len(frame), 12)
        self.assertEqual(source.calls, [])

    def test_prepare_chart_bars_reports_stable_progress_after_each_chunk(self):
        source = FakeSource(
            "binance",
            trade=bars("binance", "trade", MONTH_START, MONTH_END),
        )
        updates = []

        CryptoDataService([source], self.cache).prepare_chart_bars(
            "btcusdt",
            MONTH_START,
            MONTH_END,
            source="binance",
            progress_callback=updates.append,
        )

        self.assertEqual(
            updates,
            [
                {
                    "completed_chunks": 0,
                    "total_chunks": 2,
                    "current_start": MONTH_START,
                    "current_end": MONTH_START,
                    "source": "binance",
                    "symbol": "BTCUSDT",
                },
                {
                    "completed_chunks": 1,
                    "total_chunks": 2,
                    "current_start": MONTH_START,
                    "current_end": MONTH_START,
                    "source": "binance",
                    "symbol": "BTCUSDT",
                },
                {
                    "completed_chunks": 1,
                    "total_chunks": 2,
                    "current_start": datetime(2024, 2, 1, tzinfo=UTC),
                    "current_end": MONTH_END,
                    "source": "binance",
                    "symbol": "BTCUSDT",
                },
                {
                    "completed_chunks": 2,
                    "total_chunks": 2,
                    "current_start": datetime(2024, 2, 1, tzinfo=UTC),
                    "current_end": MONTH_END,
                    "source": "binance",
                    "symbol": "BTCUSDT",
                },
            ],
        )

    def test_prepare_chart_bars_cancels_before_starting_the_next_chunk(self):
        source = FakeSource(
            "binance",
            trade=bars("binance", "trade", MONTH_START, MONTH_END),
        )
        checks = []

        def cancel_check():
            checks.append(True)
            return len(checks) > 1

        with self.assertRaisesRegex(RuntimeError, "cancelled.*BTCUSDT.*2 of 2") as context:
            CryptoDataService([source], self.cache).prepare_chart_bars(
                "BTCUSDT",
                MONTH_START,
                MONTH_END,
                source="binance",
                cancel_check=cancel_check,
            )

        self.assertEqual(type(context.exception).__name__, "CryptoChartPreparationCancelled")
        self.assertEqual(source.calls, [("trade", MONTH_START, MONTH_START)])

    def test_prepare_chart_bars_pins_the_requested_source(self):
        primary = FakeSource(
            "binance",
            trade=bars("binance", "trade", MONTH_START, MONTH_END),
        )
        requested = FakeSource(
            "bybit",
            trade=bars("bybit", "trade", MONTH_START, MONTH_END),
        )

        source_name, frame = CryptoDataService([primary, requested], self.cache).prepare_chart_bars(
            "BTCUSDT",
            MONTH_START,
            MONTH_END,
            source="bybit",
        )

        self.assertEqual(source_name, "bybit")
        self.assertEqual(primary.calls, [])
        self.assertEqual(
            requested.calls,
            [
                ("trade", MONTH_START, MONTH_START),
                ("trade", datetime(2024, 2, 1, tzinfo=UTC), MONTH_END),
            ],
        )
        self.assertEqual(set(frame["source"]), {"bybit"})

    def test_prepare_chart_bars_rejects_an_inverted_range_before_fetching(self):
        source = FakeSource("binance")

        with self.assertRaisesRegex(ValueError, "start must not be after end"):
            CryptoDataService([source], self.cache).prepare_chart_bars(
                "BTCUSDT",
                END,
                START,
                source="binance",
            )

        self.assertEqual(source.calls, [])

    def test_prepare_chart_bars_rejects_unaligned_one_minute_boundaries(self):
        source = FakeSource("binance")

        with self.assertRaisesRegex(ValueError, "1-minute boundaries"):
            CryptoDataService([source], self.cache).prepare_chart_bars(
                "BTCUSDT",
                START + timedelta(seconds=30),
                END,
                source="binance",
            )

        self.assertEqual(source.calls, [])

    def test_complete_fallback_cache_is_used_before_primary_network(self):
        unavailable_primary = FakeSource("binance", fail=True)
        fallback = FakeSource("bybit")
        CryptoDataService([unavailable_primary, fallback], self.cache).get_bundle("BTCUSDT", START, END)

        primary = FakeSource("binance")
        cached_fallback = FakeSource("bybit", fail=True)
        bundle = CryptoDataService(
            [primary, cached_fallback], CryptoMonthlyCache(Path(self.temp.name))
        ).get_bundle("BTCUSDT", START, END)

        self.assertEqual(bundle.source, "bybit")
        self.assertEqual(primary.calls, [])
        self.assertEqual(cached_fallback.calls, [])

    def test_new_service_uses_persisted_instrument_funding_and_candles_offline(self):
        funding = FundingEvent("binance", "BTCUSDT", START, Decimal("0.001"), Decimal("10"))
        online = FakeSource("binance", funding=[funding])
        CryptoDataService([online], self.cache).get_bundle("BTCUSDT", START, END)
        offline = FakeSource("binance", fail=True)
        restarted = CryptoDataService([offline], CryptoMonthlyCache(Path(self.temp.name)))
        bundle = restarted.get_bundle("BTCUSDT", START, END)
        self.assertEqual(bundle.instrument, instrument("binance"))
        self.assertEqual(bundle.funding, (funding,))
        self.assertEqual(offline.calls, [])

    def test_rejects_partial_trade_or_mark_coverage(self):
        partial_mark = bars("binance", "mark", START, START + timedelta(minutes=1))
        source = FakeSource("binance", mark=partial_mark)
        with self.assertRaisesRegex(CryptoDataUnavailable, "complete aligned trade/mark coverage"):
            CryptoDataService([source], self.cache).get_bundle("BTCUSDT", START, END)

if __name__ == "__main__":
    unittest.main()
