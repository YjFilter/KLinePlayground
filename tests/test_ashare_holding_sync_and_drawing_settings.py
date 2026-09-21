"""Verification for A-share holding tab synchronization, symbol normalization,
and drawing tool settings / floating toolbar button isolation.
"""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HTML_PATH = PROJECT_ROOT / "frontend" / "index_enhanced.html"
CSS_PATH = PROJECT_ROOT / "frontend" / "css" / "style_enhanced.css"
JS_PATH = PROJECT_ROOT / "frontend" / "js" / "main_enhanced.js"


def _extract_function(source: str, name: str) -> str:
    needle = f"function {name}("
    start = source.find(needle)
    while start >= 0:
        line_start = source.rfind("\n", 0, start) + 1
        if not source[line_start:start].strip().startswith("//"):
            break
        start = source.find(needle, start + len(needle))
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


class AshareHoldingSyncAndDrawingSettingsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = HTML_PATH.read_text(encoding="utf-8")
        cls.css = CSS_PATH.read_text(encoding="utf-8")
        cls.js = JS_PATH.read_text(encoding="utf-8")

    def test_css_sync_order_btn_hidden_has_display_none_important(self):
        """CSS must ensure .drawing-sync-order-btn.hidden has display: none !important."""
        self.assertIn(".drawing-floating-toolbar button.drawing-sync-order-btn.hidden", self.css)
        idx = self.css.find(".drawing-floating-toolbar button.drawing-sync-order-btn.hidden")
        self.assertGreater(idx, -1)
        css_slice = self.css[idx:idx + 150]
        self.assertIn("display: none !important", css_slice)

    def test_normalize_ashare_symbol_function(self):
        """normalizeAshareSymbol must prepend sh/sz/bj according to code prefix."""
        body = _extract_function(self.js, "normalizeAshareSymbol")
        self.assertIn("startsWith('6')", body)
        self.assertIn("startsWith('8')", body)
        self.assertIn("return 'sh' + c", body)
        self.assertIn("return 'sz' + c", body)
        self.assertIn("return 'bj' + c", body)

    def test_drawing_key_and_read_fallback(self):
        """ashareLiveDrawingsKey and readAshareLiveDrawings must handle normalization and fallback."""
        key_body = _extract_function(self.js, "ashareLiveDrawingsKey")
        self.assertIn("normalizeAshareSymbol", key_body)
        read_body = _extract_function(self.js, "readAshareLiveDrawings")
        self.assertIn("candidates", read_body)
        self.assertIn("ASHARE_LIVE_DRAWINGS_PREFIX + normCode", read_body)

    def test_get_ashare_tab_stocks_holding_includes_full_symbol(self):
        """getAshareTabStocks for holding tab must set symbol with market prefix."""
        body = _extract_function(self.js, "getAshareTabStocks")
        self.assertIn("currentAshareWlTab === 'holding'", body)
        self.assertIn("normalizeAshareSymbol(sym)", body)
        self.assertIn("fullSymbol = p.symbol || normalizeAshareSymbol(sym)", body)

    def test_switch_stock_normalizes_current_symbol(self):
        """switchAshareLiveStock must set currentAshareSymbol to normalized symbol."""
        body = _extract_function(self.js, "switchAshareLiveStock")
        self.assertIn("fullSym = normalizeAshareSymbol(rawSym) || rawSym", body)
        self.assertIn("currentAshareSymbol = fullSym", body)

    def test_trade_markers_match_with_normalization(self):
        """updateAshareLiveTradeMarkers must match record by normalized code/symbol."""
        body = _extract_function(self.js, "updateAshareLiveTradeMarkers")
        self.assertIn("normCurSym = normalizeAshareSymbol(symbol)", body)
        self.assertIn("normRecSym = normalizeAshareSymbol(recordSymbol)", body)
        self.assertIn("recordSymbol !== symbol && !match", body)

    def test_sync_drawing_floating_toolbar_restricts_sync_order_btn(self):
        """syncDrawingFloatingToolbar must only show sync-order button for risk-reward drawings."""
        body = _extract_function(self.js, "syncDrawingFloatingToolbar")
        self.assertIn("isRiskDrawing = !!model && (", body)
        self.assertIn("model.type === 'long'", body)
        self.assertIn("model.type === 'short'", body)
        self.assertIn("model.type === 'risk-reward'", body)
        self.assertIn("syncBtn.classList.toggle('hidden', !isRiskDrawing)", body)

    def test_line_settings_panel_title_and_label_visibility(self):
        """renderLineSettingsPanel must set dynamic title and hide price label for polyline/ruler."""
        body = _extract_function(self.js, "renderLineSettingsPanel")
        self.assertIn("'polyline': '折线设置'", body)
        self.assertIn("'horizontal': '水平线设置'", body)
        self.assertIn("'ray': '射线设置'", body)
        self.assertIn("'trend': '趋势线设置'", body)
        self.assertIn("'ruler': '测算尺设置'", body)
        self.assertIn("type === 'polyline' || type === 'ruler'", body)


if __name__ == "__main__":
    unittest.main()
