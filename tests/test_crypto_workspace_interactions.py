import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
JS_PATH = ROOT / "frontend" / "js" / "main_enhanced.js"


class CryptoWorkspaceInteractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.js = JS_PATH.read_text(encoding="utf-8")

    def function_source(self, name):
        match = re.search(rf"(?:async )?function {name}\([^)]*\)\s*{{", self.js)
        self.assertIsNotNone(match, name)
        start = match.start()
        depth = 0
        for index in range(self.js.find("{", start), len(self.js)):
            if self.js[index] == "{":
                depth += 1
            elif self.js[index] == "}":
                depth -= 1
                if depth == 0:
                    return self.js[start:index + 1]
        self.fail(f"unterminated function {name}")

    def test_crypto_period_switch_is_single_request_without_window_or_account_reload(self):
        source = self.function_source("switchCryptoViewPeriod")
        self.assertIn("/period", source)
        self.assertIn("periodSwitchAbortController", source)
        self.assertIn("request_id", source)
        self.assertIn("range_start", source)
        self.assertIn("range_end", source)
        self.assertIn("chartWindowState.extended_history", source)
        self.assertIn("requestBody.range_start", source)
        self.assertIn("requestBody.range_end", source)
        self.assertIn("chartWindowState.window_start", source)
        self.assertIn("chartWindowState.window_end", source)
        self.assertNotIn("range_start: visibleRange?.from", source)
        self.assertNotIn("range_end: visibleRange?.to", source)
        self.assertIn("applyCryptoPeriodSnapshot", source)
        self.assertIn("applyIntradaySnapshot", self.function_source("applyCryptoPeriodSnapshot"))
        self.assertNotIn("reloadChartWindowForPeriod", source)
        self.assertNotIn("updateAccountInfo", source)

    def test_chart_window_timestamp_parser_accepts_numeric_chart_times(self):
        source = self.function_source("parseChartWindowTimestamp")
        self.assertIn("typeof value === 'number'", source)
        self.assertIn("Number.isFinite", source)

    def test_earlier_chart_window_marks_runtime_as_extended(self):
        start = self.js.index("function applyChartWindow")
        end = self.js.index("\nfunction enqueueChartWindowRequest", start)
        source = self.js[start:end]
        self.assertIn("extended_history", source)
        self.assertIn("options.direction === 'earlier'", source)

    def test_period_loading_indicator_is_delayed_and_rapid_switches_are_versioned(self):
        self.assertIn("const PERIOD_LOADING_DELAY_MS = 150", self.js)
        self.assertIn("let periodSwitchGeneration = 0", self.js)
        self.assertIn("function beginPeriodSwitchFeedback", self.js)
        self.assertIn("function endPeriodSwitchFeedback", self.js)

    def test_crypto_period_snapshot_cache_key_covers_runtime_identity(self):
        source = self.function_source("buildCryptoPeriodSnapshotCacheKey")
        for token in (
            "trainingId",
            "period",
            "window_start",
            "window_end",
            "extended_history",
            "replayTime",
        ):
            self.assertIn(token, source)

    def test_crypto_period_switch_reuses_cached_snapshot_before_fetch(self):
        source = self.function_source("switchCryptoViewPeriod")
        cache_read = source.index("getCryptoPeriodSnapshotCache")
        network_fetch = source.index("fetch(")
        self.assertLess(cache_read, network_fetch)
        self.assertIn("setCryptoPeriodSnapshotCache", source)
        self.assertIn("applyCryptoPeriodSnapshot", source)
        self.assertIn("compact_chart", source)

    def test_crypto_start_prepares_history_before_existing_start_flow(self):
        payload_source = self.function_source("buildCryptoStartPayload")
        self.assertIn("history_years", payload_source)
        self.assertIn("getCryptoHistoryYears", payload_source)

        start_source = self.function_source("startTraining")
        self.assertIn("startCryptoTrainingWithHistoryPreparation", start_source)
        self.assertIn("startTrainingWithConfig", start_source)

        prepare_source = self.function_source("startCryptoTrainingWithHistoryPreparation")
        self.assertIn("prepareCryptoHistory", prepare_source)
        self.assertIn("history_prepare_id", prepare_source)
        self.assertIn("startTrainingWithConfig", prepare_source)

    def test_crypto_history_year_validation_is_integer_between_two_and_five(self):
        source = self.function_source("getCryptoHistoryYears")
        self.assertIn("Number.isInteger", source)
        self.assertIn("historyYears < 2", source)
        self.assertIn("historyYears > 5", source)
        self.assertIn("crypto-history-years", source)

    def test_crypto_history_prepare_supports_poll_cancel_retry_and_actionable_errors(self):
        prepare_source = self.function_source("prepareCryptoHistory")
        self.assertIn("/crypto/history/prepare", prepare_source)
        self.assertIn("pollCryptoHistoryPreparation", prepare_source)
        self.assertIn("showCryptoHistoryPrepareModal", prepare_source)

        poll_source = self.function_source("pollCryptoHistoryPreparation")
        self.assertIn("/crypto/history/prepare/", poll_source)
        self.assertIn("completed_months", poll_source)
        self.assertIn("total_months", poll_source)
        self.assertIn("current_month", poll_source)
        self.assertIn("cancelled", poll_source)
        self.assertIn("failed", poll_source)

        cancel_source = self.function_source("cancelCryptoHistoryPreparation")
        self.assertIn("method: 'DELETE'", cancel_source)
        self.assertIn("/crypto/history/prepare/", cancel_source)
        self.assertIn("AbortController", self.js)
        self.assertIn("retryCryptoHistoryPreparation", self.js)

    def test_fine_period_switch_sends_visible_window_and_consumes_render_metadata(self):
        source = self.function_source("switchCryptoViewPeriod")
        self.assertIn("isFineCryptoPeriod", source)
        self.assertIn("visible_start", source)
        self.assertIn("visible_end", source)

        apply_source = self.function_source("applyCryptoPeriodSnapshot")
        for field in (
            "history_start",
            "history_end",
            "render_start",
            "render_end",
            "has_earlier_render",
        ):
            self.assertIn(field, apply_source)

        cache_source = self.function_source("buildCryptoPeriodSnapshotCacheKey")
        for field in ("history_start", "history_end", "render_start", "render_end"):
            self.assertIn(field, cache_source)

    def test_fine_period_auto_loads_earlier_segment_near_left_edge(self):
        source = self.function_source("maybeLoadEarlierCryptoSegment")
        self.assertIn("300", source)
        self.assertIn("has_earlier_render", source)
        self.assertIn("loadEarlierCryptoSegment", source)

        load_source = self.function_source("loadEarlierCryptoSegment")
        self.assertIn("visible_start", load_source)
        self.assertIn("visible_end", load_source)
        self.assertIn("preserveRange: true", load_source)
        self.assertIn("direction: 'earlier'", load_source)
        self.assertIn("clearCryptoPeriodSnapshotCache", load_source)

        initialize_source = self.function_source("initializeChart")
        self.assertIn("maybeLoadEarlierCryptoSegment", initialize_source)

    def test_compact_period_snapshot_rebuilds_volume_state_from_bars(self):
        source = self.function_source("applyCryptoPeriodSnapshot")
        self.assertIn("snapshot.volume_data.length", source)
        self.assertIn("buildIntradayVolumeData(periodBars)", source)

    def test_crypto_period_snapshot_cache_invalidates_at_runtime_boundaries(self):
        apply_window_start = self.js.index("function applyChartWindow")
        apply_window_end = self.js.index("\nfunction enqueueChartWindowRequest", apply_window_start)
        self.assertIn(
            "clearCryptoPeriodSnapshotCache",
            self.js[apply_window_start:apply_window_end],
            "applyChartWindow",
        )
        for name in (
            "resetChartWindowState",
            "applyCryptoNextDelta",
            "startTrainingWithConfig",
            "endTraining",
            "resetTraining",
        ):
            self.assertIn("clearCryptoPeriodSnapshotCache", self.function_source(name), name)
        self.assertIn(
            "syncCryptoPeriodSnapshotCacheTraining",
            self.function_source("switchCryptoViewPeriod"),
        )

    def test_crypto_workspace_controls_have_event_handlers(self):
        for function in (
            "toggleChartPanel",
            "toggleChartFullscreen",
            "selectCryptoOrderAction",
            "syncCryptoWorkspaceMode",
        ):
            self.assertIn(f"function {function}", self.js)
        self.assertIn("[data-crypto-action]", self.js)
        self.assertIn("toggle-volume-panel-btn", self.js)
        self.assertIn("toggle-indicator-panel-btn", self.js)
        self.assertIn("chart-fullscreen-btn", self.js)
        self.assertIn("crypto-end-training-btn", self.js)
        self.assertIn("crypto-reset-training-btn", self.js)

    def test_drawings_clear_at_training_lifecycle_boundaries(self):
        self.assertIn("function clearSessionDrawings", self.js)
        for name in ("startTrainingWithConfig", "endTraining", "resetTraining"):
            self.assertIn("clearSessionDrawings", self.function_source(name))

    def test_drawing_controller_receives_feedback_and_account_context(self):
        source = self.function_source("initializeDrawingTools")
        self.assertIn("onError", source)
        self.assertIn("onInteractionChange", source)
        self.assertIn("accountSizeProvider", source)
        self.assertIn("setDrawingStatus", self.js)
        self.assertIn("resetAll", self.function_source("clearSessionDrawings"))


    def test_ohlc_neutral_color_does_not_use_black(self):
        """OHLC crosshair display must not hardcode #000000 as the neutral/equal color."""
        crosshair_start = self.js.index("chart.subscribeCrosshairMove")
        crosshair_end = self.js.index("volumeChart.subscribeCrosshairMove", crosshair_start)
        segment = self.js[crosshair_start:crosshair_end]
        self.assertNotIn("'#000000'", segment)
        self.assertNotIn('"#000000"', segment)

    def test_direction_buttons_sync_active_and_aria_pressed(self):
        """selectCryptoOrderAction must toggle .active and set aria-pressed on direction buttons."""
        source = self.function_source("selectCryptoOrderAction")
        self.assertIn("classList.toggle", source)
        self.assertIn("active", source)
        self.assertIn("aria-pressed", source)
        self.assertIn("[data-crypto-action]", source)

    def test_margin_fraction_buttons_sync_active_and_aria_pressed(self):
        """Margin fraction click must toggle .active and sync aria-pressed on fraction buttons."""
        self.assertIn("data-crypto-margin-fraction", self.js)
        self.assertIn("aria-pressed", self.js)
        self.assertIn("crypto-margin-fraction", self.js)
        for token in ("classList.toggle", "active"):
            self.assertIn(token, self.js)

    def test_manual_margin_input_clears_fraction_button_state(self):
        """Editing #crypto-margin by hand must clear .active and aria-pressed on fraction buttons."""
        self.assertIn("crypto-margin", self.js)
        for token in (
            "crypto-margin-fraction",
            "classList.remove",
            "aria-pressed",
        ):
            self.assertIn(token, self.js)

    def test_crypto_console_layout_functions_exist(self):
        """Console resizer module must expose read/persist/apply/toggle/setup functions."""
        for name in (
            "readCryptoConsoleLayout",
            "persistCryptoConsoleLayout",
            "applyCryptoConsoleLayout",
            "toggleCryptoConsoleCollapsed",
            "setupCryptoConsoleResizer",
        ):
            self.assertIn(f"function {name}", self.js, name)

    def test_crypto_console_resizer_uses_local_storage_keys(self):
        """Layout persistence must use the documented localStorage keys."""
        self.assertIn("kline-crypto-console-width-v1", self.js)
        self.assertIn("kline-crypto-console-collapsed-v1", self.js)

    def test_crypto_console_resizer_calls_resize_charts(self):
        """Toggle and drag-end must call resizeCharts() so Lightweight Charts reflow."""
        toggle_src = self.function_source("toggleCryptoConsoleCollapsed")
        self.assertIn("resizeCharts", toggle_src)
        setup_src = self.function_source("setupCryptoConsoleResizer")
        self.assertIn("resizeCharts", setup_src)

    def test_crypto_console_splitter_supports_arrow_keys(self):
        """Keyboard ArrowLeft/ArrowRight must adjust console width by 16px."""
        source = self.function_source("setupCryptoConsoleResizer")
        self.assertIn("ArrowLeft", source)
        self.assertIn("ArrowRight", source)
        self.assertIn("16", source)

    def test_crypto_console_width_uses_css_custom_property(self):
        """Width must be driven by --crypto-console-width, not inline styles."""
        self.assertIn("--crypto-console-width", self.js)

    def test_direction_select_change_resyncs_direction_buttons(self):
        self.assertIn("crypto-order-action", self.js)
        self.assertIn("selectCryptoOrderAction(event.target.value, false)", self.js)

    def test_chart_focus_mode_is_page_level_not_browser_fullscreen(self):
        source = self.function_source("toggleChartFullscreen")
        self.assertIn("chart-focus-mode", source)
        self.assertIn("setChartFocusMode", source)
        self.assertNotIn("requestFullscreen", source)
        self.assertNotIn("document.fullscreenElement", source)

    def test_escape_exits_chart_focus_mode(self):
        source = self.function_source("setupKeyboardShortcuts")
        self.assertIn("Escape", source)
        self.assertIn("setChartFocusMode(false)", source)

    def test_crypto_margin_fraction_uses_fee_aware_maximum(self):
        self.assertIn("function getCryptoMaxOpenMargin", self.js)
        self.assertIn("order_constraints", self.js)
        self.assertIn("max_market_margin", self.js)
        self.assertIn("max_limit_margin", self.js)
        self.assertIn("Math.floor", self.function_source("getCryptoMaxOpenMargin"))
        self.assertIn("getCryptoMaxOpenMargin", self.js[self.js.index("data-crypto-margin-fraction"):])

    def test_fee_rate_editor_converts_percent_to_fraction_and_uses_inline_status(self):
        source = self.function_source("submitCryptoFeeRates")
        self.assertIn("/fee-rates", source)
        self.assertIn("/ 100", source)
        self.assertIn("crypto-fee-status", self.js)
        self.assertIn("submitButton.disabled", source)
        self.assertNotIn("alert(", source)

    def test_crypto_submit_uses_inline_status_and_prevents_duplicates(self):
        source = self.function_source("submitCryptoOrder")
        self.assertIn("crypto-order-status", self.js)
        self.assertIn("setCryptoOrderStatus", source)
        self.assertIn("submitButton.disabled", source)
        self.assertNotIn("alert(", source)
        self.assertIn("payload.message", source)

    def test_crypto_segmented_order_type_updates_hidden_value_and_trigger_payload(self):
        source = self.function_source("setCryptoOrderType")
        self.assertIn("[data-crypto-order-type]", self.js)
        self.assertIn("crypto-order-type", source)
        self.assertIn("aria-pressed", source)
        self.assertIn("crypto-limit-price-group", source)
        submit = self.function_source("submitCryptoOrder")
        self.assertIn("trigger_price", submit)
        self.assertIn("orderType !== 'market'", submit)

    def test_crypto_next_uses_incremental_response_without_followup_requests(self):
        source = self.function_source("nextCryptoBar")
        self.assertIn("cryptoNextInFlight", source)
        self.assertIn("applyCryptoNextDelta", source)
        self.assertNotIn("updateAccountInfo", source)
        self.assertNotIn("updateTradeHistory", source)
        apply_source = self.function_source("applyCryptoNextDelta")
        self.assertIn("candlestickSeries.update", apply_source)
        self.assertIn("volumeSeries.update", apply_source)
        self.assertIn("updateIntradayReplayStatus", apply_source)
        self.assertIn("currentTraining.current_time", apply_source)
        self.assertIn("renderCryptoAccount", apply_source)
        self.assertIn("renderCryptoTradeHistory", apply_source)


if __name__ == "__main__":
    unittest.main()
