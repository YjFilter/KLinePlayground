"""TASK-019 static contracts for historical chart-window frontend wiring."""

from __future__ import annotations

import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
JS_PATH = PROJECT_ROOT / "frontend" / "js" / "main_enhanced.js"


def _load_js() -> str:
    return JS_PATH.read_text(encoding="utf-8")


def _function_body(source: str, signature: str) -> str:
    start = source.find(signature)
    if start < 0:
        return ""
    candidates = [
        source.find("\nfunction ", start + 1),
        source.find("\nasync function ", start + 1),
    ]
    ends = [position for position in candidates if position > start]
    return source[start:min(ends)] if ends else source[start:]


class HistoricalChartWindowFrontendStaticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.js = _load_js()

    def test_active_chart_window_endpoint_is_wired(self):
        self.assertIn("/chart-window", self.js)
        self.assertIn("/training/${currentTraining.id}/chart-window", self.js)

    def test_completed_history_chart_endpoint_is_wired(self):
        self.assertIn("/users/${encodeURIComponent(currentUser)}/history/", self.js)
        self.assertIn("/chart?", self.js)

    def test_merge_chart_window_deduplicates_and_sorts_normalized_times(self):
        body = _function_body(self.js, "function mergeChartWindow")
        self.assertTrue(body, "缺少 mergeChartWindow")
        helper = _function_body(self.js, "function mergeTimedItems")
        self.assertIn("normalizeChartTime", body)
        self.assertIn("new Map", helper)
        self.assertIn(".sort", helper)

    def test_trade_markers_preserve_same_timestamp_entries(self):
        body = _function_body(self.js, "function mergeChartWindow")
        helper = _function_body(self.js, "function normalizeTradeMarkers")
        self.assertTrue(helper, "缺少不去重的交易标记标准化函数")
        self.assertIn("next.trade_markers !== undefined", body)
        self.assertNotIn(
            "mergeTimedItems(base.trade_markers, next.trade_markers",
            body,
        )

    def test_year_loading_functions_exist_and_use_calendar_years(self):
        earlier = _function_body(self.js, "async function loadEarlierYear")
        later = _function_body(self.js, "async function loadLaterYear")
        self.assertTrue(earlier, "缺少 loadEarlierYear")
        self.assertTrue(later, "缺少 loadLaterYear")
        self.assertIn("shiftChartWindowYear", earlier)
        self.assertIn("shiftChartWindowYear", later)

    def test_earlier_loading_preserves_visible_logical_range(self):
        body = _function_body(self.js, "function applyChartWindow")
        self.assertIn("getVisibleLogicalRange", body)
        self.assertIn("setVisibleRangeAll", body)
        self.assertIn("addedEarlierBars", body)

    def test_later_loading_is_completed_read_only_only(self):
        body = _function_body(self.js, "async function loadLaterYear")
        self.assertIn("read_only", body)
        self.assertIn("has_later", body)

    def test_active_mode_hides_later_button(self):
        body = _function_body(self.js, "function updateChartWindowControls")
        self.assertIn("load-later-year-btn", body)
        self.assertIn("classList.toggle('hidden'", body)
        self.assertIn("!chartWindowState.read_only", body)

    def test_window_buttons_are_bound(self):
        setup = _function_body(self.js, "function setupEventListeners")
        self.assertIn("load-earlier-year-btn", setup)
        self.assertIn("loadEarlierYear", setup)
        self.assertIn("load-later-year-btn", setup)
        self.assertIn("loadLaterYear", setup)

    def test_chart_window_requests_are_serialized(self):
        self.assertIn("chartWindowRequestChain", self.js)
        body = _function_body(self.js, "function enqueueChartWindowRequest")
        self.assertIn(".then", body)
        request_body = _function_body(self.js, "async function requestChartWindow")
        self.assertIn("requestGeneration", request_body)
        self.assertIn("chartWindowRequestGeneration", request_body)

    def test_stale_window_requests_cannot_unlock_or_overwrite_new_view(self):
        earlier = _function_body(self.js, "async function loadEarlierYear")
        later = _function_body(self.js, "async function loadLaterYear")
        for body in (earlier, later):
            self.assertIn("requestGeneration === chartWindowRequestGeneration", body)
            self.assertIn("if (requestGeneration === chartWindowRequestGeneration)", body)

    def test_directional_page_loads_preserve_opposite_availability_flag(self):
        body = _function_body(self.js, "function applyChartWindow")
        self.assertIn("options.direction === 'earlier'", body)
        self.assertIn("merged.has_later = previous.has_later", body)
        self.assertIn("options.direction === 'later'", body)
        self.assertIn("merged.has_earlier = previous.has_earlier", body)

    def test_status_covers_loading_success_empty_and_error(self):
        self.assertIn("'loading'", self.js)
        self.assertIn("'success'", self.js)
        self.assertIn("'empty'", self.js)
        self.assertIn("'error'", self.js)

    def test_buttons_disable_for_loading_and_exhausted_ranges(self):
        body = _function_body(self.js, "function updateChartWindowControls")
        self.assertIn("earlierButton.disabled", body)
        self.assertIn("laterButton.disabled", body)
        self.assertIn("!chartWindowState.has_earlier", body)
        self.assertIn("!chartWindowState.has_later", body)

    def test_start_uses_returned_context_without_next(self):
        body = _function_body(self.js, "function startTrainingWithConfig")
        self.assertIn("context_kline_data", body)
        intraday_index = body.find("if (isIntradayMode())")
        legacy_index = body.find("// === legacy_daily", intraday_index)
        intraday_start = body[intraday_index:legacy_index]
        self.assertNotIn("nextBar()", intraday_start)

    def test_history_view_avoids_full_data_and_active_training_dependency(self):
        body = _function_body(self.js, "async function viewFullChart")
        self.assertNotIn("/full_data", body)
        self.assertNotIn("currentTraining = {", body)
        self.assertIn("currentReportData.session_id", body)
        self.assertIn("stopAutoSync()", body)

    def test_read_only_mode_disables_legacy_refresh_controls(self):
        body = _function_body(self.js, "function setTrainingViewOnlyMode")
        self.assertIn("input[name=\"adjustment\"]", body)
        self.assertIn("indicator-select", body)

    def test_history_view_falls_back_to_legacy_date_metadata(self):
        body = _function_body(self.js, "async function viewFullChart")
        self.assertIn(
            "currentReportData.training_start || currentReportData.start_date",
            body,
        )
        self.assertIn(
            "currentReportData.training_end || currentReportData.end_date",
            body,
        )

    def test_history_trade_markers_are_rendered(self):
        body = _function_body(self.js, "function applyChartWindow")
        self.assertIn("trade_markers", body)
        self.assertIn("updateTradeMarkers", body)


if __name__ == "__main__":
    unittest.main()
