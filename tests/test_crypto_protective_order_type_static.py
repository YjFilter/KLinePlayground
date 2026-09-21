"""Static + behavioural guard for how the chart creates take-profit / stop-loss orders.

Regression context (user report): a long position was opened, a stop-loss line was
dragged onto the chart, and the position was closed on the very next bar even though
price never reached the stop.

Root cause: the drag handler submitted ``order_type: 'limit'`` for BOTH take-profit and
stop-loss.  The engine matches a *sell limit* with ``high >= limit``, so a stop placed
BELOW the market is immediately marketable and fills on the next bar.  A stop-loss must
be a **breakout** order (``low <= trigger``); only take-profit may use a limit order.

These tests pin the three places that must stay in agreement:
  1. ``resolveCloseOrderType`` maps (price, mark, close side) -> 'limit' | 'breakout'.
  2. the drag handler resolves the type from the price instead of hardcoding 'limit'.
  3. the AICoin pill shows the real order type instead of a hard-coded "市价".
"""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from tests._frontend_js import PROJECT_ROOT, load_frontend_js


NODE_CANDIDATES = (
    Path.home() / ".workbuddy" / "binaries" / "node" / "versions" / "22.22.2-3" / "node.exe",
    Path.home() / ".workbuddy" / "binaries" / "node" / "versions" / "22.22.2-2" / "node.exe",
    Path.home() / ".workbuddy" / "binaries" / "node" / "versions" / "22.22.2" / "node.exe",
)


def _find_node() -> str:
    for candidate in NODE_CANDIDATES:
        if candidate.exists():
            return str(candidate)
    return "node"


def _extract_function(source: str, declaration: str) -> str:
    """Return the full text of ``declaration`` (e.g. ``function foo(``) with balanced braces.

    The search is anchored on a newline so a commented-out copy of the function can
    never be mistaken for the live one (that trap already bit this suite once).
    """
    start = source.find("\n" + declaration)
    if start < 0:
        return ""
    start += 1
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
                return source[start : index + 1]
    return source[start:]


class ProtectiveOrderTypeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.js = load_frontend_js()
        cls.orders_py = (PROJECT_ROOT / "backend" / "crypto" / "futures_orders.py").read_text(
            encoding="utf-8"
        )
        cls.drag_body = _extract_function(cls.js, "async function createProtectiveOrderFromDrag(")

    # ----- 1.价位 -> 类型 的映射（真跑一遍 JS） -----

    def test_resolve_close_order_type_geometry(self):
        """多头现价上方=止盈(限价)、下方=止损(突破)；空头相反。"""
        body = _extract_function(self.js, "function resolveCloseOrderType(")
        self.assertTrue(body, "resolveCloseOrderType() is missing from the frontend bundle")

        script = body + r"""
const cases = [
  [110, 100, 'sell', 'limit'],     // 多头止盈（限价）
  [90,  100, 'sell', 'breakout'],  // 多头止损（突破）—— 必须走 breakout
  [90,  100, 'buy',  'limit'],     // 空头止盈（限价）
  [110, 100, 'buy',  'breakout'],  // 空头止损（突破）
  [100, 100, 'sell', 'breakout'],  // 恰好等于现价 -> 退化，由校验层拦下
];
const actual = cases.map(([price, mark, side]) => resolveCloseOrderType(price, mark, side));
const expected = cases.map((row) => row[3]);
if (JSON.stringify(actual) !== JSON.stringify(expected)) {
  throw new Error('resolveCloseOrderType mismatch: ' + JSON.stringify(actual));
}
console.log('OK');
"""
        completed = self._run_node(script)
        self.assertIn("OK", completed.stdout, completed.stderr)

    # ----- 2.拖动创建保护单时发什么 -----

    def test_drag_handler_is_wired_to_resolver(self):
        self.assertTrue(self.drag_body, "createProtectiveOrderFromDrag() is missing")
        # 必须复用共享解析器，避免拖动路径与手动下单路径各写一套方向判断而漂移
        self.assertIn("resolveCloseOrderType(target, mark, closeSide)", self.drag_body)
        self.assertIn("const isTakeProfit = orderType === 'limit';", self.drag_body)

    def test_drag_handler_sends_breakout_with_trigger_price(self):
        """止损分支必须是「突破单 + trigger_price」，否则又变成下一根 K 线成交的市价平仓。"""
        self.assertIn("{ action: 'close', order_type: 'breakout', trigger_price: target }", self.drag_body)
        self.assertIn("{ action: 'close', order_type: 'limit', limit_price: target }", self.drag_body)

    def test_drag_handler_rejects_price_equal_to_mark(self):
        self.assertIn("保护价不能等于当前标记价", self.drag_body)

    def test_drag_handler_refuses_when_flat(self):
        self.assertIn("getCryptoPendingSide('close')", self.drag_body)

    # ----- 3.浮层文案 -----

    def test_protective_pill_shows_real_order_type(self):
        start = self.js.find("} else if (isTp || isSl) {")
        self.assertGreater(start, 0, "protective pill branch not found")
        branch = self.js[start : start + 900]
        self.assertNotIn("createPillSegment('市价'", branch)
        self.assertIn("item.order?.order_type", branch)

    # ----- 4.后端护栏 -----

    def test_backend_guards_marketable_limit_close(self):
        """后端必须拒绝"会立即成交"的平仓限价单，否则这个 bug 会从 API 复活。"""
        self.assertIn("平多限价必须高于当前标记价", self.orders_py)
        self.assertIn("平空限价必须低于当前标记价", self.orders_py)

    def test_backend_amending_across_market_switches_order_type(self):
        """拖动改单跨过现价时必须改判类型（限价↔突破）。"""
        self.assertIn("_retarget_reduce_only_order", self.orders_py)

    def test_backend_match_priority_helper_is_used(self):
        self.assertIn("def _protective_priority(", self.orders_py)
        self.assertIn("sorted(list(self.active_orders), key=_protective_priority)", self.orders_py)

    def _run_node(self, script: str):
        with tempfile.TemporaryDirectory() as tmp:
            script_path = Path(tmp) / "guard.mjs"
            script_path.write_text(script, encoding="utf-8")
            return subprocess.run(
                [_find_node(), str(script_path)],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )


if __name__ == "__main__":
    unittest.main()
