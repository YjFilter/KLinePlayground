import re
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML_PATH = ROOT / "frontend" / "index_enhanced.html"
CSS_PATH = ROOT / "frontend" / "css" / "style_enhanced.css"
JS_PATH = ROOT / "frontend" / "js" / "main_enhanced.js"


class CryptoFrontendStaticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = HTML_PATH.read_text(encoding="utf-8")
        cls.css = CSS_PATH.read_text(encoding="utf-8")
        cls.js = JS_PATH.read_text(encoding="utf-8")

    def test_setup_has_explicit_market_selector(self):
        self.assertIn('data-market-type="a_share"', self.html)
        self.assertIn('data-market-type="crypto_perpetual"', self.html)
        self.assertIn('id="crypto-market-fields"', self.html)
        self.assertIn('id="crypto-symbol-search"', self.html)
        self.assertIn('id="crypto-symbol-results"', self.html)

    def test_render_crypto_account_passes_pending_orders_to_renderer(self):
        start = self.js.index("function renderCryptoAccount")
        end = self.js.index("\nfunction getCryptoCurrentPrice", start)
        function_source = self.js[start:end]
        script = f"""
var cryptoOrderConstraints = {{}};
var currentTraining = {{}};
var cryptoFeeSubmitting = false;
var renderedPendingOrders = null;
function syncCryptoFeeRateInputs() {{}}
function setCryptoFeeStatus() {{}}
function renderCryptoPendingOrders(orders) {{ renderedPendingOrders = orders; }}
function refreshCryptoOrderPreview() {{}}
var document = {{
  getElementById: function() {{ return {{ textContent: '' }}; }}
}};
{function_source}
var expectedOrders = [{{ id: 'order-1' }}];
renderCryptoAccount({{
  account: {{ equity: 10000, available_balance: 9000, mark_price: 100 }},
  position: {{ side: 'flat', quantity: 0 }},
  pending_orders: expectedOrders,
  order_constraints: {{ current_price: 100 }}
}});
if (renderedPendingOrders !== expectedOrders) {{
  throw new Error('renderCryptoAccount did not forward pending_orders');
}}
"""
        result = subprocess.run(
            ["node", "-"],
            input=script,
            text=True,
            capture_output=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_update_current_info_accepts_crypto_progress_without_percent_fields(self):
        start = self.js.index("function updateCurrentInfo")
        end = self.js.index("\n// 涨停/跌停状态检测", start)
        function_source = self.js[start:end]
        script = f"""
var elements = {{}};
var document = {{
  getElementById: function(id) {{
    if (!elements[id]) elements[id] = {{ textContent: '', style: {{}} }};
    return elements[id];
  }}
}};
var latestRenderedKlineData = [];
function getThemePalette() {{ return {{ neutral: '#999', up: '#f00', down: '#0f0' }}; }}
function formatMarketPrice(value) {{ return String(value); }}
function formatCryptoToolbarPrice(value) {{ return String(value); }}
function formatCryptoToolbarVolume(value) {{ return String(value); }}
function updateElementText(id, text, color) {{
  var element = document.getElementById(id);
  element.textContent = text;
  if (color) element.style.color = color;
}}
function checkLimitStatus() {{}}
{function_source}
var bar = {{ time: 1752991200, open: 3600, high: 3700, low: 3550, close: 3642.5, volume: 1000 }};
updateCurrentInfo(bar, {{
  current_time: '2025-07-20 23:55:00',
  next_boundary: '2025-07-21 23:55:00',
  current_bar_complete: true,
  finished: false
}});
updateCurrentInfo(bar, {{ training_progress: 12.34, current_bar_id: 3, training_total_bars: 10 }});
if (elements['training-progress'].textContent !== '进度: 12.3% (3/10)') {{
  throw new Error('legacy progress rendering changed');
}}
"""
        result = subprocess.run(
            ["node", "-"],
            input=script,
            text=True,
            capture_output=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_crypto_periods_and_usdt_settings_exist(self):
        for period in ("5m", "15m", "30m", "1h", "4h", "daily", "weekly"):
            self.assertIn(f'data-crypto-period="{period}"', self.html)
        self.assertIn('id="crypto-leverage"', self.html)
        self.assertIn('id="crypto-initial-capital"', self.html)
        self.assertIn("USDT", self.html)
        self.assertIn("UTC+8", self.html)

    def test_crypto_trading_panel_has_required_controls(self):
        self.assertIn('id="crypto-trading-panel"', self.html)
        for element_id in (
            "crypto-order-action", "crypto-order-type", "crypto-margin",
            "crypto-order-leverage", "crypto-limit-price", "crypto-submit-order", "crypto-position-side",
            "crypto-mark-price", "crypto-liquidation-price", "crypto-margin-ratio",
            "crypto-funding-summary", "crypto-pending-orders",
            "crypto-maker-fee-rate", "crypto-taker-fee-rate", "crypto-save-fee-rates", "crypto-fee-status",
        ):
            self.assertIn(f'id="{element_id}"', self.html)
        for fraction in ("0.25", "0.5", "0.75", "1"):
            self.assertIn(f'data-crypto-margin-fraction="{fraction}"', self.html)

    def test_frontend_branches_by_market_type(self):
        self.assertIn("const CRYPTO_MARKET_TYPE = 'crypto_perpetual'", self.js)
        self.assertIn("const CRYPTO_DATA_MODE = 'crypto_5m'", self.js)
        self.assertIn("function setTrainingMarketType", self.js)
        self.assertIn("async function searchCryptoInstruments", self.js)
        self.assertIn("function normalizeCryptoSymbol", self.js)
        self.assertIn("symbol + 'USDT'", self.js)
        self.assertIn("function buildCryptoStartPayload", self.js)
        self.assertIn("function renderCryptoAccount", self.js)
        self.assertIn("function renderCryptoTradeHistory", self.js)
        self.assertIn("function createCryptoTradeDetailsTable", self.js)
        self.assertIn("report.market_type === CRYPTO_MARKET_TYPE", self.js)
        self.assertIn("item.time || item.timestamp ||", self.js)
        self.assertIn("marker.type === 'L'", self.js)
        self.assertIn("marker.type === 'X'", self.js)
        self.assertIn("crypto-cancel-order", self.js)
        self.assertEqual(self.js.count("\nfunction updateTradeMarkers(markers)"), 1)
        self.assertIn("async function submitCryptoOrder", self.js)
        self.assertIn("async function submitCryptoFeeRates", self.js)
        self.assertIn("/fee-rates", self.js)
        self.assertIn("CRYPTO_PERIODS.includes(currentReportData.period)", self.js)

    def test_crypto_chart_prices_use_usdt_not_yuan(self):
        self.assertIn("function formatMarketPrice", self.js)
        self.assertIn("isCryptoMode() ? formatted + ' USDT'", self.js)
        self.assertIn("formatMarketPrice(barData.close)", self.js)
        self.assertIn("formatMarketPrice(barData.open)", self.js)

    def test_crypto_workspace_has_aicoin_two_column_contract(self):
        self.assertIn("#main-app.crypto-training-active", self.css)
        self.assertIn("grid-template-columns: minmax(0, 1fr) auto var(--crypto-console-width)", self.css)
        self.assertIn("--crypto-console-width: 340px", self.css)
        self.assertIn("grid-column: auto", self.css)
        self.assertIn("#volume-chart.panel-collapsed", self.css)
        self.assertIn("display: none !important", self.css)
        self.assertIn("#main-app.crypto-training-active .workspace-sidebar", self.css)
        self.assertIn("display: none", self.css)
        self.assertIn("--crypto-shell: #0b0e11", self.css)
        self.assertIn("@media (max-width: 980px)", self.css)

    def test_crypto_console_has_direction_and_compact_sections(self):
        for action in ("open_long", "open_short", "close"):
            self.assertIn(f'data-crypto-action="{action}"', self.html)
        self.assertIn('id="crypto-end-training-btn"', self.html)
        self.assertIn('id="crypto-reset-training-btn"', self.html)
        self.assertIn('id="crypto-total-assets"', self.html)
        self.assertIn('id="crypto-trade-history"', self.html)
        self.assertIn('class="control-section" data-a-share-workspace-only', self.html)
        self.assertEqual(self.html.count('id="total-assets"'), 1)
        self.assertEqual(self.html.count('id="trade-history"'), 1)
        for class_name in (
            "account-console-section",
            "position-console-section",
            "order-console-section",
            "record-console-section",
        ):
            self.assertIn(class_name, self.html)

    def test_existing_crypto_control_ids_remain_unique(self):
        for element_id in (
            "crypto-order-action",
            "crypto-order-type",
            "crypto-order-leverage",
            "crypto-margin",
            "crypto-limit-price",
            "crypto-submit-order",
            "crypto-pending-orders",
            "trade-history",
            "total-assets",
            "available-cash",
        ):
            self.assertEqual(self.html.count(f'id="{element_id}"'), 1, element_id)

    def test_crypto_daily_market_metrics_live_in_chart_toolbar(self):
        for element_id in (
            "crypto-open-price", "crypto-high-price", "crypto-low-price",
            "crypto-close-price", "crypto-volume", "crypto-change-percent",
        ):
            self.assertEqual(self.html.count(f'id="{element_id}"'), 1)
            self.assertIn(f"'{element_id}'", self.js)
        self.assertIn('class="crypto-market-strip"', self.html)
        self.assertIn('data-a-share-workspace-only', self.html)
        self.assertIn(
            "#main-app.crypto-training-active .trade-console .info-section[data-a-share-workspace-only]",
            self.css,
        )
        self.assertIn("overflow-x: auto", self.css)

    def test_chart_candle_normalization_preserves_volume_for_ruler_metrics(self):
        intraday_start = self.js.index("function buildIntradayKlineChartData")
        intraday_end = self.js.index("\nfunction buildIntradayVolumeData", intraday_start)
        self.assertIn("volume: Number(bar.volume) || 0", self.js[intraday_start:intraday_end])
        normalize_start = self.js.index("function normalizeChartCandle")
        normalize_end = self.js.index("\nfunction normalizeChartVolume", normalize_start)
        self.assertIn("volume: Number(item.volume) || 0", self.js[normalize_start:normalize_end])


    def test_ohlc_neutral_color_not_hardcoded_black_in_css_or_js(self):
        """Crypto OHLC neutral color must not use #000000 in JS crosshair or CSS."""
        self.assertNotIn("'#000000'", self.js)
        self.assertNotIn('"#000000"', self.js)

    def test_crypto_chart_info_display_uses_theme_text_color(self):
        """The .chart-info-display in crypto mode must inherit the crypto text variable."""
        self.assertIn("chart-info-display", self.css)
        self.assertIn("--crypto-text", self.css)

    def test_crypto_console_vertical_splitter_exists_in_html(self):
        """A vertical splitter element must exist between chart workbench and trade console."""
        self.assertIn('role="separator"', self.html)
        self.assertIn('aria-orientation="vertical"', self.html)
        self.assertIn('id="crypto-console-splitter"', self.html)

    def test_crypto_console_collapse_button_exists_in_html(self):
        """A collapse/expand toggle button must exist inside the trade console."""
        self.assertIn('id="crypto-console-collapse-btn"', self.html)
        self.assertIn('aria-label=', self.html)

    def test_crypto_console_collapse_tab_label_exists(self):
        """When collapsed, a 32px-wide vertical tab labeled '交易台' must exist."""
        self.assertIn('crypto-console-collapsed-tab', self.html)
        self.assertIn("交易台", self.html)

    def test_css_has_32px_collapsed_state(self):
        """CSS must define a 32px width for the collapsed trade console."""
        self.assertIn("32px", self.css)
        self.assertIn("crypto-console-collapsed", self.css)

    def test_css_has_280_to_520_width_constraints(self):
        """Crypto console width must be constrained to 280-520px range."""
        self.assertIn("min-width: 280px", self.css)
        self.assertIn("max-width: 520px", self.css)

    def test_css_crypto_console_width_custom_property(self):
        """Console width must use --crypto-console-width CSS custom property."""
        self.assertIn("--crypto-console-width", self.css)

    def test_css_crypto_splitter_has_resize_cursor_and_focus(self):
        """Vertical splitter must show col-resize cursor and focus-visible outline."""
        self.assertIn("col-resize", self.css)
        self.assertIn("crypto-console-splitter", self.css)

    def test_js_has_console_layout_functions(self):
        """JS must declare the five console layout management functions."""
        for name in (
            "readCryptoConsoleLayout",
            "persistCryptoConsoleLayout",
            "applyCryptoConsoleLayout",
            "toggleCryptoConsoleCollapsed",
            "setupCryptoConsoleResizer",
        ):
            self.assertIn(f"function {name}", self.js, name)

    def test_js_crypto_console_local_storage_keys(self):
        """JS must use the documented localStorage keys for width and collapsed state."""
        self.assertIn("kline-crypto-console-width-v1", self.js)
        self.assertIn("kline-crypto-console-collapsed-v1", self.js)

    def test_direction_buttons_have_active_and_aria_pressed_sync(self):
        """Direction buttons must sync .active class with aria-pressed."""
        source_fn = "selectCryptoOrderAction"
        match = self.js.find(f"function {source_fn}")
        self.assertGreater(match, 0)
        self.assertIn("aria-pressed", self.js[match:match + 800])

    def test_fraction_buttons_have_active_and_aria_pressed_sync(self):
        """Fraction buttons must toggle .active and aria-pressed on click."""
        self.assertIn("data-crypto-margin-fraction", self.html)
        self.assertIn("aria-pressed", self.js)

    def test_manual_margin_clears_fraction_active_state(self):
        """Manual edit of #crypto-margin must clear fraction button .active state."""
        self.assertIn("crypto-margin", self.js)
        self.assertIn("classList.remove", self.js)

    def test_crypto_button_hover_and_active_styles_in_css(self):
        """CSS must define hover, active, and focus-visible states for crypto buttons."""
        self.assertIn("crypto-direction-long", self.css)
        self.assertIn("crypto-direction-short", self.css)
        self.assertIn("crypto-direction-close", self.css)
        self.assertIn(":hover", self.css)
        self.assertIn(":focus-visible", self.css)

    def test_a_share_three_column_layout_selectors_preserved(self):
        """A-share workspace selectors and structure must remain intact."""
        self.assertIn(".training-workspace", self.css)
        self.assertIn(".workspace-sidebar", self.css)
        self.assertIn(".trade-console", self.css)
        self.assertIn('class="left-panel workspace-sidebar"', self.html)
        self.assertIn('class="right-panel trade-console"', self.html)
        self.assertIn("grid-template-columns: minmax(230px", self.css)

    def test_collapsed_console_keeps_right_edge_tab(self):
        self.assertIn("grid-template-columns: minmax(0, 1fr) 32px", self.css)

    def test_narrow_layout_forces_collapsed_console_visible(self):
        self.assertIn("#main-app.crypto-training-active.crypto-console-collapsed .trade-console", self.css)
        self.assertIn("display: block !important", self.css)

    def test_chart_focus_mode_has_visible_exit_control(self):
        self.assertIn('id="chart-focus-exit-btn"', self.html)
        self.assertIn("#main-app.chart-focus-mode", self.css)
        self.assertIn("#chart-focus-exit-btn", self.css)
        self.assertIn("100vw", self.css)
        self.assertIn("100vh", self.css)

    def test_crypto_order_has_inline_live_status(self):
        self.assertIn('id="crypto-order-status"', self.html)
        self.assertIn('aria-live="polite"', self.html)
        self.assertIn(".crypto-order-status", self.css)

    def test_crypto_order_type_uses_segmented_buttons(self):
        self.assertNotIn('<select id="crypto-order-type"', self.html)
        self.assertIn('<input type="hidden" id="crypto-order-type" value="market">', self.html)
        self.assertIn('class="crypto-order-type-switch"', self.html)
        for order_type, label in (("market", "市价"), ("limit", "限价"), ("breakout", "突破")):
            self.assertIn(f'data-crypto-order-type="{order_type}"', self.html)
            self.assertIn(f'data-order-type="{order_type}"', self.html)
            self.assertIn(f'>{label}</button>', self.html)

    def test_crypto_order_type_segment_has_accessible_states(self):
        self.assertIn('role="group" aria-label="订单类型"', self.html)
        self.assertIn('data-crypto-order-type="market"', self.html)
        self.assertIn('class="crypto-order-type-btn active"', self.html)
        self.assertIn('aria-pressed="true"', self.html)
        self.assertGreaterEqual(self.html.count('aria-pressed="false"'), 2)
        for state in (":hover", ":focus-visible", ":active", ".active"):
            self.assertIn(f".crypto-order-type-btn{state}", self.css)

    def test_crypto_order_type_segment_is_single_row_and_equal_width(self):
        self.assertIn(".crypto-order-type-switch", self.css)
        self.assertIn("grid-template-columns: repeat(3, minmax(0, 1fr))", self.css)
        self.assertIn("border-radius:", self.css)

    def test_crypto_limit_and_breakout_share_trigger_price_field(self):
        self.assertIn('id="crypto-limit-price-group"', self.html)
        self.assertIn('id="crypto-limit-price"', self.html)
        self.assertIn('>触发价', self.html)
        self.assertEqual(self.html.count('id="crypto-limit-price-group"'), 1)
        self.assertEqual(self.html.count('id="crypto-limit-price"'), 1)


    def test_crypto_cancel_refreshes_authoritative_orders_on_failure(self):
        cancel_start = self.js.index("async function cancelPendingOrder")
        cancel_end = self.js.index("async function executeBuy", cancel_start)
        cancel_source = self.js[cancel_start:cancel_end]

        self.assertNotIn("if (false)", cancel_source)
        self.assertRegex(
            cancel_source,
            re.compile(
                r"if \(!response\.ok\) \{\s*"
                r"if \(isCryptoMode\(\)\) \{\s*await updateAccountInfo\(\);",
                re.MULTILINE,
            ),
        )


if __name__ == "__main__":
    unittest.main()
