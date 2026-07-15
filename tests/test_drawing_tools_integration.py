import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML_PATH = ROOT / "frontend" / "index_enhanced.html"
JS_PATH = ROOT / "frontend" / "js" / "main_enhanced.js"
DRAWING_JS_PATH = ROOT / "frontend" / "js" / "drawing_tools.js"


class DrawingToolsIntegrationStaticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = HTML_PATH.read_text(encoding="utf-8")
        cls.js = JS_PATH.read_text(encoding="utf-8")
        cls.drawing_js = DRAWING_JS_PATH.read_text(encoding="utf-8")

    def test_drawing_module_loads_before_main(self):
        drawing_index = self.html.find('js/drawing_tools.js')
        main_index = self.html.find('js/main_enhanced.js')
        self.assertGreaterEqual(drawing_index, 0)
        self.assertGreater(main_index, drawing_index)

    def test_left_toolbar_exposes_approved_tools_and_actions(self):
        self.assertIn('id="drawing-toolbar"', self.html)
        for tool in (
            "select", "trend", "horizontal", "ray", "rectangle", "text",
            "fibonacci", "ruler", "long-position", "short-position",
        ):
            self.assertIn(f'data-drawing-tool="{tool}"', self.html)
        for action in ("lock", "hide", "delete", "undo", "redo", "clear"):
            self.assertIn(f'data-drawing-action="{action}"', self.html)
        self.assertIn('id="drawing-fibonacci-settings"', self.html)

    def test_main_owns_drawing_controller_lifecycle(self):
        self.assertIn("function initializeDrawingTools", self.js)
        self.assertIn("function syncDrawingToolBars", self.js)
        self.assertIn("function destroyDrawingTools", self.js)
        self.assertIn("window.KLineDrawingTools", self.js)
        reset_start = self.js.index("function resetToMainAppState()")
        destroy_index = self.js.index("destroyDrawingTools()", reset_start)
        chart_remove_index = self.js.index("chart.remove()", reset_start)
        self.assertLess(destroy_index, chart_remove_index)
        self.assertIn("drawingUiAbortController.abort()", self.js)
        self.assertNotIn("{ once: true }", self.js)

    def test_drawing_controls_publish_accessible_names_and_state(self):
        self.assertIn('data-drawing-tool="select" aria-label=', self.html)
        self.assertIn('aria-pressed="false"', self.html)
        self.assertIn('data-fibonacci-action="close" aria-label=', self.html)
        self.assertIn("enabled.setAttribute('aria-label'", self.js)
        self.assertIn(".drawing-toolbar button:focus-visible", (ROOT / "frontend" / "css" / "style_enhanced.css").read_text(encoding="utf-8"))

    def test_period_and_window_updates_sync_without_clearing(self):
        self.assertGreaterEqual(self.js.count("syncDrawingToolBars("), 3)
        self.assertNotIn("clearDrawingsOnPeriodChange", self.js)

    def test_drawing_runtime_exposes_drag_draft_snap_and_interaction_contracts(self):
        for token in (
            "_draftPrimitive", "requestAnimationFrame", "onInteractionStateChange",
            "SNAP_DISTANCE_PX", "盈亏比", "账户", "仓量",
        ):
            self.assertIn(token, self.drawing_js)


if __name__ == "__main__":
    unittest.main()
