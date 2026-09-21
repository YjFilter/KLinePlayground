"""Static verification for A-share live market viewing and trading console frontend assets.

Ensures that:
1. The right-panel trade-console contains dedicated A-share paper-trading markup tagged with data-ashare-live-only.
2. CSS defines dark AICoin aesthetics for A-share live mode with grid workspace, buy/sell buttons, and strict isolation.
3. JavaScript contains core trading, preview, T+1 validation, and account management functions.
"""
from __future__ import annotations

import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HTML_PATH = PROJECT_ROOT / "frontend" / "index_enhanced.html"
CSS_PATH = PROJECT_ROOT / "frontend" / "css" / "style_enhanced.css"
JS_PATH = PROJECT_ROOT / "frontend" / "js" / "main_enhanced.js"


class AshareLiveFrontendStaticTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = HTML_PATH.read_text(encoding="utf-8")
        cls.css = CSS_PATH.read_text(encoding="utf-8")
        cls.js = JS_PATH.read_text(encoding="utf-8")

    def test_ashare_live_sections_exist_in_html(self):
        """Dedicated A-share live trading components must exist with data-ashare-live-only attribute."""
        self.assertIn('data-ashare-live-only', self.html)
        self.assertIn('id="ashare-live-account-section"', self.html)
        self.assertIn('id="ashare-live-position-section"', self.html)
        self.assertIn('id="ashare-live-order-section"', self.html)
        self.assertIn('id="ashare-live-history-section"', self.html)

    def test_ashare_live_account_cards_exist(self):
        """Account cards for total assets, available cash, position value, and floating PnL must exist."""
        self.assertIn('id="ashare-live-total-assets"', self.html)
        self.assertIn('id="ashare-live-available-cash"', self.html)
        self.assertIn('id="ashare-live-position-value"', self.html)
        self.assertIn('id="ashare-live-floating-pnl"', self.html)

    def test_ashare_live_trading_controls_exist(self):
        """Buy/sell tabs, lot inputs, fraction buttons, and action buttons must exist."""
        self.assertIn('id="ashare-tab-buy"', self.html)
        self.assertIn('id="ashare-tab-sell"', self.html)
        self.assertIn('id="ashare-buy-lots"', self.html)
        self.assertIn('id="ashare-sell-lots"', self.html)
        self.assertIn('id="ashare-submit-buy"', self.html)
        self.assertIn('id="ashare-submit-sell"', self.html)
        self.assertIn('data-ashare-fraction="0.25"', self.html)
        self.assertIn('data-ashare-fraction="0.5"', self.html)
        self.assertIn('data-ashare-fraction="0.75"', self.html)
        self.assertIn('data-ashare-fraction="1"', self.html)

    def test_ashare_live_css_grid_and_isolation(self):
        """CSS must define 3-column workspace grid and mutual isolation for A-share live mode."""
        self.assertIn('#main-app.ashare-live-active .training-workspace', self.css)
        self.assertIn('#main-app:not(.ashare-live-active) [data-ashare-live-only]', self.css)
        self.assertIn('#main-app.ashare-live-active .trade-console', self.css)
        self.assertIn('.ashare-direction-buy', self.css)
        self.assertIn('.ashare-direction-sell', self.css)
        self.assertIn('.ashare-pos-frozen-tag', self.css)

    def test_ashare_live_js_functions_exist(self):
        """JS must define essential functions for rendering, ordering, preview, and T+1 handling."""
        for fn in (
            "function getAshareLiveAccount",
            "function saveAshareLiveAccount",
            "function renderAshareLiveAccount",
            "function updateAshareOrderPreview",
            "function selectAshareOrderAction",
            "function applyAshareFraction",
            "function executeAshareLiveBuy",
            "function executeAshareLiveSell",
            "function clearAshareTradeHistory",
            "function unfreezeAshareT1Holdings",
            "function resetAshareLiveAccount",
        ):
            self.assertIn(fn, self.js, f"Missing function: {fn}")

    def test_ashare_watchlist_html_components(self):
        """Watchlist panel, tabs, sort headers, and collapse/expand controls must exist in HTML."""
        self.assertIn('id="ashare-live-watchlist-panel"', self.html)
        self.assertIn('class="ashare-wl-tabs"', self.html)
        self.assertIn('data-wl-tab="custom"', self.html)
        self.assertIn('data-wl-tab="holding"', self.html)
        self.assertIn('data-wl-tab="index"', self.html)
        self.assertIn('id="ashare-wl-collapse-btn"', self.html)
        self.assertIn('id="ashare-wl-expand-btn"', self.html)
        self.assertIn('id="ashare-wl-sort-price"', self.html)
        self.assertIn('id="ashare-wl-sort-change"', self.html)
        self.assertIn('id="ashare-watchlist-items"', self.html)
        self.assertIn('id="ashare-wl-add-btn"', self.html)

    def test_ashare_watchlist_css_rules(self):
        """Watchlist layout, item rows, pills, and collapsed states must exist in CSS."""
        self.assertIn('.ashare-live-watchlist-panel', self.css)
        self.assertIn('.ashare-wl-topbar', self.css)
        self.assertIn('.ashare-wl-tabs', self.css)
        self.assertIn('.ashare-wl-tab.active', self.css)
        self.assertIn('.ashare-wl-item', self.css)
        self.assertIn('.ashare-wl-pill', self.css)
        self.assertIn('.ashare-wl-remove-btn', self.css)
        self.assertIn('#main-app.ashare-live-active.ashare-watchlist-collapsed', self.css)

    def test_ashare_watchlist_js_functions(self):
        """Watchlist JS functions must be defined in main_enhanced.js."""
        for fn in (
            "function getAshareWatchlist",
            "function saveAshareWatchlist",
            "function renderAshareWatchlist",
            "function fetchAshareWatchlistQuotes",
            "function addStockToAshareWatchlist",
            "function removeStockFromAshareWatchlist",
            "function collapseAshareWatchlist",
            "function setAshareWatchlistTab",
            "function toggleAshareWatchlistSort",
            "function initAshareSearchModalEvents",
        ):
            self.assertIn(fn, self.js, f"Missing watchlist function: {fn}")



    def test_ashare_pro_header_html_and_css(self):
        """Single-line pro ticker bar elements and rules must exist."""
        self.assertIn('id="ashare-live-header-metrics"', self.html)
        self.assertIn('id="ashare-header-change"', self.html)
        self.assertIn('id="ashare-live-market-status"', self.html)
        self.assertIn('id="ashare-live-exit-btn"', self.html)
        
        # CSS must suppress top website nav and replay bars in live mode
        self.assertIn('#main-app.ashare-live-active > .toolbar', self.css)
        self.assertIn('#main-app.ashare-live-active .chart-window-toolbar', self.css)
        self.assertIn('#main-app.ashare-live-active .replay-status-bar', self.css)
        self.assertIn('#main-app.ashare-live-active .chart-workbench .chart-header', self.css)

    def test_ashare_pro_header_js_functions(self):
        """Ticker formatting and updating functions must be defined in main_enhanced.js."""
        for fn in (
            "function formatAshareSnapshotTime",
            "function formatAshareTurnoverText",
            "function getAshareMarketStatusText",
            "function updateAshareHeaderTicker",
        ):
            self.assertIn(fn, self.js, f"Missing header ticker function: {fn}")

    def test_ashare_live_stock_switch_scale_reset(self):
        """Ensure autoScale reset, marker clearing, and range synchronization exist on stock switch."""
        self.assertIn("clearChartTradePriceLines()", self.js)
        self.assertIn("chart?.priceScale('right')?.applyOptions({ autoScale: true })", self.js)
        self.assertIn("volumeChart?.priceScale('right')?.applyOptions({ autoScale: true })", self.js)
        self.assertIn("setVisibleRangeAll", self.js)
        self.assertIn("pollSymbol !== currentAshareSymbol", self.js)

    def test_fullscreen_focus_mode_layout_and_exit_controls(self):
        """Ensure fullscreen mode preserves header in flow, preserves period switch, and has visible exit controls."""
        self.assertIn("#main-app.chart-focus-mode .chart-header", self.css)
        self.assertIn("position: relative !important", self.css)
        self.assertIn("#main-app.chart-focus-mode #chart-focus-exit-btn", self.css)
        self.assertIn("position: absolute !important", self.css)
        self.assertIn("退出全屏", self.html)
        self.assertIn("toggleButton.textContent = active ? '退出全屏' : '全屏'", self.js)

    def test_ashare_live_theme_toggle_controls_and_light_theme(self):
        """Theme toggle button must be supported and unhidden in A-share live mode, with light theme CSS."""
        self.assertIn("#main-app.ashare-live-active #crypto-theme-toggle-btn", self.css)
        self.assertIn('#main-app.ashare-live-active[data-crypto-theme="light"]', self.css)
        self.assertIn("document.getElementById('crypto-theme-toggle-btn')?.classList.remove('hidden')", self.js)
        self.assertIn("updateThemeButton()", self.js)
        self.assertIn("shortcutKey === 't' && (isCryptoMode() || isAshareLiveMode)", self.js)

    def test_ashare_live_console_collapse_and_expand_controls(self):
        """Trade console collapse and expand tab must function properly in A-share live mode."""
        self.assertIn("#main-app.ashare-live-active.crypto-console-collapsed .trade-console", self.css)
        self.assertIn("#main-app.ashare-live-active.crypto-console-collapsed .crypto-console-collapsed-tab", self.css)
        self.assertIn('id="crypto-console-collapsed-tab"', self.html)
        self.assertIn('class="collapsed-tab-text">交易台<', self.html)
        self.assertIn("document.getElementById('crypto-console-collapsed-tab')?.classList.remove('hidden')", self.js)
        self.assertIn("applyCryptoConsoleLayout(readCryptoConsoleLayout())", self.js)

    def test_ashare_index_watchlist_isolation_and_protection(self):
        """Watchlist quote cache and rendering must prioritize symbol and protect index names from stock collisions."""
        self.assertIn("const q = (st.symbol && ashareWatchlistQuotes[st.symbol]) || ashareWatchlistQuotes[st.code] || {};", self.js)
        self.assertIn("const name = (st.isIndex ? st.name : (q.name || st.name)) || st.code;", self.js)
        self.assertIn("!isIndexCodeCollision", self.js)
        self.assertIn("const rawSym = String(code || '').trim();", self.js)


if __name__ == "__main__":
    unittest.main()


