"""Static verification for A-share live-watch trade markers and trade-history timestamps.

Guards two user-reported gaps:
1. The 交易记录 rows showed only ``HH:MM:SS`` with no date, so it was impossible to
   tell *when* a trade happened.
2. Completed live trades left no marker on the K-line chart at all, so there was no
   way to see where a buy/sell occurred.

Tested structurally because they are DOM/chart wiring, not pure logic.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
JS_PATH = PROJECT_ROOT / "frontend" / "js" / "main_enhanced.js"


def _collapse(source: str) -> str:
    return re.sub(r"\s+", " ", source)


def _extract_function(source: str, name: str) -> str:
    """Extract a top-level function body, skipping commented-out definitions.

    main_enhanced.js keeps legacy implementations commented out (e.g. an old
    ``// function updateTradeMarkers(...)``), so a naive ``str.find`` would match
    the dead comment and silently assert against the wrong text.
    """
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


class TradeHistoryTimestampTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.js = JS_PATH.read_text(encoding="utf-8")
        cls.flat = _collapse(cls.js)

    def test_stamp_helpers_exist(self):
        for name in ("formatAshareTradeStamp", "formatAshareTradeStampFull"):
            self.assertIn(f"function {name}(", self.flat, f"missing helper: {name}")

    def test_stamp_shortens_iso_date_to_month_day(self):
        body = _collapse(_extract_function(self.js, "formatAshareTradeStamp"))
        self.assertIn(r"/^\d{4}-\d{2}-\d{2}$/", body)
        self.assertIn("date.slice(5)", body)

    def test_history_row_renders_date_and_full_title(self):
        self.assertIn("formatAshareTradeStampFull(t)", self.flat)
        marker = 'class="ashare-trade-time"'
        start = self.flat.find(marker)
        self.assertGreater(start, -1)
        row = self.flat[start:start + 320]
        self.assertIn("title=", row, "hover title with the full timestamp is missing")
        self.assertIn("formatAshareTradeStamp(t)", row)

    def test_market_and_limit_records_carry_a_date(self):
        # 市价买卖早已写入 date；限价成交此前漏了 date/symbol，导致记录里既没有日期也匹配不到标的
        self.assertIn("date: new Date().toISOString().slice(0, 10), type: '买入'", self.flat)
        self.assertIn("date: new Date().toISOString().slice(0, 10), type: '卖出'", self.flat)
        self.assertIn("symbol: order.code", self.flat)


class TradeMarkerWiringTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.js = JS_PATH.read_text(encoding="utf-8")
        cls.flat = _collapse(cls.js)

    def test_marker_helpers_exist(self):
        for name in ("currentAshareBarTime", "ashareTradeBarTime", "updateAshareLiveTradeMarkers"):
            self.assertIn(f"function {name}(", self.flat, f"missing helper: {name}")

    def test_bar_time_is_preferred_then_falls_back_to_date(self):
        body = _collapse(_extract_function(self.js, "ashareTradeBarTime"))
        self.assertIn("record?.bar_time", body)
        self.assertIn("alignTradeMarkerTimeToRenderedBar(tradeTimestamp)", body)
        # 必须校验对齐结果确实存在于当前 K 线，避免把标记丢到图表之外
        self.assertIn("bars.some((bar) => Number(bar.time) === aligned)", body)

    def test_markers_are_scoped_to_the_current_symbol_and_real_fills(self):
        body = _collapse(_extract_function(self.js, "updateAshareLiveTradeMarkers"))
        self.assertIn("record.symbol || record.code", body, "legacy limit-fill records only carry `code`")
        self.assertIn("recordSymbol !== symbol", body)
        self.assertIn("record.type === '买入'", body)
        self.assertIn("record.type === '卖出'", body)

    def test_buy_below_sell_above_and_chinese_labels(self):
        body = _collapse(_extract_function(self.js, "updateAshareLiveTradeMarkers"))
        self.assertIn("position: 'belowBar'", body)
        self.assertIn("position: 'aboveBar'", body)
        self.assertIn("label: '买'", body)
        self.assertIn("label: '卖'", body)

    def test_marker_renderer_honours_explicit_overrides(self):
        body = _collapse(_extract_function(self.js, "updateTradeMarkers"))
        for override in ("marker.position ||", "marker.color ||", "marker.shape ||", "marker.label ||"):
            self.assertIn(override, body, f"missing override: {override}")

    def test_markers_refresh_on_every_path_that_changes_fills_or_bars(self):
        for fn, note in (
            ("loadAshareLiveData", "进入看盘/换股/换周期"),
            ("executeAshareLiveBuy", "市价买入"),
            ("executeAshareLiveSell", "市价卖出"),
            ("matchAsharePendingOrders", "限价成交"),
            ("clearAshareTradeHistory", "清空记录"),
            ("resetAshareLiveAccount", "重置账户"),
        ):
            body = _collapse(_extract_function(self.js, fn))
            self.assertIn("updateAshareLiveTradeMarkers();", body, f"{fn} 未刷新成交标记（{note}）")

    def test_trade_records_capture_the_bar_time(self):
        # 市价买卖记录 bar_time，换周期后仍能通过日期回退定位
        self.assertLessEqual(self.flat.count("bar_time: currentAshareBarTime()"), 4)
        self.assertGreaterEqual(self.flat.count("bar_time: currentAshareBarTime()"), 2)
        self.assertIn("bar_time: String(order.code) === String(currentAshareSymbol) ? currentAshareBarTime() : null", self.flat)


if __name__ == "__main__":
    unittest.main()
