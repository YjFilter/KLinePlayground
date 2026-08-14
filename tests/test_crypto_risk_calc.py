"""Runtime contracts for the risk-based position sizing module (以损定仓)."""

from __future__ import annotations

import json
import subprocess
import textwrap
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
RISK_CALC_PATH = PROJECT_ROOT / "frontend" / "js" / "risk_calc.js"
MAIN_JS_PATH = PROJECT_ROOT / "frontend" / "js" / "main_enhanced.js"
HTML_PATH = PROJECT_ROOT / "frontend" / "index_enhanced.html"
SIMULATOR_PATH = PROJECT_ROOT / "backend" / "crypto" / "futures_simulator.py"


def run_node(script: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["node", "-e", textwrap.dedent(script)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


class RiskCalcMathRuntimeTests(unittest.TestCase):
    def test_quantity_notional_and_margin_follow_max_loss_and_leverage(self):
        script = f"""
        const risk = require({json.dumps(str(RISK_CALC_PATH))});
        const assert = require('node:assert/strict');
        const long = risk.computeRiskPosition({{
            entryPrice: 100, stopPrice: 95, maxLoss: 50, leverage: 10, action: 'open_long',
        }});
        assert.equal(long.valid, true);
        assert.equal(long.quantity, 10);
        assert.equal(long.notional, 1000);
        assert.equal(long.margin, 100);
        assert.ok(Math.abs(long.stopRate - 0.05) < 1e-12);
        assert.ok(Math.abs(long.marginLossRate - 0.5) < 1e-12);
        assert.equal(long.directionOk, true);
        const short = risk.computeRiskPosition({{
            entryPrice: 100, stopPrice: 104, maxLoss: 80, leverage: 5, action: 'open_short',
        }});
        assert.equal(short.valid, true);
        assert.equal(short.quantity, 20);
        assert.equal(short.margin, 400);
        assert.equal(short.directionOk, true);
        """
        completed = run_node(script)
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_direction_warning_stop_collision_and_missing_inputs(self):
        script = f"""
        const risk = require({json.dumps(str(RISK_CALC_PATH))});
        const assert = require('node:assert/strict');
        const wrongSide = risk.computeRiskPosition({{
            entryPrice: 100, stopPrice: 105, maxLoss: 10, leverage: 2, action: 'open_long',
        }});
        assert.equal(wrongSide.valid, true);
        assert.equal(wrongSide.directionOk, false);
        const collision = risk.computeRiskPosition({{
            entryPrice: 100, stopPrice: 100, maxLoss: 10, leverage: 2, action: 'open_long',
        }});
        assert.equal(collision.valid, false);
        assert.equal(collision.reason, 'stop-too-close');
        const missing = risk.computeRiskPosition({{
            entryPrice: 100, stopPrice: 95, maxLoss: 0, leverage: 2, action: 'open_long',
        }});
        assert.equal(missing.valid, false);
        assert.equal(missing.reason, 'missing-inputs');
        const clamped = risk.computeRiskPosition({{
            entryPrice: 100, stopPrice: 95, maxLoss: 50, leverage: 500, action: 'open_long',
        }});
        assert.equal(clamped.leverage, 100);
        assert.equal(clamped.margin, 10);
        """
        completed = run_node(script)
        self.assertEqual(completed.returncode, 0, completed.stderr)


class RiskCalcFrontendContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = HTML_PATH.read_text(encoding="utf-8")
        cls.js = MAIN_JS_PATH.read_text(encoding="utf-8")
        cls.simulator = SIMULATOR_PATH.read_text(encoding="utf-8")

    def test_risk_calc_module_loaded_before_main_script(self):
        risk_index = self.html.find("js/risk_calc.js")
        main_index = self.html.find("js/main_enhanced.js")
        self.assertGreaterEqual(risk_index, 0)
        self.assertLess(risk_index, main_index)

    def test_risk_calc_inputs_and_actions_present(self):
        for element_id in (
            "crypto-riskcalc-enabled",
            "crypto-riskcalc-fields",
            "crypto-riskcalc-entry",
            "crypto-riskcalc-stop",
            "crypto-riskcalc-maxloss",
            "crypto-riskcalc-apply",
            "crypto-riskcalc-result",
        ):
            self.assertIn(f'id="{element_id}"', self.html, element_id)

    def test_main_js_wires_risk_calc_to_order_form(self):
        self.assertIn("window.RiskCalc.computeRiskPosition", self.js)
        self.assertIn("function applyCryptoRiskCalc", self.js)
        self.assertIn("crypto-margin", self.js[self.js.index("function applyCryptoRiskCalc"):])

    def test_leverage_selects_offer_100x_and_simulator_allows_it(self):
        self.assertEqual(self.html.count('<option value="100">100x</option>'), 2)
        self.assertIn("1 <= leverage <= 100", self.simulator)


if __name__ == "__main__":
    unittest.main()
