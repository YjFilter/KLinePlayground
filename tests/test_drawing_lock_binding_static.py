"""Guard: the drawing lock button must fire exactly once per click.

Regression (user report): pressing the padlock on the floating drawing toolbar did
nothing — the object stayed draggable.

Root cause: the floating-toolbar buttons match BOTH bindings —
  * the generic ``document.querySelectorAll('[data-drawing-action]')`` loop, and
  * ``bindDrawingFloatingToolbar()`` which owns them.
So one click invoked ``invokeDrawingAction('lock')`` twice and ``toggleLock()`` ran
twice: lock -> unlock. A pure toggle therefore looked like a no-op. (delete survived
because the second call is a no-op once the selection is gone; settings/sync-order are
not in the generic method map at all — only lock/hide broke, which is why it went
unnoticed.)

The fix makes the generic loop skip buttons inside ``#drawing-floating-toolbar``.
"""

from __future__ import annotations

import unittest

from tests._frontend_js import PROJECT_ROOT, load_frontend_js


class DrawingLockBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.js = load_frontend_js()

    def test_generic_binding_skips_floating_toolbar_buttons(self):
        marker = "if (button.closest('#drawing-floating-toolbar')) return;"
        self.assertIn(
            marker,
            self.js,
            "the generic [data-drawing-action] loop must not bind floating-toolbar buttons",
        )
        # 在 [data-drawing-action] 这个循环块内校验顺序：跳过必须发生在
        # "登记已绑定标记"之前，避免把按钮标记成已绑定却没人管它。
        loop_start = self.js.find("document.querySelectorAll('[data-drawing-action]')")
        self.assertGreater(loop_start, 0, "[data-drawing-action] loop not found")
        block = self.js[loop_start : loop_start + 600]
        skip_at = block.find(marker)
        mark_at = block.find("button.dataset.drawingBound = '1';")
        self.assertGreater(skip_at, 0, "skip guard missing inside the action loop")
        self.assertGreater(mark_at, 0)
        self.assertLess(skip_at, mark_at)

    def test_floating_toolbar_has_its_own_handler(self):
        self.assertIn("function bindDrawingFloatingToolbar()", self.js)
        self.assertIn("bindDrawingFloatingToolbar();", self.js)

    def test_lock_action_maps_to_toggle_lock(self):
        start = self.js.find("function invokeDrawingAction(")
        self.assertGreater(start, 0)
        body = self.js[start : start + 1600]
        self.assertIn("lock: 'toggleLock'", body)

    def test_lock_refresh_reports_real_state_after_toggle(self):
        start = self.js.find("function invokeDrawingAction(")
        body = self.js[start : start + 2200]
        self.assertIn("syncDrawingFloatingToolbar(selectedId, model)", body)
        self.assertIn("已锁定：该图形不可拖动/缩放", body)

    def test_shackle_swap_does_not_corrupt_the_16px_toolbar_icon(self):
        """主工具条的锁是 16x16 几何，锁体替换必须只作用于 24x24 那套图标。"""
        start = self.js.find("function applyDrawingLockVisualState(")
        self.assertGreater(start, 0)
        body = self.js[start : start + 1200]
        self.assertIn("DRAWING_LOCK_SHACKLE_CLOSED", body)
        self.assertIn("current === DRAWING_LOCK_SHACKLE_CLOSED", body)

    def test_controller_blocks_dragging_of_locked_drawings(self):
        source = (PROJECT_ROOT / "frontend" / "js" / "drawing_tools.js").read_text(encoding="utf-8")
        self.assertIn("if (hit.locked) {", source)
        self.assertIn("this._gesture = null;", source)
        # 锁定对象不再绘制锚点手柄（无从下手拖）
        self.assertIn("if ((model.hovered || model.selected) && !model.locked)", source)


if __name__ == "__main__":
    unittest.main()
