"""Static verification for the A-share live-watch price alert feature (AICoin style).

Guards the wiring that unit tests cannot reach: the module is loaded before
main_enhanced.js, the toolbar button exists, the CSS classes used by the DOM
wiring are defined, and the polling loop performs a *crossing* evaluation
against the previous tick price (the whole point of the feature — comparing
only the current price would silently drop alerts whenever the 3s poll jumps
across the threshold).
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HTML_PATH = PROJECT_ROOT / "frontend" / "index_enhanced.html"
CSS_PATH = PROJECT_ROOT / "frontend" / "css" / "style_enhanced.css"
JS_PATH = PROJECT_ROOT / "frontend" / "js" / "main_enhanced.js"
MODULE_PATH = PROJECT_ROOT / "frontend" / "js" / "modules" / "price_alerts.js"
TEST_PATH = PROJECT_ROOT / "tests" / "js" / "price_alerts.test.js"


def _collapse(source: str) -> str:
    return re.sub(r"\s+", " ", source)


def _extract_function(source: str, name: str) -> str:
    start = source.find(f"function {name}(")
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


class PriceAlertModuleStaticTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = MODULE_PATH.read_text(encoding="utf-8")
        cls.html = HTML_PATH.read_text(encoding="utf-8")
        cls.js = JS_PATH.read_text(encoding="utf-8")
        cls.flat_js = _collapse(cls.js)

    def test_module_is_umd_and_registers_global(self):
        self.assertIn("root.KLinePriceAlertsModule = factory();", self.module)
        self.assertIn("module.exports = factory();", self.module)

    def test_module_exports_expected_api(self):
        for name in (
            "normalizeAlert",
            "normalizeAlertList",
            "deriveAlertDirection",
            "evaluateAlertCrossing",
            "findTriggeredAlerts",
            "formatAlertLabel",
            "alertStorageKey",
            "selectPersistableAlerts",
        ):
            self.assertIn(name + ":", self.module, f"missing export: {name}")

    def test_module_is_loaded_before_main_enhanced(self):
        module_at = self.html.find('js/modules/price_alerts.js')
        main_at = self.html.find('js/main_enhanced.js')
        self.assertGreater(module_at, -1, "price_alerts.js script tag missing")
        self.assertGreater(main_at, -1)
        self.assertLess(module_at, main_at, "module must load before main_enhanced.js")

    def test_unit_test_file_exists(self):
        self.assertTrue(TEST_PATH.exists(), "missing tests/js/price_alerts.test.js")

    def test_consumed_with_namespaced_aliases(self):
        self.assertIn("} = window.KLinePriceAlertsModule || {};", self.flat_js)
        self.assertIn("evaluateAlertCrossing: evaluatePriceAlertCrossing", self.flat_js)


class PriceAlertHtmlStaticTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = HTML_PATH.read_text(encoding="utf-8")

    def test_toolbar_button_exists_and_is_hidden_by_default(self):
        marker = 'id="alert-add-btn"'
        self.assertIn(marker, self.html)
        start = self.html.find(marker)
        tag_start = self.html.rfind("<button", 0, start)
        tag_end = self.html.find(">", start)
        tag = self.html[tag_start:tag_end]
        self.assertIn('data-alert-action="add"', tag)
        self.assertIn("hidden", tag, "alert button must start hidden (live watch only)")
        self.assertIn('aria-pressed="false"', tag)


class PriceAlertCssStaticTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.css = CSS_PATH.read_text(encoding="utf-8")

    def test_required_classes_are_defined(self):
        for selector in (".alert-chip {", ".alert-chip-close {", ".alert-chip-grip {",
                         ".alert-popup {", ".alert-popup-stack {", ".alert-toast {",
                         ".alert-toast-icon {", ".alert-add-btn.is-adding {"):
            self.assertIn(selector, self.css, f"missing style: {selector}")

    def test_light_theme_overrides_exist(self):
        self.assertIn('[data-theme="light"] .alert-chip', self.css)
        self.assertIn('[data-crypto-theme="light"] .alert-popup', self.css)


class PriceAlertWiringStaticTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.js = JS_PATH.read_text(encoding="utf-8")
        cls.flat = _collapse(cls.js)

    def test_polling_uses_crossing_evaluation_before_overwriting_baseline(self):
        body = _collapse(_extract_function(self.js, "startAshareLivePolling"))
        self.assertIn("checkAshareAlerts(ashareAlertLastPrice, snap.price);", body)
        self.assertIn("ashareAlertLastPrice = snap.price;", body)
        # 基准价必须在判定之后才被覆盖，否则穿越条件永远拿不到"上一价"
        self.assertLess(
            body.find("checkAshareAlerts(ashareAlertLastPrice, snap.price);"),
            body.find("ashareAlertLastPrice = snap.price;"),
        )

    def test_launch_shows_button_and_loads_symbol_alerts(self):
        body = _collapse(_extract_function(self.js, "launchAshareLiveWatch"))
        self.assertIn("bindAshareAlertChartHandlers();", body)
        self.assertIn("document.getElementById('alert-add-btn')?.classList.remove('hidden');", body)
        self.assertIn("loadAshareAlertsForSymbol(currentAshareSymbol);", body)

    def test_exit_hides_button_and_clears_visuals(self):
        body = _collapse(_extract_function(self.js, "exitAshareLiveWatch"))
        self.assertIn("clearAshareAlertVisuals();", body)
        self.assertIn("document.getElementById('alert-add-btn')?.classList.add('hidden');", body)

    def test_switching_symbol_reloads_its_own_alerts(self):
        body = _collapse(_extract_function(self.js, "switchAshareLiveStock"))
        self.assertIn("loadAshareAlertsForSymbol(normCode);", body)

    def test_persistence_only_stores_active_alerts(self):
        body = _collapse(_extract_function(self.js, "persistAshareAlerts"))
        self.assertIn("selectPersistablePriceAlerts(ashareAlerts)", body)
        self.assertIn("localStorage.removeItem(priceAlertStorageKey(symbol));", body)

    def test_three_notification_channels_are_wired(self):
        self.assertIn("function showAshareAlertPopup(", self.flat)
        self.assertIn("function playAshareAlertSound(", self.flat)
        self.assertIn("function sendAshareSystemNotification(", self.flat)
        fire = _collapse(_extract_function(self.js, "fireAshareAlert"))
        for call in ("showAshareAlertPopup(", "playAshareAlertSound();", "sendAshareSystemNotification("):
            self.assertIn(call, fire)

    def test_triggered_alert_is_disabled_and_keeps_a_trace(self):
        body = _collapse(_extract_function(self.js, "checkAshareAlerts"))
        self.assertIn("alert.triggeredAt = Date.now();", body)
        self.assertIn("alert.enabled = false;", body)

    def test_alt_a_and_escape_shortcuts_are_handled(self):
        self.assertIn("if (shortcutKey === 'a' && isAshareLiveMode) {", self.flat)
        self.assertIn("if (event.key === 'Escape' && ashareAlertAdding) {", self.flat)

    def test_alert_chip_events_do_not_leak_to_the_chart(self):
        body = _collapse(_extract_function(self.js, "ensureAshareAlertChip"))
        self.assertIn("event.stopPropagation()", body)


if __name__ == "__main__":
    unittest.main()
