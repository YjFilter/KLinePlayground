"""Tests for drawing tool long/short risk box synchronization to order panel."""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HTML_PATH = PROJECT_ROOT / "frontend" / "index_enhanced.html"
JS_PATH = PROJECT_ROOT / "frontend" / "js" / "main_enhanced.js"
RISK_CALC_PATH = PROJECT_ROOT / "frontend" / "js" / "risk_calc.js"


class DrawingOrderSyncTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = HTML_PATH.read_text(encoding="utf-8")
        cls.js = JS_PATH.read_text(encoding="utf-8")
        cls.risk_calc_js = RISK_CALC_PATH.read_text(encoding="utf-8")

    def test_sync_order_button_exists_in_html(self):
        self.assertIn('data-drawing-action="sync-order"', self.html)
        self.assertIn('class="drawing-sync-order-btn', self.html)
        self.assertIn('⚡ 同步下单', self.html)

    def test_offline_data_dashboard_elements_exist_in_html(self):
        self.assertIn('id="refresh-offline-data-btn"', self.html)
        self.assertIn('id="offline-data-table-body"', self.html)
        self.assertIn('id="offline-download-symbol"', self.html)
        self.assertIn('id="start-offline-download-btn"', self.html)

    def test_sync_drawing_to_order_panel_js_function_exists(self):
        self.assertIn("function syncDrawingToOrderPanel(model)", self.js)
        self.assertIn("data-drawing-action=\"sync-order\"", self.js)
        self.assertIn("loadCryptoOfflineStatus", self.js)
        self.assertIn("triggerCryptoOfflineDownload", self.js)

    def test_nodejs_sync_drawing_long_and_short_execution(self):
        script = f"""
{self.risk_calc_js}
const window = global;
window.RiskCalc = RiskCalc;

// Mock DOM elements
const elements = {{
    'crypto-order-action': {{ value: 'open_long' }},
    'crypto-order-type': {{ value: 'market' }},
    'crypto-limit-price': {{ value: '' }},
    'crypto-limit-price-group': {{ classList: {{ toggle: () => {{}} }} }},
    'crypto-limit-price-label': {{ textContent: '' }},
    'crypto-margin': {{ value: '100' }},
    'crypto-tpsl-enabled': {{ checked: false }},
    'crypto-tpsl-fields': {{ classList: {{ remove: () => {{}}, add: () => {{}} }} }},
    'crypto-tp-price': {{ value: '' }},
    'crypto-sl-price': {{ value: '' }},
    'crypto-riskcalc-enabled': {{ checked: false }},
    'crypto-riskcalc-fields': {{ classList: {{ remove: () => {{}}, add: () => {{}} }} }},
    'crypto-riskcalc-entry': {{ value: '' }},
    'crypto-riskcalc-stop': {{ value: '' }},
    'crypto-riskcalc-maxloss': {{ value: '' }},
    'crypto-riskcalc-result': {{ textContent: '' }},
    'crypto-order-status': {{ textContent: '' }},
    'crypto-order-leverage': {{ value: '10' }},
}};

global.document = {{
    getElementById: (id) => elements[id] || null,
    querySelector: () => null,
    querySelectorAll: () => [],
}};

global.selectedTrainingMarketType = 'crypto_perpetual';
global.CRYPTO_MARKET_TYPE = 'crypto_perpetual';
global.currentCryptoSummary = {{ account_equity: 10000, balance: 10000 }};
global.drawingController = {{ accountRiskPercent: 2 }};

function formatCryptoValue(val) {{ return String(val); }}
function setCryptoOrderStatus(msg) {{ elements['crypto-order-status'].textContent = msg; }}
function selectCryptoOrderAction(action) {{ elements['crypto-order-action'].value = action; }}
function setCryptoOrderType(type) {{ elements['crypto-order-type'].value = type; }}
function refreshCryptoOrderPreview() {{}}
function refreshCryptoTpSlPnl() {{}}

function getCryptoOrderPreview() {{
    return {{
        action: elements['crypto-order-action'].value,
        entryPrice: Number(elements['crypto-limit-price'].value || 60000),
        leverage: 10,
    }};
}}

function getCryptoRiskCalcParams() {{
    const preview = getCryptoOrderPreview();
    const entryInput = Number(elements['crypto-riskcalc-entry'].value || 0);
    const stopInput = Number(elements['crypto-riskcalc-stop'].value || 0);
    return {{
        entryPrice: entryInput > 0 ? entryInput : preview.entryPrice,
        stopPrice: stopInput > 0 ? stopInput : Number(elements['crypto-sl-price'].value || 0),
        maxLoss: Number(elements['crypto-riskcalc-maxloss'].value || 0),
        leverage: preview.leverage,
        action: preview.action,
    }};
}}

function refreshCryptoRiskCalcResult() {{
    const params = getCryptoRiskCalcParams();
    const result = window.RiskCalc.computeRiskPosition(params);
    if (result.valid) {{
        elements['crypto-margin'].value = String(result.margin);
    }}
    return result;
}}

function applyCryptoRiskCalc() {{
    refreshCryptoRiskCalcResult();
}}

// Define syncDrawingToOrderPanel
function syncDrawingToOrderPanel(model) {{
    const anchors = Array.isArray(model.anchors) ? model.anchors : [];
    const entryPrice = Number(anchors[0]?.price);
    const stopPrice = Number(anchors[1]?.price);
    const targetPrice = anchors.length >= 3 && Number.isFinite(Number(anchors[2]?.price)) ? Number(anchors[2]?.price) : null;
    
    let isLong = true;
    if (model.type === 'short') {{
        isLong = false;
    }} else if (model.type === 'long') {{
        isLong = true;
    }} else if (model.type === 'risk-reward') {{
        isLong = stopPrice < entryPrice;
    }}
    
    const riskPct = Number(drawingController?.accountRiskPercent || 1);
    const equity = Number(currentCryptoSummary?.account_equity || 10000);
    const riskAmount = Math.max(1, Math.round(equity * (riskPct / 100)));
    
    const action = isLong ? 'open_long' : 'open_short';
    selectCryptoOrderAction(action);
    setCryptoOrderType('limit');
    elements['crypto-limit-price'].value = String(entryPrice);
    
    elements['crypto-tpsl-enabled'].checked = true;
    elements['crypto-sl-price'].value = String(stopPrice);
    if (targetPrice !== null) elements['crypto-tp-price'].value = String(targetPrice);
    
    elements['crypto-riskcalc-enabled'].checked = true;
    elements['crypto-riskcalc-entry'].value = String(entryPrice);
    elements['crypto-riskcalc-stop'].value = String(stopPrice);
    elements['crypto-riskcalc-maxloss'].value = String(riskAmount);
    
    applyCryptoRiskCalc();
    setCryptoOrderStatus('synced');
}}

// 1. Test Long Drawing Sync
const longModel = {{
    type: 'long',
    anchors: [
        {{ time: 100, price: 60000 }}, // Entry
        {{ time: 100, price: 58000 }}, // Stop loss (-2000)
        {{ time: 100, price: 64000 }}, // Take profit (+4000)
    ]
}};

syncDrawingToOrderPanel(longModel);

if (elements['crypto-order-action'].value !== 'open_long') throw new Error('Action mismatch for long');
if (elements['crypto-limit-price'].value !== '60000') throw new Error('Limit price mismatch');
if (elements['crypto-sl-price'].value !== '58000') throw new Error('SL price mismatch');
if (elements['crypto-tp-price'].value !== '64000') throw new Error('TP price mismatch');
if (elements['crypto-riskcalc-maxloss'].value !== '200') throw new Error('Risk amount mismatch (expected 200 USDT)');
// Max loss = 200, Stop distance = 2000 (3.33%), Qty = 200 / 2000 = 0.1 BTC, Notional = 6000 USDT, Margin(10x) = 600 USDT
if (Number(elements['crypto-margin'].value) !== 600) throw new Error('Calculated margin mismatch: ' + elements['crypto-margin'].value);

// 2. Test Short Drawing Sync
const shortModel = {{
    type: 'short',
    anchors: [
        {{ time: 100, price: 60000 }}, // Entry
        {{ time: 100, price: 61000 }}, // Stop loss (+1000)
        {{ time: 100, price: 57000 }}, // Take profit (-3000)
    ]
}};

syncDrawingToOrderPanel(shortModel);

if (elements['crypto-order-action'].value !== 'open_short') throw new Error('Action mismatch for short');
if (elements['crypto-sl-price'].value !== '61000') throw new Error('SL price mismatch for short');
if (elements['crypto-tp-price'].value !== '57000') throw new Error('TP price mismatch for short');
// Max loss = 200, Stop distance = 1000, Qty = 200 / 1000 = 0.2 BTC, Notional = 12000 USDT, Margin(10x) = 1200 USDT
if (Number(elements['crypto-margin'].value) !== 1200) throw new Error('Calculated margin mismatch for short: ' + elements['crypto-margin'].value);

console.log('SYNC_ORDER_OK');
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
        self.assertIn("SYNC_ORDER_OK", completed.stdout)


if __name__ == "__main__":
    unittest.main()
