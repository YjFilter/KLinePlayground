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
        self.assertIn("CRYPTO_PERIODS.includes(currentReportData.period)", self.js)

    def test_crypto_chart_prices_use_usdt_not_yuan(self):
        self.assertIn("function formatMarketPrice", self.js)
        self.assertIn("isCryptoMode() ? formatted + ' USDT'", self.js)
        self.assertIn("formatMarketPrice(barData.close)", self.js)
        self.assertIn("formatMarketPrice(barData.open)", self.js)

    def test_crypto_workspace_has_aicoin_two_column_contract(self):
        self.assertIn("#main-app.crypto-training-active", self.css)
        self.assertIn("grid-template-columns: minmax(0, 1fr) minmax(320px, 340px)", self.css)
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


if __name__ == "__main__":
    unittest.main()
