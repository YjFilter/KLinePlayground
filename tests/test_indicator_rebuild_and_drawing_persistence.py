"""Regression guards for indicator-panel rebuild and A-share live drawing persistence.

Background (both bugs were observed in production use):

1. MACD subchart rendered blank after switching modes (crypto ↔ A-share live watch).
   Root cause: ``initializeChart()`` rebuilt all three Lightweight-Charts instances but
   never cleared the ``currentIndicatorSeries`` / ``bollSeries`` bookkeeping. The next
   ``loadTechnicalIndicator()`` therefore called ``removeSeries()`` on series that
   belonged to the *destroyed* chart, Lightweight Charts threw ``Value is undefined``,
   and the error was swallowed by the ``catch`` in ``loadTechnicalIndicator``. The
   subchart was never redrawn while the legend kept the previous dataset's values.

2. Drawings made on the A-share live-watch chart were lost on every re-entry, because
   ``initializeChart()`` recreates the ``DrawingController`` and drawings only ever
   lived in memory.

These tests assert the *structural* fixes so a revert is caught by the gate.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
JS_PATH = PROJECT_ROOT / "frontend" / "js" / "main_enhanced.js"


def _collapse(source: str) -> str:
    """Collapse all whitespace so assertions survive reformatting."""
    return re.sub(r"\s+", " ", source)


def _extract_function(source: str, name: str) -> str:
    """Best-effort extraction of a top-level function body by brace matching."""
    start = source.find(f"function {name}(")
    if start < 0:
        return ""
    brace = source.find("{", start)
    if brace < 0:
        return ""
    depth = 0
    for index in range(brace, len(source)):
        char = source[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[start:index + 1]
    return source[start:]


class IndicatorPanelRebuildTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.js = JS_PATH.read_text(encoding="utf-8")
        cls.flat = _collapse(cls.js)

    def test_initialize_chart_resets_indicator_series_bookkeeping(self):
        """initializeChart must drop stale series references before rebuilding charts."""
        body = _collapse(_extract_function(self.js, "initializeChart"))
        self.assertIn("function initializeChart(", body)
        self.assertIn("destroyDrawingTools();", body)
        self.assertIn("currentIndicatorSeries = [];", body)
        self.assertIn("bollSeries = {};", body)

    def test_series_bookkeeping_reset_precedes_chart_creation(self):
        """The reset must happen before the new chart objects are created."""
        body = _collapse(_extract_function(self.js, "initializeChart"))
        reset_at = body.find("currentIndicatorSeries = [];")
        candlestick_at = body.find("LightweightCharts.createChart")
        self.assertGreater(reset_at, -1)
        self.assertGreater(candlestick_at, -1)
        self.assertLess(reset_at, candlestick_at)

    def test_clear_technical_indicator_series_is_defensive(self):
        """removeSeries must be guarded so one stale series cannot abort the refresh."""
        body = _collapse(_extract_function(self.js, "clearTechnicalIndicatorSeries"))
        self.assertIn("function clearTechnicalIndicatorSeries(", body)
        self.assertIn("try {", body)
        self.assertIn("removeSeries(series);", body)
        self.assertIn("catch (error)", body)
        # Bookkeeping must still be cleared regardless of removal failures.
        self.assertIn("currentIndicatorSeries = [];", body)
        self.assertIn("bollSeries = {};", body)

    def test_load_technical_indicator_still_clears_first(self):
        """The refresh entry point must clear previous series before recomputing."""
        body = _collapse(_extract_function(self.js, "loadTechnicalIndicator"))
        self.assertIn("clearTechnicalIndicatorSeries();", body)

    def test_apply_crypto_next_delta_refreshes_all_indicators(self):
        """Next bar delta in crypto training must update all active subcharts."""
        body = _collapse(_extract_function(self.js, "applyCryptoNextDelta"))
        self.assertIn("loadTechnicalIndicators()", body)

    def test_remove_subchart_updates_current_indicator_type(self):
        """Removing a subchart must reset currentIndicatorType to avoid stale pointer."""
        body = _collapse(_extract_function(self.js, "removeSubchart"))
        self.assertIn("currentIndicatorType = activeSubcharts.length > 0", body)

    def test_toggle_indicator_visibility_updates_current_indicator_type(self):
        """Toggling an indicator subchart off must update currentIndicatorType."""
        body = _collapse(_extract_function(self.js, "toggleIndicatorVisibility"))
        self.assertIn("currentIndicatorType = activeSubcharts.length > 0", body)

    def test_load_technical_indicators_autoscale_and_series_reuse(self):
        """Subchart updates must ensure rightPriceScale autoScale is applied."""
        body = _collapse(_extract_function(self.js, "loadTechnicalIndicators"))
        self.assertIn("autoScale: true", body)
        self.assertIn("difSeries.setData(", body)
        self.assertIn("histogramSeries.setData(", body)



class AshareLiveDrawingPersistenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.js = JS_PATH.read_text(encoding="utf-8")
        cls.flat = _collapse(cls.js)

    def test_persistence_helpers_exist(self):
        for name in (
            "ashareLiveDrawingsKey",
            "readAshareLiveDrawings",
            "persistAshareLiveDrawings",
            "createAshareLiveDrawingStore",
        ):
            self.assertIn(f"function {name}(", self.flat, f"missing helper: {name}")

    def test_storage_key_is_symbol_scoped(self):
        body = _collapse(_extract_function(self.js, "ashareLiveDrawingsKey"))
        self.assertIn("ASHARE_LIVE_DRAWINGS_PREFIX", body)
        self.assertIn("symbol", body)

    def test_store_restores_snapshot_and_persists_on_commit(self):
        body = _collapse(_extract_function(self.js, "createAshareLiveDrawingStore"))
        self.assertIn("new Store(readAshareLiveDrawings(persistSymbol))", body)
        # Every mutation funnels through _commit; reset is handled separately.
        self.assertIn("_commit", body)
        self.assertIn("persistAshareLiveDrawings(store, persistSymbol);", body)
        self.assertIn("store.reset = () =>", body)

    def test_controller_receives_the_restored_store(self):
        body = _collapse(_extract_function(self.js, "initializeDrawingTools"))
        self.assertIn("createAshareLiveDrawingStore(api, persistSymbol)", body)
        self.assertIn("store: restoredDrawingStore || undefined", body)

    def test_switching_symbol_reloads_its_own_drawings(self):
        body = _collapse(_extract_function(self.js, "switchAshareLiveStock"))
        self.assertIn("await loadAshareLiveData(", body)
        self.assertIn("initializeDrawingTools();", body)

    def test_live_watch_ui_snapshot_is_dropped_when_jumping_into_training(self):
        """Leaving live watch via the training buttons must invalidate the snapshot."""
        body = _collapse(_extract_function(self.js, "startTrainingWithConfig"))
        self.assertIn("stopAshareLivePolling();", body)
        self.assertIn("asharePreLiveUiState = null;", body)


if __name__ == "__main__":
    unittest.main()
