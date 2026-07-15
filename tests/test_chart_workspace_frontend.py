"""Regression contracts for the resizable chart workspace and local indicators."""

from __future__ import annotations

import json
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
        self.assertEqual(self.html.count('role="separator"'), 2)
        self.assertEqual(self.html.count('tabindex="0"'), 2)

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
  MACD: {{fast: 12, slow: 26, signal: 9}},
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


if __name__ == "__main__":
    unittest.main()
