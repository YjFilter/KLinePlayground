import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
JS_PATH = ROOT / "frontend" / "js" / "main_enhanced.js"


class CryptoWorkspaceInteractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.js = JS_PATH.read_text(encoding="utf-8")

    def function_source(self, name):
        match = re.search(rf"(?:async )?function {name}\([^)]*\)\s*{{", self.js)
        self.assertIsNotNone(match, name)
        start = match.start()
        depth = 0
        for index in range(self.js.find("{", start), len(self.js)):
            if self.js[index] == "{":
                depth += 1
            elif self.js[index] == "}":
                depth -= 1
                if depth == 0:
                    return self.js[start:index + 1]
        self.fail(f"unterminated function {name}")

    def test_crypto_period_switch_is_single_request_without_window_or_account_reload(self):
        source = self.function_source("switchCryptoViewPeriod")
        self.assertIn("/period", source)
        self.assertIn("periodSwitchAbortController", source)
        self.assertIn("request_id", source)
        self.assertIn("range_start", source)
        self.assertIn("range_end", source)
        self.assertIn("applyIntradaySnapshot", source)
        self.assertNotIn("reloadChartWindowForPeriod", source)
        self.assertNotIn("updateAccountInfo", source)

    def test_period_loading_indicator_is_delayed_and_rapid_switches_are_versioned(self):
        self.assertIn("const PERIOD_LOADING_DELAY_MS = 150", self.js)
        self.assertIn("let periodSwitchGeneration = 0", self.js)
        self.assertIn("function beginPeriodSwitchFeedback", self.js)
        self.assertIn("function endPeriodSwitchFeedback", self.js)

    def test_crypto_workspace_controls_have_event_handlers(self):
        for function in (
            "toggleChartPanel",
            "toggleChartFullscreen",
            "selectCryptoOrderAction",
            "syncCryptoWorkspaceMode",
        ):
            self.assertIn(f"function {function}", self.js)
        self.assertIn("[data-crypto-action]", self.js)
        self.assertIn("toggle-volume-panel-btn", self.js)
        self.assertIn("toggle-indicator-panel-btn", self.js)
        self.assertIn("chart-fullscreen-btn", self.js)
        self.assertIn("crypto-end-training-btn", self.js)
        self.assertIn("crypto-reset-training-btn", self.js)

    def test_drawings_clear_at_training_lifecycle_boundaries(self):
        self.assertIn("function clearSessionDrawings", self.js)
        for name in ("startTrainingWithConfig", "endTraining", "resetTraining"):
            self.assertIn("clearSessionDrawings", self.function_source(name))

    def test_drawing_controller_receives_feedback_and_account_context(self):
        source = self.function_source("initializeDrawingTools")
        self.assertIn("onError", source)
        self.assertIn("onInteractionChange", source)
        self.assertIn("accountSizeProvider", source)
        self.assertIn("setDrawingStatus", self.js)
        self.assertIn("resetAll", self.function_source("clearSessionDrawings"))


if __name__ == "__main__":
    unittest.main()
