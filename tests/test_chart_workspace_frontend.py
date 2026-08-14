"""Regression contracts for the resizable chart workspace and local indicators."""

from __future__ import annotations

import json
import re
import subprocess
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
HTML_PATH = PROJECT_ROOT / "frontend" / "index_enhanced.html"
CSS_PATH = PROJECT_ROOT / "frontend" / "css" / "style_enhanced.css"
JS_PATH = PROJECT_ROOT / "frontend" / "js" / "main_enhanced.js"
INDICATOR_MATH_PATH = PROJECT_ROOT / "frontend" / "js" / "indicator_math.js"


class ChartWorkspaceStructureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = HTML_PATH.read_text(encoding="utf-8")
        cls.css = CSS_PATH.read_text(encoding="utf-8")
        cls.js = JS_PATH.read_text(encoding="utf-8")

    def test_chart_panels_have_two_keyboard_accessible_splitters(self):
        self.assertIn('class="chart-panels"', self.html)
        self.assertEqual(self.html.count('class="chart-panel-splitter"'), 2)
        self.assertIn('data-before-panel="chart"', self.html)
        self.assertIn('data-after-panel="volume-chart"', self.html)
        self.assertIn('data-before-panel="volume-chart"', self.html)
        self.assertIn('data-after-panel="indicator-chart"', self.html)
        splitters = re.findall(r'<div class="chart-panel-splitter"[^>]+>', self.html)
        self.assertEqual(len(splitters), 2)
        for splitter in splitters:
            self.assertIn('role="separator"', splitter)
            self.assertIn('tabindex="0"', splitter)

    def test_splitters_are_visibly_draggable(self):
        self.assertIn(".chart-panel-splitter", self.css)
        self.assertIn("cursor: row-resize", self.css)
        self.assertIn("touch-action: none", self.css)

    def test_panel_resizing_is_persisted_and_observed(self):
        self.assertIn("function setupChartPanelResizers", self.js)
        self.assertIn("kline-chart-panel-heights", self.js)
        self.assertIn("new ResizeObserver", self.js)
        self.assertIn("localStorage.setItem", self.js)
        self.assertIn("resizeCharts()", self.js)

    def test_training_layout_is_compact_and_panels_can_collapse_meaningfully(self):
        self.assertIn("training-active", self.js)
        self.assertIn("#main-app.training-active .toolbar", self.css)
        self.assertIn("#main-app.training-active .chart-header", self.css)
        self.assertIn("'volume-chart': 32", self.js)
        self.assertIn("'indicator-chart': 52", self.js)

    def test_crypto_chart_chrome_has_required_static_controls(self):
        self.assertIn('class="market-period-toolbar"', self.html)
        self.assertIn('id="toggle-volume-panel-btn"', self.html)
        self.assertIn('id="toggle-indicator-panel-btn"', self.html)
        self.assertIn('id="chart-fullscreen-btn"', self.html)
        self.assertIn('aria-controls="volume-chart"', self.html)
        self.assertIn('aria-controls="indicator-chart"', self.html)
        self.assertIn('aria-controls="chart-panels"', self.html)

    def test_crypto_drawing_toolbar_becomes_horizontal(self):
        self.assertIn("#main-app.crypto-training-active .drawing-toolbar", self.css)
        self.assertIn("flex-direction: row", self.css)
        self.assertIn("overflow-x: auto", self.css)

    def test_crypto_layout_degrades_vertically_below_980(self):
        media_start = self.css.index("@media (max-width: 980px)")
        responsive_css = self.css[media_start:]
        self.assertIn("#main-app.crypto-training-active .training-workspace", responsive_css)
        self.assertIn("grid-template-columns: minmax(0, 1fr)", responsive_css)
        self.assertIn(".trade-console", responsive_css)


class LocalIndicatorIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = HTML_PATH.read_text(encoding="utf-8")
        cls.js = JS_PATH.read_text(encoding="utf-8")

    def test_indicator_math_is_loaded_before_main_script(self):
        indicator_index = self.html.find('js/indicator_math.js')
        main_index = self.html.find('js/main_enhanced.js')
        self.assertGreaterEqual(indicator_index, 0)
        self.assertGreater(main_index, indicator_index)

    def test_intraday_indicator_branch_no_longer_clears_and_returns(self):
        start = self.js.index("async function loadTechnicalIndicator")
        end = self.js.index("\nfunction changeIndicator", start)
        body = self.js[start:end]
        self.assertIn("KLineIndicatorMath.calculate", body)
        self.assertNotIn("intraday 模式清空指标系列", body)
        self.assertNotIn("/indicators/", body)

    def test_snapshot_and_chart_window_refresh_indicators(self):
        intraday_start = self.js.index("function applyIntradaySnapshot")
        intraday_end = self.js.index("\nconst THEME_PALETTES", intraday_start)
        self.assertIn("loadTechnicalIndicator(currentIndicatorType)", self.js[intraday_start:intraday_end])

        window_start = self.js.index("function applyChartWindow")
        window_end = self.js.index("\nfunction enqueueChartWindowRequest", window_start)
        self.assertIn("loadTechnicalIndicator(currentIndicatorType)", self.js[window_start:window_end])


class IntradayTradeMarkerFrontendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.js = JS_PATH.read_text(encoding="utf-8")

    def test_trade_markers_align_to_the_current_rendered_period(self):
        self.assertIn("function alignTradeMarkerTimeToRenderedBar", self.js)
        start = self.js.index("function updateTradeMarkers(markers)", self.js.index("function updateTradeMarkers(markers)") + 1)
        end = self.js.index("\n// 回放控制", start)
        body = self.js[start:end]
        self.assertIn("time: alignTradeMarkerTimeToRenderedBar(marker.time)", body)
        self.assertIn("tradeMarkerSeries.setMarkers(markerData)", body)
        self.assertNotIn("createSeriesMarkers(candlestickSeries, markerData)", body)

    def test_buy_and_sell_sync_markers_immediately(self):
        self.assertGreaterEqual(self.js.count("syncActiveTradeMarkers(result.trade_markers)"), 2)

    def test_intraday_snapshot_preserves_existing_markers(self):
        start = self.js.index("function applyIntradaySnapshot")
        end = self.js.index("\nconst THEME_PALETTES", start)
        body = self.js[start:end]
        self.assertNotIn("currentTraining.tradeMarkers = []", body)
        self.assertIn("updateTradeMarkers", body)


class IndicatorMathRuntimeTests(unittest.TestCase):
    def test_all_indicators_return_finite_chart_points(self):
        script = f"""
const math = require({json.dumps(str(INDICATOR_MATH_PATH))});
const bars = Array.from({{length: 80}}, (_, index) => ({{
  time: 1700000000 + index * 1800,
  open: 10 + index * 0.03,
  high: 10.4 + index * 0.03 + (index % 5) * 0.02,
  low: 9.7 + index * 0.03 - (index % 3) * 0.01,
  close: 10.1 + index * 0.03 + Math.sin(index / 4) * 0.2,
}}));
const configs = {{
  MACD: {{fast: 10, slow: 20, signal: 5}},
  KDJ: {{n: 9, m1: 3, m2: 3}},
  RSI: {{periods: [6, 12, 24]}},
  BOLL: {{period: 20, stdDev: 2}},
}};
for (const type of Object.keys(configs)) {{
  const result = math.calculate(type, bars, configs[type]);
  if (!result || !Array.isArray(result.data) || result.data.length === 0) {{
    throw new Error(type + ' returned no data');
  }}
  for (const point of result.data) {{
    for (const [key, value] of Object.entries(point)) {{
      if (key !== 'time' && !Number.isFinite(value)) throw new Error(type + ' has invalid ' + key);
    }}
  }}
}}
"""
        completed = subprocess.run(
            ["node", "-e", script],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)


class MaIndicatorDefaultSettingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.js = JS_PATH.read_text(encoding="utf-8")

    def test_ma_default_settings_match_reference_specification(self):
        self.assertIn("const INDICATOR_SETTINGS_KEY = 'indicatorSettingsV2'", self.js)
        self.assertIn("{ period: 10, visible: false, color: '#7038db' }", self.js)
        self.assertIn("{ period: 20, visible: true, color: '#2196f3' }", self.js)
        self.assertIn("{ period: 40, visible: true, color: '#52c41a' }", self.js)
        self.assertIn("{ period: 80, visible: true, color: '#26c6da' }", self.js)
        self.assertIn("{ period: 160, visible: true, color: '#b85717' }", self.js)

    def test_ma_visibility_guards_legend_info_and_tooltip(self):
        self.assertIn("if (maSeries[p] && isMaLineVisible(p))", self.js)
        self.assertIn("if (!series || !isMaLineVisible(p)) return;", self.js)
        self.assertIn("if (!isMaLineVisible(p)) return;", self.js)


class ChartTradePriceLinesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.js = JS_PATH.read_text(encoding="utf-8")

    def test_trade_price_lines_functions_and_variables_exist(self):
        self.assertIn("let activeChartTradePriceLines = [];", self.js)
        self.assertIn("function clearChartTradePriceLines()", self.js)
        self.assertIn("function updateChartTradePriceLines()", self.js)

    def test_trade_price_lines_wired_into_lifecycle_events(self):
        self.assertIn("updateChartTradePriceLines();", self.js)
        self.assertIn("clearChartTradePriceLines();", self.js)

    def test_trade_price_lines_node_execution_logic(self):
        script = r"""
const lines = [];
const candlestickSeries = {
  createPriceLine(opt) {
    lines.push(opt);
    return opt;
  },
  removePriceLine(line) {
    const idx = lines.indexOf(line);
    if (idx >= 0) lines.splice(idx, 1);
  }
};
let activeChartTradePriceLines = [];
let currentTraining = {
  id: 'test-session',
  position: { side: 'long', quantity: 1.5, entry_price: 64200, unrealized_pnl: 150.25, isolated_margin: 642 },
  pending_orders: [
    { order_id: 'tp1', parent_order_id: 'p1', protection_type: 'tp', limit_price: 66000, status: 'active' },
    { order_id: 'sl1', parent_order_id: 'p1', protection_type: 'sl', trigger_price: 63000, status: 'active' },
    { order_id: 'o2', action: 'open_short', order_type: 'limit', limit_price: 68000, quantity: 0.5, status: 'active' }
  ]
};
function isCryptoMode() { return true; }
function formatCryptoValue(val, maxD = 8) { return Number(val).toLocaleString(undefined, { maximumFractionDigits: maxD }); }
function getCryptoProtectivePrices(pendingOrders) {
  let tp = 0, sl = 0;
  (pendingOrders || []).forEach(o => {
    if (!o || !o.parent_order_id) return;
    if (o.protection_type === 'tp') tp = Number(o.limit_price || o.tp_price || 0);
    if (o.protection_type === 'sl') sl = Number(o.trigger_price || o.sl_price || 0);
  });
  return { tp, sl };
}
""" + self.js[self.js.find("function clearChartTradePriceLines()"):self.js.find("function renderCryptoPositionCard(")] + r"""

updateChartTradePriceLines();
if (lines.length !== 4) {
  throw new Error(`Expected 4 price lines (pos, tp, sl, limit), got ${lines.length}`);
}
const posLine = lines.find(l => l.price === 64200);
if (!posLine || !posLine.title.includes('多') || !posLine.title.includes('1.5') || posLine.color !== '#2196f3') {
  throw new Error('Position price line invalid: ' + JSON.stringify(posLine));
}
const tpLine = lines.find(l => l.price === 66000);
if (!tpLine || !tpLine.title.includes('止盈') || tpLine.color !== '#0ecb81') {
  throw new Error('TP price line invalid: ' + JSON.stringify(tpLine));
}
const slLine = lines.find(l => l.price === 63000);
if (!slLine || !slLine.title.includes('止损') || slLine.color !== '#f6465d') {
  throw new Error('SL price line invalid: ' + JSON.stringify(slLine));
}
const limitLine = lines.find(l => l.price === 68000);
if (!limitLine || !limitLine.title.includes('限价') || limitLine.color !== '#2962ff') {
  throw new Error('Limit order price line invalid: ' + JSON.stringify(limitLine));
}

// Test clear
clearChartTradePriceLines();
if (lines.length !== 0) {
  throw new Error('Failed to clear price lines');
}
"""
        completed = subprocess.run(
            ["node", "-e", script],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)


if __name__ == "__main__":
    unittest.main()

