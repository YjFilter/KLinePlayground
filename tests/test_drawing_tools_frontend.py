"""Runtime contracts for the standalone chart drawing tools module."""

from __future__ import annotations

import json
import subprocess
import textwrap
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DRAWING_TOOLS_PATH = PROJECT_ROOT / "frontend" / "js" / "drawing_tools.js"


def run_node(script: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["node", "-e", textwrap.dedent(script)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


class DrawingMathRuntimeTests(unittest.TestCase):
    def test_fibonacci_defaults_interpolation_and_reverse_mode(self):
        script = f"""
        const drawing = require({json.dumps(str(DRAWING_TOOLS_PATH))});
        const assert = require('node:assert/strict');
        assert.deepEqual(
          drawing.DEFAULT_FIBONACCI_LEVELS.map(level => level.value),
          [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1, 1.382, 1.618, 2]
        );
        assert.deepEqual(
          drawing.DEFAULT_FIBONACCI_LEVELS.map(level => level.colorGroup),
          ['purple', 'purple', 'blue', 'blue', 'blue', 'pink', 'pink', 'green', 'green', 'orange']
        );
        assert.deepEqual(
          drawing.DEFAULT_FIBONACCI_LEVELS.map(level => level.label),
          ['0', '23.6', '38.2', '50', '61.8', '78.6', '100', '138.2', '161.8', '200']
        );
        assert.ok(drawing.DEFAULT_FIBONACCI_LEVELS.every(level => /^#[0-9a-f]{{6}}$/i.test(level.color)));
        const normal = drawing.calculateFibonacciLevels(100, 200);
        assert.equal(normal.find(level => level.value === 0.5).price, 150);
        assert.equal(normal.find(level => level.value === 0.236).price, 123.6);
        const reverse = drawing.calculateFibonacciLevels(100, 200, {{reverse: true}});
        assert.equal(reverse.find(level => level.value === 0).price, 200);
        assert.equal(reverse.find(level => level.value === 1).price, 100);
        """
        completed = run_node(script)
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_ruler_metrics_cover_delta_percent_bars_duration_and_volume(self):
        script = f"""
        const drawing = require({json.dumps(str(DRAWING_TOOLS_PATH))});
        const assert = require('node:assert/strict');
        const bull = drawing.calculateRulerMetrics(
          {{time: 1000, price: 10}},
          {{time: 1180, price: 12.5}},
          {{
            startIndex: 4,
            endIndex: 9,
            bars: [
              {{time: 1000, open: 10, close: 11, volume: 1000}},
              {{time: 1060, open: 11, close: 10, volume: 2000}},
              {{time: 1120, open: 10, close: 10, volume: 3000}},
              {{time: 1180, open: 10, close: 12, volume: 4000}},
            ],
          }}
        );
        assert.deepEqual(bull, {{
          priceDelta: 2.5,
          absolutePriceChange: 2.5,
          percentChange: 25,
          barCount: 4,
          bullishCount: 2,
          bearishCount: 1,
          totalVolume: 10000,
          duration: 180,
          elapsedDuration: 180,
          direction: 'bull',
        }});
        const bear = drawing.calculateRulerMetrics(
          {{time: 1180, price: 12.5}},
          {{time: 1000, price: 10}},
          {{barCount: 5}}
        );
        assert.equal(bear.priceDelta, -2.5);
        assert.equal(bear.percentChange, -20);
        assert.equal(bear.barCount, 5);
        assert.equal(bear.duration, 180);
        assert.equal(bear.elapsedDuration, 180);
        assert.equal(bear.absolutePriceChange, 2.5);
        assert.equal(bear.bullishCount, 0);
        assert.equal(bear.bearishCount, 0);
        assert.equal(bear.totalVolume, 0);
        assert.equal(bear.direction, 'bear');
        """
        completed = run_node(script)
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_long_and_short_risk_reward_require_valid_three_point_ordering(self):
        script = f"""
        const drawing = require({json.dumps(str(DRAWING_TOOLS_PATH))});
        const assert = require('node:assert/strict');
        const longResult = drawing.calculateRiskReward('long', 100, 95, 115);
        assert.deepEqual(longResult, {{
          side: 'long', entry: 100, stop: 95, target: 115,
          risk: 5, reward: 15, riskPercent: 5, rewardPercent: 15,
          rewardRiskRatio: 3,
        }});
        const shortResult = drawing.calculateRiskReward('short', 100, 104, 92);
        assert.equal(shortResult.risk, 4);
        assert.equal(shortResult.reward, 8);
        assert.equal(shortResult.rewardRiskRatio, 2);
        const aliasResult = drawing.calculateRiskReward(
          'long-position', 100, 95, 115, {{accountRiskAmount: 250}}
        );
        assert.equal(aliasResult.side, 'long');
        assert.equal(aliasResult.accountRiskAmount, 250);
        const shortAlias = drawing.createDrawingModel('short-position', [
          {{time: 1, price: 100}}, {{time: 2, price: 105}}, {{time: 2, price: 90}}
        ]);
        assert.equal(shortAlias.type, 'short');
        const accountRiskModel = drawing.createDrawingModel('long-position', [
          {{time: 1, price: 100}}, {{time: 2, price: 95}}, {{time: 2, price: 115}}
        ], {{accountRiskAmount: 300}});
        assert.equal(accountRiskModel.options.accountRiskAmount, 300);
        assert.throws(() => drawing.calculateRiskReward('long', 100, 101, 115));
        assert.throws(() => drawing.calculateRiskReward('short', 100, 99, 92));
        assert.throws(() => drawing.calculateRiskReward('sideways', 100, 95, 115));
        """
        completed = run_node(script)
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_models_validate_and_serialize_timestamp_price_anchors(self):
        script = f"""
        const drawing = require({json.dumps(str(DRAWING_TOOLS_PATH))});
        const assert = require('node:assert/strict');
        const source = {{time: 1700000000, price: 12.34}};
        const model = drawing.createDrawingModel('trend', [source, {{time: 1700000060, price: 13}}]);
        source.price = 999;
        assert.equal(model.anchors[0].price, 12.34);
        assert.equal(model.type, 'trend');
        assert.equal(model.locked, false);
        assert.equal(model.hidden, false);
        const serialized = drawing.serializeDrawing(model);
        assert.deepEqual(serialized.anchors, [
          {{time: 1700000000, price: 12.34}},
          {{time: 1700000060, price: 13}},
        ]);
        assert.throws(() => drawing.createDrawingModel('trend', [{{time: NaN, price: 1}}]));
        assert.throws(() => drawing.createDrawingModel('trend', [{{time: 1, price: Infinity}}]));
        """
        completed = run_node(script)
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_drawing_store_history_uses_immutable_snapshots(self):
        script = f"""
        const drawing = require({json.dumps(str(DRAWING_TOOLS_PATH))});
        const assert = require('node:assert/strict');
        const store = new drawing.DrawingStore();
        const first = drawing.createDrawingModel('horizontal', [{{time: 10, price: 20}}], {{id: 'a'}});
        store.add(first);
        first.anchors[0].price = 999;
        assert.equal(store.get('a').anchors[0].price, 20);
        store.update('a', current => ({{...current, hidden: true}}));
        assert.equal(store.get('a').hidden, true);
        assert.equal(store.undo(), true);
        assert.equal(store.get('a').hidden, false);
        assert.equal(store.redo(), true);
        assert.equal(store.get('a').hidden, true);
        const snapshot = store.snapshot();
        snapshot[0].anchors[0].price = -1;
        assert.equal(store.get('a').anchors[0].price, 20);
        store.remove('a');
        assert.equal(store.size, 0);
        assert.equal(store.undo(), true);
        assert.equal(store.size, 1);
        """
        completed = run_node(script)
        self.assertEqual(completed.returncode, 0, completed.stderr)


class PrimitiveRenderingRuntimeTests(unittest.TestCase):
    def test_ray_endpoint_follows_direction_and_is_shared_by_render_and_hit_test(self):
        script = f"""
        const drawing = require({json.dumps(str(DRAWING_TOOLS_PATH))});
        const assert = require('node:assert/strict');
        const bounds = {{left: 0, top: 0, right: 100, bottom: 100}};
        assert.deepEqual(
          drawing.calculateRayEndpoint({{x: 20, y: 50}}, {{x: 40, y: 60}}, bounds),
          {{x: 100, y: 90}}
        );
        assert.deepEqual(
          drawing.calculateRayEndpoint({{x: 80, y: 50}}, {{x: 60, y: 60}}, bounds),
          {{x: 0, y: 90}}
        );
        assert.deepEqual(
          drawing.calculateRayEndpoint({{x: 50, y: 80}}, {{x: 50, y: 60}}, bounds),
          {{x: 50, y: 0}}
        );
        const operations = [];
        const context = new Proxy({{}}, {{
          get(target, key) {{ return (...args) => operations.push([key, ...args]); }},
          set(target, key, value) {{ target[key] = value; return true; }}
        }});
        const model = drawing.createRayModel([
          {{time: 80, price: 50}}, {{time: 60, price: 60}}
        ], {{selected: false}});
        const primitive = new drawing.DrawingPrimitive(model);
        primitive.attached({{
          chart: {{timeScale: () => ({{timeToCoordinate: value => value}})}},
          series: {{priceToCoordinate: value => value}},
          requestUpdate() {{}},
        }});
        primitive.paneViews()[0].renderer().draw({{useBitmapCoordinateSpace(callback) {{
          callback({{context, horizontalPixelRatio: 1, verticalPixelRatio: 1,
            bitmapSize: {{width: 100, height: 100}}, mediaSize: {{width: 100, height: 100}}}});
        }}}});
        assert.ok(operations.some(op => op[0] === 'lineTo' && op[1] === 0 && op[2] === 90));
        const hit = primitive.hitTest(1, 89.5);
        assert.equal(hit.drawingId, model.id);
        assert.equal(hit.hitKind, 'body');
        """
        completed = run_node(script)
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_primitive_attach_projection_z_order_and_update_requests(self):
        script = f"""
        const drawing = require({json.dumps(str(DRAWING_TOOLS_PATH))});
        const assert = require('node:assert/strict');
        let updates = 0;
        const chart = {{timeScale: () => ({{timeToCoordinate: time => time / 10}})}};
        const series = {{priceToCoordinate: price => 500 - price * 10}};
        const model = drawing.createTrendModel([
          {{time: 100, price: 20}}, {{time: 200, price: 30}}
        ], {{id: 'trend-1'}});
        const primitive = new drawing.DrawingPrimitive(model);
        primitive.attached({{chart, series, requestUpdate: () => updates++}});
        assert.deepEqual(primitive.projectAnchors(), [{{x: 10, y: 300}}, {{x: 20, y: 200}}]);
        assert.equal(primitive.paneViews()[0].zOrder(), 'top');
        assert.equal(primitive.autoscaleInfo(), null);
        primitive.setModel({{...model, selected: true}});
        assert.equal(updates, 1);
        primitive.detached();
        assert.deepEqual(primitive.paneViews(), []);
        """
        completed = run_node(script)
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_renderers_clip_scale_and_draw_every_supported_tool(self):
        script = f"""
        const drawing = require({json.dumps(str(DRAWING_TOOLS_PATH))});
        const assert = require('node:assert/strict');
        const operations = [];
        const context = new Proxy({{
          measureText: text => ({{width: text.length * 6}}),
        }}, {{
          get(target, key) {{
            if (key in target) return target[key];
            return (...args) => operations.push([key, ...args]);
          }},
          set(target, key, value) {{ operations.push(['set', key, value]); target[key] = value; return true; }}
        }});
        const target = {{
          useBitmapCoordinateSpace(callback) {{
            callback({{
              context,
              horizontalPixelRatio: 2,
              verticalPixelRatio: 2,
              bitmapSize: {{width: 800, height: 600}},
              mediaSize: {{width: 400, height: 300}},
            }});
          }}
        }};
        const chart = {{timeScale: () => ({{timeToCoordinate: time => time}})}};
        const series = {{priceToCoordinate: price => 300 - price}};
        const definitions = [
          ['trend', [{{time: 10, price: 10}}, {{time: 100, price: 40}}]],
          ['horizontal', [{{time: 20, price: 50}}]],
          ['ray', [{{time: 10, price: 20}}, {{time: 80, price: 50}}]],
          ['rectangle', [{{time: 20, price: 20}}, {{time: 100, price: 80}}]],
          ['text', [{{time: 30, price: 30}}]],
          ['fibonacci', [{{time: 20, price: 20}}, {{time: 120, price: 100}}]],
          ['fib-trend-time', [{{time: 20, price: 30}}, {{time: 120, price: 90}}]],
          ['ruler', [{{time: 40, price: 30}}, {{time: 140, price: 90}}]],
          ['long', [{{time: 60, price: 100}}, {{time: 140, price: 80}}, {{time: 140, price: 140}}]],
          ['short', [{{time: 60, price: 100}}, {{time: 140, price: 120}}, {{time: 140, price: 60}}]],
        ];
        for (const [type, anchors] of definitions) {{
          const model = drawing.createDrawingModel(type, anchors, {{
            selected: true,
            options: {{text: 'Note'}},
          }});
          const primitive = new drawing.DrawingPrimitive(model);
          primitive.attached({{chart, series, requestUpdate() {{}}}});
          primitive.paneViews()[0].renderer().draw(target);
        }}
        assert.ok(operations.some(operation => operation[0] === 'clip'));
        assert.ok(operations.some(operation => operation[0] === 'arc'));
        assert.ok(operations.some(operation => operation[0] === 'fillText'));
        assert.ok(operations.some(operation => operation[0] === 'fillRect'));
        assert.ok(operations.some(operation => operation[0] === 'lineTo'));
        assert.ok(operations.some(operation => operation[0] === 'setLineDash'));
        assert.ok(operations.some(operation => operation[0] === 'fillText' && String(operation[1]).includes('23.6% (')));
        assert.ok(operations.some(operation => operation[0] === 'set' && operation[1] === 'lineWidth' && operation[2] >= 2));
        """
        completed = run_node(script)
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_hit_regions_respect_selected_locked_and_hidden_state(self):
        script = f"""
        const drawing = require({json.dumps(str(DRAWING_TOOLS_PATH))});
        const assert = require('node:assert/strict');
        const chart = {{timeScale: () => ({{timeToCoordinate: time => time}})}};
        const series = {{priceToCoordinate: price => price}};
        const base = drawing.createTrendModel([
          {{time: 10, price: 10}}, {{time: 110, price: 10}}
        ], {{selected: true}});
        const primitive = new drawing.DrawingPrimitive(base);
        primitive.attached({{chart, series, requestUpdate() {{}}}});
        const anchorHit = primitive.hitTest(10, 10);
        assert.deepEqual(anchorHit, {{
          externalId: `${{base.id}}:anchor:0`, zOrder: 'top', cursorStyle: 'grab',
          itemType: 'primitive', distance: 0, hitTestPriority: 2,
          drawingId: base.id, hitKind: 'anchor', anchorIndex: 0,
        }});
        const bodyHit = primitive.hitTest(60, 12);
        assert.equal(bodyHit.externalId, `${{base.id}}:body`);
        assert.equal(bodyHit.zOrder, 'top');
        assert.equal(bodyHit.cursorStyle, 'move');
        assert.equal(bodyHit.itemType, 'primitive');
        assert.equal(bodyHit.hitTestPriority, 1);
        assert.equal(bodyHit.distance, 2);
        primitive.setModel({{...base, locked: true}});
        const lockedHit = primitive.hitTest(10, 10);
        assert.equal(lockedHit.externalId, `${{base.id}}:body`);
        assert.equal(lockedHit.cursorStyle, 'default');
        assert.equal(lockedHit.locked, true);
        primitive.setModel({{...base, hidden: true}});
        assert.equal(primitive.hitTest(60, 10), null);
        assert.deepEqual(primitive.paneViews(), []);
        """
        completed = run_node(script)
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_offscreen_projection_preserves_original_anchor_indices(self):
        script = f"""
        const drawing = require({json.dumps(str(DRAWING_TOOLS_PATH))});
        const assert = require('node:assert/strict');
        const chart = {{timeScale: () => ({{timeToCoordinate: time => time === 10 ? null : time}})}};
        const series = {{priceToCoordinate: price => price}};
        const model = drawing.createTrendModel([
          {{time: 10, price: 10}}, {{time: 110, price: 20}}
        ], {{selected: true}});
        const primitive = new drawing.DrawingPrimitive(model);
        primitive.attached({{chart, series, requestUpdate() {{}}}});
        assert.deepEqual(primitive.projectAnchors(), [null, {{x: 110, y: 20}}]);
        primitive.setBars([{{time: 12}}, {{time: 110}}]);
        assert.deepEqual(primitive.projectAnchors(), [{{x: 12, y: 10}}, {{x: 110, y: 20}}]);
        const hit = primitive.hitTest(110, 20);
        assert.equal(hit.anchorIndex, 1);
        assert.equal(hit.externalId, `${{model.id}}:anchor:1`);
        """
        completed = run_node(script)
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_ruler_renderer_uses_tradingview_card_guides_arrow_and_fixed_teal_style(self):
        script = f"""
        const drawing = require({json.dumps(str(DRAWING_TOOLS_PATH))});
        const assert = require('node:assert/strict');
        function render(endPrice) {{
          const operations = [];
          const context = new Proxy({{measureText: text => ({{width: text.length * 6}})}}, {{
            get(target, key) {{
              if (key in target) return target[key];
              return (...args) => operations.push([key, ...args]);
            }},
            set(target, key, value) {{ operations.push(['set', key, value]); target[key] = value; return true; }}
          }});
          const model = drawing.createRulerModel([
            {{time: 1000, price: 10}}, {{time: 1180, price: endPrice}}
          ]);
          const primitive = new drawing.DrawingPrimitive(model);
          primitive.setBars([
            {{time: 1000, open: 10, close: 11, volume: 1_000_000_000}},
            {{time: 1060, open: 11, close: 10, volume: 2_000_000_000}},
            {{time: 1180, open: 10, close: endPrice, volume: 3_000_000_000}},
          ]);
          primitive.attached({{
            chart: {{timeScale: () => ({{timeToCoordinate: time => time - 990}})}},
            series: {{priceToCoordinate: price => 200 - price}},
            requestUpdate() {{}},
          }});
          primitive.paneViews()[0].renderer().draw({{useBitmapCoordinateSpace(callback) {{
            callback({{context, horizontalPixelRatio: 1, verticalPixelRatio: 1,
              bitmapSize: {{width: 400, height: 300}}, mediaSize: {{width: 400, height: 300}}}});
          }}}});
          return operations;
        }}
        const bull = render(12.5);
        const bear = render(8);
        for (const operations of [bull, bear]) {{
          assert.ok(operations.some(op => op[0] === 'set' && op[1] === 'fillStyle' && op[2] === 'rgba(38, 166, 154, 0.18)'));
          assert.ok(operations.some(op => op[0] === 'setLineDash'));
          assert.ok(operations.filter(op => op[0] === 'arc').length >= 2);
          const labels = operations.filter(op => op[0] === 'fillText').map(op => String(op[1]));
          assert.equal(labels.length, 3);
          assert.ok(labels.some(text => text.includes('3分钟')));
          assert.equal(labels.some(text => text.includes('成交量')), false);
        }}
        assert.ok(bull.some(op => op[0] === 'fillText' && String(op[1]).includes('3柱 (2阳1阴)')));
        assert.ok(bear.some(op => op[0] === 'fillText' && String(op[1]).includes('3柱 (1阳2阴)')));
        assert.ok(bull.some(op => op[0] === 'fillText' && String(op[1]).startsWith('2.5 (25.00%)')));
        assert.ok(bear.some(op => op[0] === 'fillText' && String(op[1]).startsWith('-2 (-20.00%)')));
        const hasCenterGuide = bull.some((op, index) => op[0] === 'moveTo' && op[1] === 100 && op[2] === 190
          && bull[index + 1]?.[0] === 'lineTo' && bull[index + 1][1] === 100 && bull[index + 1][2] === 187.5);
        assert.equal(hasCenterGuide, true);
        const cardColorIndex = bull.findIndex(op => op[0] === 'set' && op[1] === 'fillStyle'
          && op[2] === 'rgba(10, 63, 66, 0.94)');
        const card = bull.slice(cardColorIndex + 1).find(op => op[0] === 'fillRect');
        assert.ok(card[2] + card[4] <= 187.5);
        """
        completed = run_node(script)
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_ruler_information_card_is_clamped_inside_the_canvas(self):
        script = f"""
        const drawing = require({json.dumps(str(DRAWING_TOOLS_PATH))});
        const assert = require('node:assert/strict');
        const operations = [];
        const context = new Proxy({{
          font: '12px sans-serif',
          measureText(text) {{
            const size = Number.parseFloat(this.font) || 12;
            return {{width: text.length * size * 0.5}};
          }}
        }}, {{
          get(target, key) {{ if (key in target) return target[key]; return (...args) => operations.push([key, ...args]); }},
          set(target, key, value) {{ operations.push(['set', key, value]); target[key] = value; return true; }}
        }});
        const primitive = new drawing.DrawingPrimitive(drawing.createRulerModel([
          {{time: 1150, price: 82}}, {{time: 1190, price: 78}}
        ]));
        primitive.setBars([{{time: 1150, open: 82, close: 80, volume: 1000}}]);
        primitive.attached({{
          chart: {{timeScale: () => ({{timeToCoordinate: time => time - 1000}})}},
          series: {{priceToCoordinate: price => 210 - price}}, requestUpdate() {{}},
        }});
        primitive.paneViews()[0].renderer().draw({{useBitmapCoordinateSpace(callback) {{
          callback({{context, horizontalPixelRatio: 1, verticalPixelRatio: 1,
            bitmapSize: {{width: 90, height: 70}}, mediaSize: {{width: 90, height: 70}}}});
        }}}});
        const cardColorIndex = operations.findIndex(op => op[0] === 'set' && op[1] === 'fillStyle'
          && op[2] === 'rgba(10, 63, 66, 0.94)');
        const card = operations.slice(cardColorIndex + 1).find(op => op[0] === 'fillRect');
        assert.ok(card);
        assert.ok(card[1] >= 0 && card[2] >= 0);
        assert.ok(card[1] + card[3] <= 90);
        assert.ok(card[2] + card[4] <= 70);
        """
        completed = run_node(script)
        self.assertEqual(completed.returncode, 0, completed.stderr)


    def test_risk_renderer_only_shows_compact_price_labels_while_hovered(self):
        script = f"""
        const drawing = require({json.dumps(str(DRAWING_TOOLS_PATH))});
        const assert = require('node:assert/strict');
        function render(hovered) {{
          const operations = [];
          const context = new Proxy({{measureText: text => ({{width: text.length * 7}})}}, {{
            get(target, key) {{ if (key in target) return target[key]; return (...args) => operations.push([key, ...args]); }},
            set(target, key, value) {{ operations.push(['set', key, value]); target[key] = value; return true; }}
          }});
          const model = drawing.createDrawingModel('short-position', [
            {{time: 10, price: 117500}}, {{time: 200, price: 117932.72}}, {{time: 200, price: 116850.92}}
          ], {{accountSize: 10000, accountRiskAmount: 200, positionSize: 0.158234}});
          const primitive = new drawing.DrawingPrimitive({{...model, hovered}});
          primitive.attached({{
            chart: {{timeScale: () => ({{timeToCoordinate: value => value}})}},
            series: {{priceToCoordinate: value => 220 - ((value - 116000) / 10)}}, requestUpdate() {{}},
          }});
          primitive.paneViews()[0].renderer().draw({{useBitmapCoordinateSpace(callback) {{
            callback({{context, horizontalPixelRatio: 1, verticalPixelRatio: 1,
              bitmapSize: {{width: 400, height: 300}}, mediaSize: {{width: 400, height: 300}}}});
          }}}});
          return operations;
        }}
        const hidden = render(false);
        assert.equal(hidden.filter(op => op[0] === 'fillText').length, 0);
        assert.ok(hidden.some(op => op[0] === 'set' && op[1] === 'strokeStyle' && op[2] === '#ef5350'));
        assert.ok(hidden.some(op => op[0] === 'set' && op[1] === 'strokeStyle' && op[2] === '#26a69a'));

        const visible = render(true);
        const labels = visible.filter(op => op[0] === 'fillText').map(op => String(op[1]));
        assert.equal(labels.length, 3);
        assert.ok(labels.some(label => label.includes('止损 117932.72 · -0.37%')));
        assert.ok(labels.some(label => label.includes('入场 117500 · RR 1.50')));
        assert.ok(labels.some(label => label.includes('止盈 116850.92 · +0.55%')));
        assert.equal(labels.some(label => label.includes('账户') || label.includes('仓量')
          || label.includes('未开仓')), false);
        """
        completed = run_node(script)
        self.assertEqual(completed.returncode, 0, completed.stderr)

class DrawingControllerRuntimeTests(unittest.TestCase):
    def test_risk_labels_follow_pointer_hover_and_leave(self):
        script = f"""
        const drawing = require({json.dumps(str(DRAWING_TOOLS_PATH))});
        const assert = require('node:assert/strict');
        class Target {{
          constructor() {{ this.listeners = new Map(); }}
          addEventListener(type, handler) {{ this.listeners.set(type, handler); }}
          removeEventListener(type) {{ this.listeners.delete(type); }}
          dispatch(type, event = {{}}) {{ this.listeners.get(type)?.({{pointerId: 21, preventDefault() {{}}, ...event}}); }}
          getBoundingClientRect() {{ return {{left: 0, top: 0}}; }}
        }}
        const element = new Target();
        const chart = {{timeScale: () => ({{timeToCoordinate: value => value, coordinateToTime: value => value}})}};
        const series = {{
          priceToCoordinate: value => value,
          coordinateToPrice: value => value,
          attachPrimitive(primitive) {{ primitive.attached({{chart, series, requestUpdate() {{}}}}); }},
          detachPrimitive() {{}},
        }};
        const store = new drawing.DrawingStore([
          drawing.createDrawingModel('long', [
            {{time: 10, price: 100}}, {{time: 100, price: 90}}, {{time: 100, price: 115}}
          ], {{id: 'risk'}})
        ]);
        const controller = new drawing.DrawingController({{
          chart, series, element, keyTarget: new Target(), store,
        }});
        assert.equal(controller._primitives.get('risk').model().hovered, false);
        element.dispatch('pointermove', {{clientX: 50, clientY: 100}});
        assert.equal(controller._primitives.get('risk').model().hovered, true);
        element.dispatch('pointermove', {{clientX: 200, clientY: 200}});
        assert.equal(controller._primitives.get('risk').model().hovered, false);
        element.dispatch('pointermove', {{clientX: 50, clientY: 100}});
        element.dispatch('pointerleave');
        assert.equal(controller._primitives.get('risk').model().hovered, false);
        """
        completed = run_node(script)
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_main_callback_aliases_and_account_provider_populate_risk_model(self):
        script = f"""
        const drawing = require({json.dumps(str(DRAWING_TOOLS_PATH))});
        const assert = require('node:assert/strict');
        class Target {{
          constructor() {{ this.listeners = new Map(); }}
          addEventListener(type, handler) {{ this.listeners.set(type, handler); }}
          removeEventListener(type) {{ this.listeners.delete(type); }}
          dispatch(type, event) {{ this.listeners.get(type)?.({{pointerId: 9, preventDefault() {{}}, ...event}}); }}
          setPointerCapture() {{}}
          releasePointerCapture() {{}}
          getBoundingClientRect() {{ return {{left: 0, top: 0}}; }}
        }}
        const element = new Target();
        const keyTarget = new Target();
        const interactions = [];
        const tools = [];
        const chart = {{timeScale: () => ({{timeToCoordinate: v => v, coordinateToTime: v => v}})}};
        const series = {{priceToCoordinate: v => 200 - v, coordinateToPrice: v => 200 - v,
          attachPrimitive(primitive) {{ primitive.attached({{chart, series, requestUpdate() {{}}}}); }}, detachPrimitive() {{}}}};
        const controller = new drawing.DrawingController({{
          chart, series, element, keyTarget,
          accountSizeProvider: () => 10000,
          onInteractionChange: active => interactions.push(active),
          onToolChange: tool => tools.push(tool),
        }});
        controller.activateTool('long');
        element.dispatch('pointerdown', {{clientX: 10, clientY: 100}});
        element.dispatch('pointerup', {{clientX: 50, clientY: 110}});
        const model = controller.store.snapshot()[0];
        assert.equal(model.options.accountSize, 10000);
        assert.equal(model.options.accountRiskAmount, 100);
        assert.equal(model.options.positionSize, 10);
        assert.deepEqual(interactions, [true, false]);
        assert.deepEqual(tools, ['long', null]);
        """
        completed = run_node(script)
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_two_point_tool_click_without_drag_does_not_commit(self):
        script = f"""
        const drawing = require({json.dumps(str(DRAWING_TOOLS_PATH))});
        const assert = require('node:assert/strict');
        class Target {{
          constructor() {{ this.listeners = new Map(); }}
          addEventListener(type, handler) {{ this.listeners.set(type, handler); }}
          removeEventListener(type) {{ this.listeners.delete(type); }}
          dispatch(type, event) {{ this.listeners.get(type)?.({{pointerId: 10, preventDefault() {{}}, ...event}}); }}
          setPointerCapture() {{}}
          releasePointerCapture() {{}}
          getBoundingClientRect() {{ return {{left: 0, top: 0}}; }}
        }}
        const element = new Target();
        const keyTarget = new Target();
        const chart = {{timeScale: () => ({{timeToCoordinate: v => v, coordinateToTime: v => v}})}};
        const series = {{priceToCoordinate: v => v, coordinateToPrice: v => v,
          attachPrimitive(primitive) {{ primitive.attached({{chart, series, requestUpdate() {{}}}}); }}, detachPrimitive() {{}}}};
        const controller = new drawing.DrawingController({{chart, series, element, keyTarget}});
        controller.activateTool('rectangle');
        element.dispatch('pointerdown', {{clientX: 20, clientY: 30}});
        assert.ok(controller._draftPrimitive);
        element.dispatch('pointerup', {{clientX: 20, clientY: 30}});
        assert.equal(controller.store.size, 0);
        assert.equal(controller._draftPrimitive, null);
        """
        completed = run_node(script)
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_two_point_tool_drag_previews_draft_and_commits_on_release(self):
        script = f"""
        const drawing = require({json.dumps(str(DRAWING_TOOLS_PATH))});
        const assert = require('node:assert/strict');
        class Target {{
          constructor() {{ this.listeners = new Map(); }}
          addEventListener(type, handler) {{ this.listeners.set(type, handler); }}
          removeEventListener(type) {{ this.listeners.delete(type); }}
          dispatch(type, event) {{ this.listeners.get(type)?.({{pointerId: 4, preventDefault() {{}}, ...event}}); }}
          setPointerCapture() {{}}
          releasePointerCapture() {{}}
          getBoundingClientRect() {{ return {{left: 10, top: 20}}; }}
        }}
        const element = new Target();
        const keyTarget = new Target();
        const attached = [];
        const chart = {{timeScale: () => ({{timeToCoordinate: value => value + 10, coordinateToTime: value => value - 10}})}};
        const series = {{
          priceToCoordinate: value => value + 20, coordinateToPrice: value => value - 20,
          attachPrimitive(primitive) {{ attached.push(primitive); primitive.attached({{chart, series, requestUpdate() {{}}}}); }},
          detachPrimitive(primitive) {{ attached.splice(attached.indexOf(primitive), 1); }},
        }};
        const controller = new drawing.DrawingController({{chart, series, element, keyTarget}});
        controller.activateTool('trend');
        element.dispatch('pointerdown', {{clientX: 40, clientY: 70}});
        assert.equal(controller.store.size, 0);
        assert.ok(controller._draftPrimitive);
        assert.equal(attached.length, 1);
        element.dispatch('pointermove', {{clientX: 90, clientY: 110}});
        assert.deepEqual(controller._draftPrimitive.model().anchors, [
          {{time: 20, price: 30}}, {{time: 70, price: 70}}
        ]);
        assert.equal(controller.store.size, 0);
        element.dispatch('pointerup', {{clientX: 90, clientY: 110}});
        assert.equal(controller.store.size, 1);
        assert.deepEqual(controller.store.snapshot()[0].anchors, [
          {{time: 20, price: 30}}, {{time: 70, price: 70}}
        ]);
        assert.equal(controller._draftPrimitive, null);
        assert.equal(attached.length, 1);
        """
        completed = run_node(script)
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_risk_tools_create_three_anchors_in_one_drag_with_fixed_ratio(self):
        script = f"""
        const drawing = require({json.dumps(str(DRAWING_TOOLS_PATH))});
        const assert = require('node:assert/strict');
        class Target {{
          constructor() {{ this.listeners = new Map(); }}
          addEventListener(type, handler) {{ this.listeners.set(type, handler); }}
          removeEventListener(type) {{ this.listeners.delete(type); }}
          dispatch(type, event) {{ this.listeners.get(type)?.({{pointerId: 5, preventDefault() {{}}, ...event}}); }}
          setPointerCapture() {{}}
          releasePointerCapture() {{}}
          getBoundingClientRect() {{ return {{left: 0, top: 0}}; }}
        }}
        const element = new Target();
        const keyTarget = new Target();
        const chart = {{timeScale: () => ({{timeToCoordinate: v => v, coordinateToTime: v => v}})}};
        const series = {{priceToCoordinate: v => 200 - v, coordinateToPrice: v => 200 - v,
          attachPrimitive(primitive) {{ primitive.attached({{chart, series, requestUpdate() {{}}}}); }}, detachPrimitive() {{}}}};
        const controller = new drawing.DrawingController({{chart, series, element, keyTarget}});
        controller.activateTool('long-position');
        element.dispatch('pointerdown', {{clientX: 10, clientY: 100}});
        element.dispatch('pointermove', {{clientX: 60, clientY: 110}});
        assert.deepEqual(controller._draftPrimitive.model().anchors, [
          {{time: 10, price: 100}}, {{time: 60, price: 90}}, {{time: 60, price: 115}}
        ]);
        element.dispatch('pointerup', {{clientX: 60, clientY: 110}});
        const longModel = controller.store.snapshot()[0];
        assert.equal(drawing.calculateRiskReward('long', ...longModel.anchors.map(anchor => anchor.price)).rewardRiskRatio, 1.5);
        controller.activateTool('short-position');
        element.dispatch('pointerdown', {{clientX: 20, clientY: 100}});
        element.dispatch('pointerup', {{clientX: 70, clientY: 115}});
        const shortModel = controller.store.snapshot()[1];
        assert.deepEqual(shortModel.anchors, [
          {{time: 20, price: 100}}, {{time: 70, price: 110}}, {{time: 70, price: 85}}
        ]);
        assert.equal(drawing.calculateRiskReward('short', ...shortModel.anchors.map(anchor => anchor.price)).rewardRiskRatio, 1.5);
        """
        completed = run_node(script)
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_pointermove_is_raf_coalesced_and_snaps_time_and_ohlc_unless_alt(self):
        script = f"""
        const drawing = require({json.dumps(str(DRAWING_TOOLS_PATH))});
        const assert = require('node:assert/strict');
        class Target {{
          constructor() {{ this.listeners = new Map(); }}
          addEventListener(type, handler) {{ this.listeners.set(type, handler); }}
          removeEventListener(type) {{ this.listeners.delete(type); }}
          dispatch(type, event) {{ this.listeners.get(type)?.({{pointerId: 6, preventDefault() {{}}, ...event}}); }}
          setPointerCapture() {{}}
          releasePointerCapture() {{}}
          getBoundingClientRect() {{ return {{left: 0, top: 0}}; }}
        }}
        const frames = [];
        const element = new Target();
        const keyTarget = new Target();
        const chart = {{timeScale: () => ({{timeToCoordinate: v => v, coordinateToTime: v => v}})}};
        const series = {{priceToCoordinate: v => v, coordinateToPrice: v => v,
          attachPrimitive(primitive) {{ primitive.attached({{chart, series, requestUpdate() {{}}}}); }}, detachPrimitive() {{}}}};
        const controller = new drawing.DrawingController({{
          chart, series, element, keyTarget,
          bars: [{{time: 100, open: 50, high: 60, low: 40, close: 55}}],
          requestAnimationFrame(callback) {{ frames.push(callback); return frames.length; }}, cancelAnimationFrame() {{}},
        }});
        controller.activateTool('trend');
        element.dispatch('pointerdown', {{clientX: 96, clientY: 53}});
        element.dispatch('pointermove', {{clientX: 104, clientY: 58}});
        element.dispatch('pointermove', {{clientX: 106, clientY: 56}});
        assert.equal(frames.length, 1);
        assert.deepEqual(controller._draftPrimitive.model().anchors[1], {{time: 100, price: 55}});
        frames.shift()();
        assert.deepEqual(controller._draftPrimitive.model().anchors[1], {{time: 100, price: 55}});
        element.dispatch('pointerup', {{clientX: 106, clientY: 56, altKey: true}});
        assert.deepEqual(controller.store.snapshot()[0].anchors[1], {{time: 106, price: 56}});
        """
        completed = run_node(script)
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_drawings_can_be_created_and_projected_in_future_whitespace(self):
        script = f"""
        const drawing = require({json.dumps(str(DRAWING_TOOLS_PATH))});
        const assert = require('node:assert/strict');
        class Target {{
          constructor() {{ this.listeners = new Map(); }}
          addEventListener(type, handler) {{ this.listeners.set(type, handler); }}
          removeEventListener(type) {{ this.listeners.delete(type); }}
          dispatch(type, event) {{ this.listeners.get(type)?.({{pointerId: 12, preventDefault() {{}}, ...event}}); }}
          setPointerCapture() {{}}
          releasePointerCapture() {{}}
          getBoundingClientRect() {{ return {{left: 0, top: 0}}; }}
        }}
        const bars = [
          {{time: 1000, open: 10, high: 12, low: 9, close: 11}},
          {{time: 1060, open: 11, high: 13, low: 10, close: 12}},
        ];
        const knownCoordinates = new Map([[1000, 0], [1060, 10]]);
        const timeScale = {{
          timeToCoordinate: time => knownCoordinates.get(time) ?? null,
          coordinateToTime: coordinate => coordinate <= 10 ? 1000 + (coordinate * 6) : null,
          coordinateToLogical: coordinate => coordinate / 10,
          logicalToCoordinate: logical => logical * 10,
        }};
        const chart = {{timeScale: () => timeScale}};
        const series = {{
          priceToCoordinate: price => price,
          coordinateToPrice: coordinate => coordinate,
          attachPrimitive(primitive) {{ primitive.attached({{chart, series, requestUpdate() {{}}}}); }},
          detachPrimitive() {{}},
        }};
        const element = new Target();
        const controller = new drawing.DrawingController({{
          chart, series, element, keyTarget: new Target(), bars,
        }});
        controller.activateTool('trend');
        element.dispatch('pointerdown', {{clientX: 30, clientY: 40}});
        element.dispatch('pointermove', {{clientX: 50, clientY: 60}});
        element.dispatch('pointerup', {{clientX: 50, clientY: 60}});

        assert.equal(controller.store.size, 1);
        assert.deepEqual(controller.store.snapshot()[0].anchors, [
          {{time: 1180, price: 40}}, {{time: 1300, price: 60}}
        ]);
        assert.deepEqual(controller._primitives.values().next().value.projectAnchors(), [
          {{x: 30, y: 40}}, {{x: 50, y: 60}}
        ]);
        """
        completed = run_node(script)
        self.assertEqual(completed.returncode, 0, completed.stderr)
    def test_future_whitespace_drawing_supports_anchor_and_body_drag(self):
        script = f"""
        const drawing = require({json.dumps(str(DRAWING_TOOLS_PATH))});
        const assert = require('node:assert/strict');
        class Target {{
          constructor() {{ this.listeners = new Map(); }}
          addEventListener(type, handler) {{ this.listeners.set(type, handler); }}
          removeEventListener(type) {{ this.listeners.delete(type); }}
          dispatch(type, event) {{ this.listeners.get(type)?.({{pointerId: 13, preventDefault() {{}}, ...event}}); }}
          setPointerCapture() {{}}
          releasePointerCapture() {{}}
          getBoundingClientRect() {{ return {{left: 0, top: 0}}; }}
        }}
        const bars = [{{time: 1000}}, {{time: 1060}}];
        const knownCoordinates = new Map([[1000, 0], [1060, 10]]);
        const timeScale = {{
          timeToCoordinate: time => knownCoordinates.get(time) ?? null,
          coordinateToTime: coordinate => coordinate <= 10 ? 1000 + (coordinate * 6) : null,
          coordinateToLogical: coordinate => coordinate / 10,
          logicalToCoordinate: logical => logical * 10,
        }};
        const chart = {{timeScale: () => timeScale}};
        const series = {{
          priceToCoordinate: price => price,
          coordinateToPrice: coordinate => coordinate,
          attachPrimitive(primitive) {{ primitive.attached({{chart, series, requestUpdate() {{}}}}); }},
          detachPrimitive() {{}},
        }};
        const store = new drawing.DrawingStore([
          drawing.createTrendModel([{{time: 1180, price: 40}}, {{time: 1300, price: 60}}], {{id: 'future'}})
        ]);
        const element = new Target();
        const controller = new drawing.DrawingController({{
          chart, series, element, keyTarget: new Target(), bars, store,
        }});
        controller.activateTool('select');
        controller.select('future');

        element.dispatch('pointerdown', {{clientX: 30, clientY: 40}});
        element.dispatch('pointermove', {{clientX: 40, clientY: 45}});
        element.dispatch('pointerup', {{clientX: 40, clientY: 45}});
        assert.deepEqual(controller.store.get('future').anchors, [
          {{time: 1240, price: 45}}, {{time: 1300, price: 60}}
        ]);

        element.dispatch('pointerdown', {{clientX: 45, clientY: 52.5}});
        element.dispatch('pointermove', {{clientX: 55, clientY: 62.5}});
        element.dispatch('pointerup', {{clientX: 55, clientY: 62.5}});
        assert.deepEqual(controller.store.get('future').anchors, [
          {{time: 1300, price: 55}}, {{time: 1360, price: 70}}
        ]);
        """
        completed = run_node(script)
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_invalid_coordinates_are_safe_and_interaction_callback_balances(self):
        script = f"""
        const drawing = require({json.dumps(str(DRAWING_TOOLS_PATH))});
        const assert = require('node:assert/strict');
        class Target {{
          constructor() {{ this.listeners = new Map(); }}
          addEventListener(type, handler) {{ this.listeners.set(type, handler); }}
          removeEventListener(type) {{ this.listeners.delete(type); }}
          dispatch(type, event) {{ this.listeners.get(type)?.({{pointerId: 8, preventDefault() {{}}, ...event}}); }}
          setPointerCapture() {{}}
          releasePointerCapture() {{}}
          getBoundingClientRect() {{ return {{left: 0, top: 0}}; }}
        }}
        const element = new Target();
        const keyTarget = new Target();
        const states = [];
        const chart = {{timeScale: () => ({{timeToCoordinate: v => v, coordinateToTime: x => x < 0 ? null : x}})}};
        const series = {{priceToCoordinate: v => v, coordinateToPrice: y => y < 0 ? undefined : y,
          attachPrimitive(primitive) {{ primitive.attached({{chart, series, requestUpdate() {{}}}}); }}, detachPrimitive() {{}}}};
        const controller = new drawing.DrawingController({{
          chart, series, element, keyTarget,
          onInteractionStateChange(active, detail) {{ states.push([active, detail.type]); }},
        }});
        controller.activateTool('trend');
        assert.doesNotThrow(() => element.dispatch('pointerdown', {{clientX: NaN, clientY: 10}}));
        assert.equal(controller.store.size, 0);
        element.dispatch('pointerdown', {{clientX: 10, clientY: 10}});
        assert.doesNotThrow(() => element.dispatch('pointermove', {{clientX: -1, clientY: -1}}));
        assert.doesNotThrow(() => element.dispatch('pointerup', {{clientX: -1, clientY: -1}}));
        assert.equal(controller.store.size, 0);
        assert.deepEqual(states, [[true, 'create'], [false, 'create']]);
        """
        completed = run_node(script)
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_pointerdown_only_prevents_and_captures_for_creation_or_edit_hits(self):
        script = f"""
        const drawing = require({json.dumps(str(DRAWING_TOOLS_PATH))});
        const assert = require('node:assert/strict');
        class Target {{
          constructor() {{ this.listeners = new Map(); this.captured = []; this.prevented = 0; }}
          addEventListener(type, handler) {{ this.listeners.set(type, handler); }}
          removeEventListener(type) {{ this.listeners.delete(type); }}
          dispatch(type, event) {{
            this.listeners.get(type)?.({{
              pointerId: 7, clientX: 200, clientY: 200,
              preventDefault: () => this.prevented++, ...event
            }});
          }}
          setPointerCapture(id) {{ this.captured.push(id); }}
          releasePointerCapture() {{}}
          getBoundingClientRect() {{ return {{left: 0, top: 0}}; }}
        }}
        const element = new Target();
        const keyTarget = new Target();
        const store = new drawing.DrawingStore([
          drawing.createTrendModel([{{time: 10, price: 10}}, {{time: 100, price: 10}}], {{id: 'line'}}),
          drawing.createTrendModel([{{time: 10, price: 30}}, {{time: 100, price: 30}}], {{id: 'locked', locked: true}}),
        ]);
        const controller = new drawing.DrawingController({{
          chart: {{timeScale: () => ({{timeToCoordinate: v => v, coordinateToTime: v => v}})}},
          series: {{priceToCoordinate: v => v, coordinateToPrice: v => v,
            attachPrimitive() {{}}, detachPrimitive() {{}}}},
          element, keyTarget, store,
        }});
        controller.activateTool('select');
        element.dispatch('pointerdown', {{clientX: 200, clientY: 200}});
        assert.equal(element.prevented, 0);
        assert.equal(element.captured.length, 0);
        element.dispatch('pointerdown', {{clientX: 50, clientY: 30}});
        assert.equal(element.prevented, 0);
        assert.equal(element.captured.length, 0);
        element.dispatch('pointerdown', {{clientX: 50, clientY: 10}});
        assert.equal(element.prevented, 1);
        assert.deepEqual(element.captured, [7]);
        controller.cancelGesture();
        controller.activateTool('trend');
        element.dispatch('pointerdown', {{clientX: 200, clientY: 200}});
        assert.equal(element.prevented, 2);
        assert.deepEqual(element.captured, [7, 7]);
        """
        completed = run_node(script)
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_bar_sync_reuses_one_snapshot_and_updates_only_rulers_once(self):
        script = f"""
        const drawing = require({json.dumps(str(DRAWING_TOOLS_PATH))});
        const assert = require('node:assert/strict');
        class Target {{
          constructor() {{ this.listeners = new Map(); }}
          addEventListener(type, handler) {{ this.listeners.set(type, handler); }}
          removeEventListener(type) {{ this.listeners.delete(type); }}
          getBoundingClientRect() {{ return {{left: 0, top: 0}}; }}
        }}
        const element = new Target();
        const keyTarget = new Target();
        const store = new drawing.DrawingStore([
          drawing.createTrendModel([{{time: 1, price: 1}}, {{time: 2, price: 2}}], {{id: 'trend'}}),
          drawing.createRulerModel([{{time: 1, price: 1}}, {{time: 2, price: 2}}], {{id: 'ruler'}}),
        ]);
        const updates = {{trend: 0, ruler: 0}};
        const chart = {{timeScale: () => ({{timeToCoordinate: v => v, coordinateToTime: v => v}})}};
        const series = {{
          priceToCoordinate: v => v, coordinateToPrice: v => v,
          attachPrimitive(primitive) {{
            const id = primitive.model().id;
            primitive.attached({{chart, series, requestUpdate: () => updates[id]++}});
          }},
          detachPrimitive() {{}},
        }};
        const controller = new drawing.DrawingController({{chart, series, element, keyTarget, store}});
        updates.trend = 0;
        updates.ruler = 0;
        const rulerPrimitive = controller._primitives.get('ruler');
        const trendPrimitive = controller._primitives.get('trend');
        trendPrimitive.model = () => {{ throw new Error('non-ruler model must not be read during bar sync'); }};
        const sourceBars = [{{time: 1, open: 1, close: 2}}, {{time: 2, open: 2, close: 1}}];
        controller.setBars(sourceBars);
        assert.notEqual(controller._bars, sourceBars);
        assert.equal(rulerPrimitive._bars, controller._bars);
        assert.equal(trendPrimitive._bars, controller._bars);
        assert.deepEqual(updates, {{trend: 1, ruler: 1}});
        controller.refresh();
        assert.deepEqual(updates, {{trend: 2, ruler: 2}});
        controller.requestUpdate();
        assert.deepEqual(updates, {{trend: 3, ruler: 3}});
        """
        completed = run_node(script)
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_tool_activation_creates_two_and_three_point_drawings(self):
        script = f"""
        const drawing = require({json.dumps(str(DRAWING_TOOLS_PATH))});
        const assert = require('node:assert/strict');
        class Target {{
          constructor() {{ this.listeners = new Map(); this.captured = []; this.released = []; }}
          addEventListener(type, handler) {{ this.listeners.set(type, handler); }}
          removeEventListener(type) {{ this.listeners.delete(type); }}
          dispatch(type, event) {{ this.listeners.get(type)?.({{pointerId: 1, preventDefault() {{}}, ...event}}); }}
          setPointerCapture(id) {{ this.captured.push(id); }}
          releasePointerCapture(id) {{ this.released.push(id); }}
          getBoundingClientRect() {{ return {{left: 10, top: 20}}; }}
        }}
        const element = new Target();
        const keyTarget = new Target();
        const attached = [];
        const chart = {{timeScale: () => ({{
          timeToCoordinate: time => time,
          coordinateToTime: coordinate => coordinate,
        }})}};
        const series = {{
          priceToCoordinate: price => price,
          coordinateToPrice: coordinate => coordinate,
          attachPrimitive: primitive => attached.push(primitive),
          detachPrimitive: primitive => attached.splice(attached.indexOf(primitive), 1),
        }};
        const controller = new drawing.DrawingController({{chart, series, element, keyTarget}});
        controller.activateTool('trend');
        assert.equal(controller.activeTool, 'trend');
        element.dispatch('pointerdown', {{clientX: 20, clientY: 40}});
        element.dispatch('pointermove', {{clientX: 40, clientY: 60}});
        element.dispatch('pointerup', {{clientX: 40, clientY: 60}});
        assert.equal(controller.store.size, 1);
        assert.equal(controller.store.snapshot()[0].type, 'trend');
        assert.deepEqual(controller.store.snapshot()[0].anchors, [
          {{time: 10, price: 20}}, {{time: 30, price: 40}}
        ]);
        assert.equal(controller.activeTool, null);
        controller.activateTool('long');
        element.dispatch('pointerdown', {{clientX: 30, clientY: 120}});
        element.dispatch('pointermove', {{clientX: 60, clientY: 135}});
        element.dispatch('pointerup', {{clientX: 60, clientY: 135}});
        assert.equal(controller.store.size, 2);
        assert.equal(controller.store.snapshot()[1].type, 'long');
        assert.equal(attached.length, 2);
        assert.equal(element.captured.length, element.released.length);
        """
        completed = run_node(script)
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_selection_body_drag_anchor_drag_and_edit_actions(self):
        script = f"""
        const drawing = require({json.dumps(str(DRAWING_TOOLS_PATH))});
        const assert = require('node:assert/strict');
        class Target {{
          constructor() {{ this.listeners = new Map(); }}
          addEventListener(type, handler) {{ this.listeners.set(type, handler); }}
          removeEventListener(type) {{ this.listeners.delete(type); }}
          dispatch(type, event) {{ this.listeners.get(type)?.({{pointerId: 2, preventDefault() {{}}, ...event}}); }}
          setPointerCapture() {{}}
          releasePointerCapture() {{}}
          getBoundingClientRect() {{ return {{left: 0, top: 0}}; }}
        }}
        const element = new Target();
        const keyTarget = new Target();
        const store = new drawing.DrawingStore([
          drawing.createTrendModel([{{time: 10, price: 10}}, {{time: 110, price: 10}}], {{id: 'line'}})
        ]);
        const chart = {{timeScale: () => ({{timeToCoordinate: value => value, coordinateToTime: value => value}})}};
        const series = {{
          priceToCoordinate: value => value, coordinateToPrice: value => value,
          attachPrimitive() {{}}, detachPrimitive() {{}},
        }};
        const controller = new drawing.DrawingController({{chart, series, element, keyTarget, store}});
        controller.activateTool('select');
        element.dispatch('pointerdown', {{clientX: 60, clientY: 10}});
        element.dispatch('pointerup', {{clientX: 60, clientY: 10}});
        assert.equal(controller.selectedId, 'line');
        element.dispatch('pointerdown', {{clientX: 10, clientY: 10}});
        element.dispatch('pointermove', {{clientX: 20, clientY: 30}});
        element.dispatch('pointerup', {{clientX: 20, clientY: 30}});
        assert.deepEqual(store.get('line').anchors[0], {{time: 20, price: 30}});
        element.dispatch('pointerdown', {{clientX: 70, clientY: 20}});
        element.dispatch('pointermove', {{clientX: 80, clientY: 25}});
        element.dispatch('pointerup', {{clientX: 80, clientY: 25}});
        assert.deepEqual(store.get('line').anchors, [
          {{time: 30, price: 35}}, {{time: 120, price: 15}}
        ]);
        assert.equal(controller.toggleLock(), true);
        assert.equal(store.get('line').locked, true);
        assert.equal(controller.deleteSelected(), false);
        assert.equal(store.size, 1);
        assert.equal(controller.toggleHidden(), true);
        assert.equal(store.get('line').hidden, true);
        assert.equal(controller.toggleLock(), true);
        assert.equal(controller.deleteSelected(), true);
        assert.equal(store.size, 0);
        """
        completed = run_node(script)
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_escape_delete_undo_redo_clear_and_keyboard_input_guards(self):
        script = f"""
        const drawing = require({json.dumps(str(DRAWING_TOOLS_PATH))});
        const assert = require('node:assert/strict');
        class Target {{
          constructor() {{ this.listeners = new Map(); }}
          addEventListener(type, handler) {{ this.listeners.set(type, handler); }}
          removeEventListener(type) {{ this.listeners.delete(type); }}
          dispatch(type, event) {{ this.listeners.get(type)?.({{preventDefault() {{}}, ...event}}); }}
          setPointerCapture() {{}}
          releasePointerCapture() {{}}
          getBoundingClientRect() {{ return {{left: 0, top: 0}}; }}
        }}
        const element = new Target();
        const keyTarget = new Target();
        const chart = {{timeScale: () => ({{timeToCoordinate: v => v, coordinateToTime: v => v}})}};
        const series = {{
          priceToCoordinate: v => v, coordinateToPrice: v => v,
          attachPrimitive() {{}}, detachPrimitive() {{}},
        }};
        const controller = new drawing.DrawingController({{chart, series, element, keyTarget}});
        controller.activateTool('trend');
        element.dispatch('pointerdown', {{pointerId: 1, clientX: 1, clientY: 1}});
        keyTarget.dispatch('keydown', {{key: 'Escape', target: {{tagName: 'DIV'}}}});
        assert.equal(controller.activeTool, null);
        assert.equal(controller.store.size, 0);
        controller.store.add(drawing.createHorizontalModel([{{time: 1, price: 2}}], {{id: 'h'}}));
        controller.refresh();
        controller.select('h');
        keyTarget.dispatch('keydown', {{key: 'Delete', target: {{tagName: 'INPUT'}}}});
        assert.equal(controller.store.size, 1);
        keyTarget.dispatch('keydown', {{key: 'Delete', target: {{tagName: 'DIV'}}}});
        assert.equal(controller.store.size, 0);
        keyTarget.dispatch('keydown', {{key: 'z', ctrlKey: true, target: {{tagName: 'DIV'}}}});
        assert.equal(controller.store.size, 1);
        keyTarget.dispatch('keydown', {{key: 'y', ctrlKey: true, target: {{tagName: 'DIV'}}}});
        assert.equal(controller.store.size, 0);
        controller.store.add(drawing.createHorizontalModel([{{time: 2, price: 3}}], {{id: 'h2'}}));
        controller.store.add(drawing.createHorizontalModel([{{time: 3, price: 4}}], {{id: 'h3'}}));
        controller.refresh();
        assert.equal(controller.clearAll(), true);
        assert.equal(controller.store.size, 0);
        assert.equal(controller.undo(), true);
        assert.equal(controller.store.size, 2);
        assert.equal(controller.resetAll(), true);
        assert.equal(controller.store.size, 0);
        assert.equal(controller.undo(), false);
        """
        completed = run_node(script)
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_touch_normalization_and_destroy_cleanup(self):
        script = f"""
        const drawing = require({json.dumps(str(DRAWING_TOOLS_PATH))});
        const assert = require('node:assert/strict');
        class Target {{
          constructor() {{ this.listeners = new Map(); this.released = []; }}
          addEventListener(type, handler) {{ this.listeners.set(type, handler); }}
          removeEventListener(type) {{ this.listeners.delete(type); }}
          setPointerCapture() {{}}
          releasePointerCapture(id) {{ this.released.push(id); }}
          getBoundingClientRect() {{ return {{left: 5, top: 7}}; }}
        }}
        const element = new Target();
        const normalized = drawing.normalizePointerEvent({{
          touches: [{{clientX: 25, clientY: 37, identifier: 9}}]
        }}, element);
        assert.deepEqual(normalized, {{x: 20, y: 30, clientX: 25, clientY: 37, pointerId: 9}});
        let detached = 0;
        const keyTarget = new Target();
        const store = new drawing.DrawingStore([
          drawing.createHorizontalModel([{{time: 1, price: 2}}], {{id: 'h'}})
        ]);
        const controller = new drawing.DrawingController({{
          chart: {{timeScale: () => ({{timeToCoordinate: v => v, coordinateToTime: v => v}})}},
          series: {{
            priceToCoordinate: v => v, coordinateToPrice: v => v,
            attachPrimitive() {{}}, detachPrimitive() {{ detached++; }},
          }},
          element, keyTarget, store,
        }});
        controller.destroy();
        assert.equal(element.listeners.size, 0);
        assert.equal(keyTarget.listeners.size, 0);
        assert.equal(detached, 1);
        """
        completed = run_node(script)
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_set_bars_refresh_and_rebind_update_ruler_statistics(self):
        script = f"""
        const drawing = require({json.dumps(str(DRAWING_TOOLS_PATH))});
        const assert = require('node:assert/strict');
        class Target {{
          constructor() {{ this.listeners = new Map(); }}
          addEventListener(type, handler) {{ this.listeners.set(type, handler); }}
          removeEventListener(type) {{ this.listeners.delete(type); }}
          getBoundingClientRect() {{ return {{left: 0, top: 0}}; }}
        }}
        const element = new Target();
        const keyTarget = new Target();
        const store = new drawing.DrawingStore([
          drawing.createRulerModel([{{time: 1000, price: 10}}, {{time: 1180, price: 12}}], {{id: 'r'}})
        ]);
        let firstDetached = 0;
        const chart1 = {{timeScale: () => ({{timeToCoordinate: v => v, coordinateToTime: v => v}})}};
        const series1 = {{priceToCoordinate: v => v, coordinateToPrice: v => v,
          attachPrimitive() {{}}, detachPrimitive() {{ firstDetached++; }}}};
        const controller = new drawing.DrawingController({{
          chart: chart1, series: series1, element, keyTarget, store,
          bars: [{{time: 1000, open: 10, close: 11}}],
        }});
        assert.equal(controller.getRulerMetrics('r').barCount, 1);
        assert.equal(controller.requestUpdate(), 1);
        controller.setBars([
          {{time: 1000, open: 10, close: 11}},
          {{time: 1060, open: 11, close: 10}},
          {{time: 1180, open: 10, close: 12}},
        ]);
        assert.deepEqual(controller.getRulerMetrics('r'), {{
          priceDelta: 2, absolutePriceChange: 2, percentChange: 20,
          barCount: 3, bullishCount: 2, bearishCount: 1,
          totalVolume: 0,
          duration: 180, elapsedDuration: 180, direction: 'bull',
        }});
        let secondAttached = 0;
        const chart2 = {{timeScale: () => ({{timeToCoordinate: v => v / 2, coordinateToTime: v => v * 2}})}};
        const series2 = {{priceToCoordinate: v => v * 2, coordinateToPrice: v => v / 2,
          attachPrimitive() {{ secondAttached++; }}, detachPrimitive() {{}}}};
        controller.rebind({{chart: chart2, series: series2}});
        assert.equal(firstDetached, 1);
        assert.equal(secondAttached, 1);
        assert.equal(controller.getRulerMetrics('r').barCount, 3);
        controller.refresh();
        assert.equal(controller.getRulerMetrics('r').bullishCount, 2);
        """
        completed = run_node(script)
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_selected_fibonacci_settings_support_full_level_workflow(self):
        script = f"""
        const drawing = require({json.dumps(str(DRAWING_TOOLS_PATH))});
        const assert = require('node:assert/strict');
        class Target {{
          constructor() {{ this.listeners = new Map(); }}
          addEventListener(type, handler) {{ this.listeners.set(type, handler); }}
          removeEventListener(type) {{ this.listeners.delete(type); }}
          getBoundingClientRect() {{ return {{left: 0, top: 0}}; }}
        }}
        const element = new Target();
        const keyTarget = new Target();
        const store = new drawing.DrawingStore([
          drawing.createFibonacciModel([{{time: 1, price: 10}}, {{time: 2, price: 20}}], {{id: 'fib'}})
        ]);
        const controller = new drawing.DrawingController({{
          chart: {{timeScale: () => ({{timeToCoordinate: v => v, coordinateToTime: v => v}})}},
          series: {{priceToCoordinate: v => v, coordinateToPrice: v => v,
            attachPrimitive() {{}}, detachPrimitive() {{}}}},
          element, keyTarget, store,
        }});
        controller.select('fib');
        assert.equal(controller.getFibonacciSettings().levels.length, 10);
        controller.setFibonacciLevelEnabled(1, false);
        assert.equal(controller.getFibonacciSettings().levels[1].enabled, false);
        controller.addFibonacciLevel({{value: 2.618, label: '261.8', color: '#123456'}}, 2);
        assert.equal(controller.getFibonacciSettings().levels[2].value, 2.618);
        controller.reorderFibonacciLevel(2, 0);
        assert.equal(controller.getFibonacciSettings().levels[0].value, 2.618);
        controller.removeFibonacciLevel(0);
        controller.updateFibonacciSettings({{
          reverse: true, lineWidth: 3, lineStyle: 'dashed', labelPosition: 'right'
        }});
        const settings = controller.getFibonacciSettings();
        assert.equal(settings.reverse, true);
        assert.equal(settings.lineWidth, 3);
        assert.equal(settings.lineStyle, 'dashed');
        assert.equal(settings.labelPosition, 'right');
        controller.resetFibonacciSettings();
        const reset = controller.getFibonacciSettings();
        assert.equal(reset.levels.length, 10);
        assert.equal(reset.reverse, false);
        assert.equal(reset.lineWidth, 1);
        assert.equal(reset.lineStyle, 'solid');
        assert.equal(reset.labelPosition, 'left');
        """
        completed = run_node(script)
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_invalid_risk_reward_anchor_drag_is_ignored_without_throwing(self):
        script = f"""
        const drawing = require({json.dumps(str(DRAWING_TOOLS_PATH))});
        const assert = require('node:assert/strict');
        class Target {{
          constructor() {{ this.listeners = new Map(); }}
          addEventListener(type, handler) {{ this.listeners.set(type, handler); }}
          removeEventListener(type) {{ this.listeners.delete(type); }}
          dispatch(type, event) {{ this.listeners.get(type)?.({{pointerId: 1, preventDefault() {{}}, ...event}}); }}
          setPointerCapture() {{}}
          releasePointerCapture() {{}}
          getBoundingClientRect() {{ return {{left: 0, top: 0}}; }}
        }}
        const element = new Target();
        const keyTarget = new Target();
        const store = new drawing.DrawingStore([
          drawing.createDrawingModel('long-position', [
            {{time: 10, price: 100}}, {{time: 20, price: 95}}, {{time: 20, price: 115}}
          ], {{id: 'risk'}})
        ]);
        const controller = new drawing.DrawingController({{
          chart: {{timeScale: () => ({{timeToCoordinate: v => v, coordinateToTime: v => v}})}},
          series: {{priceToCoordinate: v => v, coordinateToPrice: v => v,
            attachPrimitive() {{}}, detachPrimitive() {{}}}},
          element, keyTarget, store,
        }});
        controller.activateTool('select');
        controller.select('risk');
        element.dispatch('pointerdown', {{clientX: 20, clientY: 95}});
        element.dispatch('pointermove', {{clientX: 20, clientY: 105}});
        element.dispatch('pointerup', {{clientX: 20, clientY: 105}});
        assert.deepEqual(store.get('risk').anchors, [
          {{time: 10, price: 100}}, {{time: 20, price: 95}}, {{time: 20, price: 115}}
        ]);
        """
        completed = run_node(script)
        self.assertEqual(completed.returncode, 0, completed.stderr)


class PriceAxisLabelRuntimeTests(unittest.TestCase):
    def test_axis_label_prices_mapping_covers_every_tool_type(self):
        script = f"""
        const drawing = require({json.dumps(str(DRAWING_TOOLS_PATH))});
        const assert = require('node:assert/strict');
        const anchors2 = [{{price: 1}}, {{price: 2}}];
        const anchors3 = [{{price: 1}}, {{price: 2}}, {{price: 3}}];
        assert.deepEqual(drawing.axisLabelPrices({{type: 'horizontal', anchors: [{{price: 1.5}}]}}), [1.5]);
        for (const type of ['trend', 'ray', 'rectangle', 'ruler']) {{
          assert.deepEqual(drawing.axisLabelPrices({{type, anchors: anchors2}}), [1, 2], type);
        }}
        for (const type of ['long', 'short', 'risk-reward']) {{
          assert.deepEqual(drawing.axisLabelPrices({{type, anchors: anchors3}}), [1, 2, 3], type);
        }}
        assert.deepEqual(drawing.axisLabelPrices({{type: 'fibonacci', anchors: anchors2}}), []);
        assert.deepEqual(drawing.axisLabelPrices({{type: 'text', anchors: [{{price: 1}}]}}), []);
        assert.deepEqual(drawing.axisLabelPrices(null), []);
        assert.deepEqual(drawing.axisLabelPrices({{type: 'trend'}}), []);
        """
        completed = run_node(script)
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_price_axis_views_follow_selection_hover_and_hidden_state(self):
        script = f"""
        const drawing = require({json.dumps(str(DRAWING_TOOLS_PATH))});
        const assert = require('node:assert/strict');
        const model = drawing.createTrendModel([
          {{time: 10, price: 100.5}}, {{time: 20, price: 102.25}}
        ], {{id: 'axis'}});
        const primitive = new drawing.DrawingPrimitive(model);
        primitive.attached({{
          chart: {{timeScale: () => ({{timeToCoordinate: value => value}})}},
          series: {{
            priceToCoordinate: price => 500 - price * 2,
            options: () => ({{priceFormat: {{precision: 2}}}}),
          }},
          requestUpdate() {{}},
        }});
        const views = primitive.priceAxisViews();
        assert.equal(views.length, 3);
        assert.equal(primitive.priceAxisViews(), views);
        assert.deepEqual(views.map(view => view.visible()), [false, false, false]);

        primitive.setModel({{...model, selected: true}});
        assert.deepEqual(views.map(view => view.visible()), [true, true, false]);
        assert.equal(views[0].coordinate(), 299);
        assert.equal(views[1].coordinate(), 295.5);
        assert.equal(views[0].text(), '100.50');
        assert.equal(views[1].text(), '102.25');
        assert.equal(views[0].fixedCoordinate(), null);
        assert.equal(views[0].tickVisible(), true);

        primitive.setAxisLabelColors(() => ({{background: '#111111', text: '#222222'}}));
        assert.equal(views[0].backColor(), '#111111');
        assert.equal(views[0].textColor(), '#222222');

        primitive.setModel({{...model, selected: true, hidden: true}});
        assert.deepEqual(views.map(view => view.visible()), [false, false, false]);
        assert.equal(views[0].text(), '');
        assert.equal(views[0].backColor(), 'rgba(0, 0, 0, 0)');

        primitive.setModel({{...model, hovered: true}});
        assert.equal(views[0].visible(), true);

        const fib = drawing.createFibonacciModel(
          [{{time: 1, price: 10}}, {{time: 2, price: 20}}], {{selected: true}}
        );
        const fibPrimitive = new drawing.DrawingPrimitive(fib);
        fibPrimitive.attached({{
          chart: {{timeScale: () => ({{timeToCoordinate: value => value}})}},
          series: {{priceToCoordinate: price => price}},
          requestUpdate() {{}},
        }});
        assert.deepEqual(
          fibPrimitive.priceAxisViews().map(view => view.visible()),
          [false, false, false]
        );

        const risk = drawing.createDrawingModel('long', [
          {{time: 1, price: 100}}, {{time: 2, price: 90}}, {{time: 2, price: 115}}
        ], {{selected: true}});
        const riskPrimitive = new drawing.DrawingPrimitive(risk);
        riskPrimitive.attached({{
          chart: {{timeScale: () => ({{timeToCoordinate: value => value}})}},
          series: {{priceToCoordinate: price => price}},
          requestUpdate() {{}},
        }});
        assert.deepEqual(
          riskPrimitive.priceAxisViews().map(view => view.visible()),
          [true, true, true]
        );
        """
        completed = run_node(script)
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_duplicate_anchor_prices_render_single_axis_label(self):
        script = f"""
        const drawing = require({json.dumps(str(DRAWING_TOOLS_PATH))});
        const assert = require('node:assert/strict');
        const model = drawing.createTrendModel([
          {{time: 1, price: 50}}, {{time: 2, price: 50}}
        ], {{selected: true}});
        const primitive = new drawing.DrawingPrimitive(model);
        primitive.attached({{
          chart: {{timeScale: () => ({{timeToCoordinate: value => value}})}},
          series: {{priceToCoordinate: price => price}},
          requestUpdate() {{}},
        }});
        const views = primitive.priceAxisViews();
        assert.equal(views[0].visible(), true);
        assert.equal(views[1].visible(), false);
        assert.equal(views[0].text(), '50');

        const operations = [];
        const context = new Proxy({{measureText: text => ({{width: text.length * 6}})}}, {{
          get(target, key) {{
            if (key in target) return target[key];
            return (...args) => operations.push([key, ...args]);
          }},
          set(target, key, value) {{ operations.push(['set', key, value]); target[key] = value; return true; }}
        }});
        const rectangle = drawing.createRectangleModel(
          [{{time: 0, price: 10}}, {{time: 50, price: 30}}], {{selected: true}}
        );
        const rectPrimitive = new drawing.DrawingPrimitive(rectangle);
        rectPrimitive.setDefaultStrokeColor(() => 'rgba(234, 236, 239, 0.92)');
        rectPrimitive.attached({{
          chart: {{timeScale: () => ({{timeToCoordinate: value => value}})}},
          series: {{priceToCoordinate: price => price}},
          requestUpdate() {{}},
        }});
        rectPrimitive.paneViews()[0].renderer().draw({{useBitmapCoordinateSpace(callback) {{
          callback({{context, horizontalPixelRatio: 1, verticalPixelRatio: 1,
            bitmapSize: {{width: 200, height: 200}}, mediaSize: {{width: 200, height: 200}}}});
        }}}});
        assert.ok(operations.some(op => op[0] === 'set' && op[1] === 'strokeStyle'
          && op[2] === 'rgba(234, 236, 239, 0.92)'));
        assert.ok(operations.some(op => op[0] === 'set' && op[1] === 'fillStyle'
          && op[2] === 'rgba(234, 236, 239, 0.16)'));
        """
        completed = run_node(script)
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_controller_propagates_theme_providers_to_primitives_and_drafts(self):
        script = f"""
        const drawing = require({json.dumps(str(DRAWING_TOOLS_PATH))});
        const assert = require('node:assert/strict');
        class Target {{
          constructor() {{ this.listeners = new Map(); }}
          addEventListener(type, handler) {{ this.listeners.set(type, handler); }}
          removeEventListener(type) {{ this.listeners.delete(type); }}
          dispatch(type, event = {{}}) {{ this.listeners.get(type)?.({{pointerId: 3, preventDefault() {{}}, ...event}}); }}
          setPointerCapture() {{}}
          releasePointerCapture() {{}}
          getBoundingClientRect() {{ return {{left: 0, top: 0}}; }}
        }}
        const element = new Target();
        const chart = {{timeScale: () => ({{timeToCoordinate: v => v, coordinateToTime: v => v}})}};
        const series = {{
          priceToCoordinate: v => v, coordinateToPrice: v => v,
          attachPrimitive(primitive) {{ primitive.attached({{chart, series, requestUpdate() {{}}}}); }},
          detachPrimitive() {{}},
        }};
        const store = new drawing.DrawingStore([
          drawing.createTrendModel([{{time: 10, price: 20}}, {{time: 30, price: 40}}], {{id: 'line'}})
        ]);
        const controller = new drawing.DrawingController({{
          chart, series, element, keyTarget: new Target(), store,
          axisLabelColors: () => ({{background: '#010203', text: '#040506'}}),
          defaultDrawingColor: () => '#fefefe',
        }});
        controller.select('line');
        const primitive = controller._primitives.get('line');
        const views = primitive.priceAxisViews();
        assert.deepEqual(views.map(view => view.visible()), [true, true, false]);
        assert.equal(views[0].backColor(), '#010203');
        assert.equal(views[0].textColor(), '#040506');
        assert.equal(views[0].coordinate(), 20);
        assert.equal(views[1].coordinate(), 40);

        const operations = [];
        const context = new Proxy({{measureText: text => ({{width: text.length * 6}})}}, {{
          get(target, key) {{
            if (key in target) return target[key];
            return (...args) => operations.push([key, ...args]);
          }},
          set(target, key, value) {{ operations.push(['set', key, value]); target[key] = value; return true; }}
        }});
        primitive.paneViews()[0].renderer().draw({{useBitmapCoordinateSpace(callback) {{
          callback({{context, horizontalPixelRatio: 1, verticalPixelRatio: 1,
            bitmapSize: {{width: 200, height: 200}}, mediaSize: {{width: 200, height: 200}}}});
        }}}});
        assert.ok(operations.some(op => op[0] === 'set' && op[1] === 'strokeStyle'
          && op[2] === '#fefefe'));

        controller.activateTool('trend');
        element.dispatch('pointerdown', {{clientX: 15, clientY: 25}});
        assert.ok(controller._draftPrimitive);
        assert.equal(controller._draftPrimitive.defaultStrokeColor(), '#fefefe');
        const draftViews = controller._draftPrimitive.priceAxisViews();
        assert.equal(draftViews[0].backColor(), '#010203');
        assert.equal(draftViews[0].visible(), true);
        element.dispatch('pointerup', {{clientX: 15, clientY: 25}});
        """
        completed = run_node(script)
        self.assertEqual(completed.returncode, 0, completed.stderr)


class FibTrendTimeRuntimeTests(unittest.TestCase):
    def test_fib_trend_time_defaults_model_and_serialization(self):
        script = f"""
        const drawing = require({json.dumps(str(DRAWING_TOOLS_PATH))});
        const assert = require('node:assert/strict');
        assert.deepEqual(
          drawing.DEFAULT_FIB_TREND_TIME_LEVELS.map(level => level.value),
          [0, 0.382, 0.618, 1, 1.382, 1.618, 2, 2.382, 2.618, 3]
        );
        assert.deepEqual(
          drawing.DEFAULT_FIB_TREND_TIME_LEVELS.map(level => level.label),
          ['0', '0.382', '0.618', '1', '1.382', '1.618', '2', '2.382', '2.618', '3']
        );
        assert.ok(drawing.DEFAULT_FIB_TREND_TIME_LEVELS.every(
          level => /^#[0-9a-f]{{6}}$/i.test(level.color) && level.enabled
        ));
        const settings = drawing.defaultFibTrendTimeSettings();
        assert.equal(settings.lineStyle, 'dashed');
        assert.equal(settings.levels.length, 10);
        const model = drawing.createDrawingModel('fib-trend-time', [
          {{time: 1, price: 100}}, {{time: 2, price: 90}}
        ], {{id: 'ft'}});
        assert.equal(model.type, 'fib-trend-time');
        assert.equal(model.options.levels.length, 10);
        assert.equal(model.options.lineStyle, 'dashed');
        const serialized = drawing.serializeDrawing(model);
        assert.equal(serialized.type, 'fib-trend-time');
        assert.equal(serialized.options.levels.length, 10);
        const levels = drawing.calculateFibonacciLevels(100, 90, model.options);
        assert.equal(levels.find(level => level.value === 0).price, 100);
        assert.equal(levels.find(level => level.value === 1).price, 90);
        assert.equal(levels.find(level => level.value === 2).price, 80);
        assert.equal(levels.find(level => level.value === 3).price, 70);
        const reversed = drawing.calculateFibonacciLevels(100, 90, {{...model.options, reverse: true}});
        assert.equal(reversed.find(level => level.value === 0).price, 90);
        assert.equal(reversed.find(level => level.value === 1).price, 100);
        """
        completed = run_node(script)
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_fib_trend_time_renderer_draws_vertical_time_lines(self):
        script = f"""
        const drawing = require({json.dumps(str(DRAWING_TOOLS_PATH))});
        const assert = require('node:assert/strict');
        const operations = [];
        const context = new Proxy({{measureText: text => ({{width: text.length * 6}})}}, {{
          get(target, key) {{
            if (key in target) return target[key];
            return (...args) => operations.push([key, ...args]);
          }},
          set(target, key, value) {{ operations.push(['set', key, value]); target[key] = value; return true; }}
        }});
        const model = drawing.createFibTrendTimeModel([
          {{time: 10, price: 100}}, {{time: 20, price: 90}}
        ], {{id: 'ft', selected: true}});
        const primitive = new drawing.DrawingPrimitive(model);
        primitive.attached({{
          chart: {{timeScale: () => ({{timeToCoordinate: value => value}})}},
          series: {{priceToCoordinate: price => 300 - price}},
          requestUpdate() {{}},
        }});
        primitive.paneViews()[0].renderer().draw({{useBitmapCoordinateSpace(callback) {{
          callback({{context, horizontalPixelRatio: 1, verticalPixelRatio: 1,
            bitmapSize: {{width: 200, height: 300}}, mediaSize: {{width: 200, height: 300}}}});
        }}}});
        assert.ok(operations.some(op => op[0] === 'setLineDash'));
        // 垂直线使用各档位颜色
        assert.ok(operations.some(op => op[0] === 'set' && op[1] === 'strokeStyle' && op[2] === '#9e9e9e'));
        assert.ok(operations.some(op => op[0] === 'set' && op[1] === 'strokeStyle' && op[2] === '#ff9800'));
        // 0 线对齐 B 锚点（x=20），1 线 → x=20+1*10=30，档位 3 → x=20+3*10=50，
        // 垂直贯穿整个高度 300；全部向 B 右侧（未来）扩展
        assert.ok(operations.some(op => op[0] === 'lineTo' && op[1] === 20 && op[2] === 300));
        assert.ok(operations.some(op => op[0] === 'lineTo' && op[1] === 30 && op[2] === 300));
        assert.ok(operations.some(op => op[0] === 'lineTo' && op[1] === 50 && op[2] === 300));
        // 顶部倍数标签
        assert.ok(operations.some(op => op[0] === 'fillText' && String(op[1]).includes('0.382')));
        assert.ok(operations.some(op => op[0] === 'fillText' && String(op[1]).includes('2.618')));
        """
        completed = run_node(script)
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_fib_trend_time_has_no_price_axis_views(self):
        script = f"""
        const drawing = require({json.dumps(str(DRAWING_TOOLS_PATH))});
        const assert = require('node:assert/strict');
        const chart = {{timeScale: () => ({{timeToCoordinate: value => value}})}};
        const series = {{priceToCoordinate: price => 300 - price}};
        const model = drawing.createFibTrendTimeModel([
          {{time: 10, price: 100}}, {{time: 20, price: 90}}
        ], {{id: 'ft', selected: true}});
        const primitive = new drawing.DrawingPrimitive(model);
        primitive.attached({{chart, series, requestUpdate() {{}}}});
        // 垂直时间线的倍数标签绘制在 chart 顶部/底部，不占用价格轴
        const views = primitive.priceAxisViews();
        assert.equal(views.length, 0);
        primitive.setModel({{...model, selected: true, options: {{
          ...model.options,
          levels: model.options.levels.map(level => (
            level.value === 3 ? {{...level, enabled: false}} : level
          )),
        }}}});
        assert.equal(primitive.priceAxisViews().length, 0);
        """
        completed = run_node(script)
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_fib_trend_time_controller_creation_and_settings_workflow(self):
        script = f"""
        const drawing = require({json.dumps(str(DRAWING_TOOLS_PATH))});
        const assert = require('node:assert/strict');
        class Target {{
          constructor() {{ this.listeners = new Map(); }}
          addEventListener(type, handler) {{ this.listeners.set(type, handler); }}
          removeEventListener(type) {{ this.listeners.delete(type); }}
          dispatch(type, event = {{}}) {{ this.listeners.get(type)?.({{pointerId: 11, preventDefault() {{}}, ...event}}); }}
          setPointerCapture() {{}}
          releasePointerCapture() {{}}
          getBoundingClientRect() {{ return {{left: 0, top: 0}}; }}
        }}
        const element = new Target();
        const chart = {{timeScale: () => ({{timeToCoordinate: v => v, coordinateToTime: v => v}})}};
        const series = {{
          priceToCoordinate: v => 200 - v, coordinateToPrice: v => 200 - v,
          attachPrimitive(primitive) {{ primitive.attached({{chart, series, requestUpdate() {{}}}}); }},
          detachPrimitive() {{}},
        }};
        const controller = new drawing.DrawingController({{chart, series, element, keyTarget: new Target()}});
        controller.activateTool('fib-trend-time');
        element.dispatch('pointerdown', {{clientX: 10, clientY: 100}});
        element.dispatch('pointermove', {{clientX: 60, clientY: 110}});
        element.dispatch('pointerup', {{clientX: 60, clientY: 110}});
        assert.equal(controller.store.size, 1);
        const model = controller.store.snapshot()[0];
        assert.equal(model.type, 'fib-trend-time');
        assert.deepEqual(model.anchors, [{{time: 10, price: 100}}, {{time: 60, price: 90}}]);
        assert.equal(controller.activeTool, null);

        controller.select(model.id);
        const settings = controller.getFibonacciSettings();
        assert.equal(settings.levels.length, 10);
        assert.equal(settings.lineStyle, 'dashed');

        controller.updateFibonacciSettings({{reverse: true}});
        assert.equal(controller.store.get(model.id).options.reverse, true);

        controller.setFibonacciLevelEnabled(2.382, false);
        const disabled = controller.store.get(model.id).options.levels
          .find(level => level.value === 2.382);
        assert.equal(disabled.enabled, false);
        const primitive = controller._primitives.get(model.id);
        assert.equal(primitive.priceAxisViews().length, 0);

        controller.resetFibonacciSettings();
        const resetModel = controller.store.get(model.id);
        assert.equal(resetModel.options.levels.length, 10);
        assert.ok(resetModel.options.levels.every(level => level.enabled));
        assert.equal(resetModel.options.reverse, false);

        controller.addFibonacciLevel({{value: 3.618, color: '#ffffff', enabled: true}});
        const added = controller.store.get(model.id).options.levels;
        assert.equal(added.length, 11);
        assert.equal(added[10].label, '3.618');
        assert.ok(Array.isArray(controller.getSelectedLineSettings().levels));

        // 普通斐波那契回撤不受趋势时间默认档位影响
        controller.store.add(drawing.createFibonacciModel(
          [{{time: 1, price: 10}}, {{time: 2, price: 20}}], {{id: 'fib'}}
        ));
        controller.refresh();
        controller.select('fib');
        const fibSettings = controller.getFibonacciSettings();
        assert.ok(fibSettings.levels.some(level => level.value === 0.236));
        """
        completed = run_node(script)
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_fib_trend_time_hit_test_matches_vertical_time_lines(self):
        script = f"""
        const drawing = require({json.dumps(str(DRAWING_TOOLS_PATH))});
        const assert = require('node:assert/strict');
        const chart = {{timeScale: () => ({{timeToCoordinate: time => time}})}};
        const series = {{priceToCoordinate: price => 300 - price}};
        const model = drawing.createFibTrendTimeModel([
          {{time: 10, price: 100}}, {{time: 20, price: 90}}
        ], {{id: 'ft', selected: true}});
        const primitive = new drawing.DrawingPrimitive(model);
        primitive.attached({{chart, series, requestUpdate() {{}}}});
        // 0 线对齐 B（x=20），1 线 → x=30；档位 2 → x=40；档位 3 → x=50
        const directHit = primitive.hitTest(40, 200);
        assert.equal(directHit.drawingId, 'ft');
        assert.equal(directHit.hitKind, 'body');
        assert.equal(directHit.distance, 0);
        // 档位 3 的线在 x=50，点 x=49 距离 1 命中
        const nearHit = primitive.hitTest(49, 200);
        assert.equal(nearHit.drawingId, 'ft');
        assert.equal(nearHit.distance, 1);
        // 远离所有时间线（x=100）不命中
        assert.equal(primitive.hitTest(100, 200), null);
        """
        completed = run_node(script)
        self.assertEqual(completed.returncode, 0, completed.stderr)


    def test_cross_period_anchor_projection_and_null_rejection(self):
        script = f"""
        const drawing = require({json.dumps(str(DRAWING_TOOLS_PATH))});
        const assert = require('node:assert/strict');
        assert.equal(typeof drawing.anchorToCoordinate, 'function');
        assert.equal(typeof drawing.getBarDateString, 'function');

        // 日K转120分吸附到同日峰值
        const anchor = {{ time: 1773100800, price: 44.06 }};
        const bars = [
            {{ time: 1773142200, high: 42.7, low: 40.74, open: 41, close: 42 }},
            {{ time: 1773154800, high: 44.03, low: 41.64, open: 42, close: 43.5 }}
        ];
        const timeScale = {{
            timeToCoordinate(t) {{ return t === 1773154800 ? 260 : null; }}
        }};
        const x = drawing.anchorToCoordinate(timeScale, anchor, bars);
        assert.equal(x, 260);

        // 超出历史深度数月的点返回 null
        const oldAnchor = {{ time: 1000, price: 20 }};
        const recentBars = [{{ time: 10000000 }}, {{ time: 10000100 }}];
        assert.equal(drawing.anchorToCoordinate(timeScale, oldAnchor, recentBars), null);
        """
        completed = run_node(script)
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_drawing_toggle_all_hidden_and_are_all_hidden(self):
        script = f"""
        const drawing = require({json.dumps(str(DRAWING_TOOLS_PATH))});
        const assert = require('node:assert/strict');
        class Target {{
          constructor() {{ this.listeners = new Map(); }}
          addEventListener(type, handler) {{ this.listeners.set(type, handler); }}
          removeEventListener(type) {{ this.listeners.delete(type); }}
          dispatch(type, event) {{ this.listeners.get(type)?.({{preventDefault() {{}}, ...event}}); }}
          setPointerCapture() {{}}
          releasePointerCapture() {{}}
          getBoundingClientRect() {{ return {{left: 0, top: 0}}; }}
        }}
        const element = new Target();
        const keyTarget = new Target();
        const chart = {{timeScale: () => ({{timeToCoordinate: v => v, coordinateToTime: v => v}})}};
        const series = {{
          priceToCoordinate: v => v, coordinateToPrice: v => v,
          attachPrimitive() {{}}, detachPrimitive() {{}},
        }};
        const controller = new drawing.DrawingController({{chart, series, element, keyTarget}});

        // 1. 空画线时
        assert.equal(controller.areAllHidden(), false);
        assert.equal(controller.toggleAllHidden(), false);

        // 2. 添加两根线
        controller.store.add(drawing.createHorizontalModel([{{time: 1, price: 2}}], {{id: 'h1'}}));
        controller.store.add(drawing.createTrendModel([{{time: 1, price: 2}}, {{time: 3, price: 4}}], {{id: 't1'}}));
        controller.refresh();
        controller.select('h1');
        assert.equal(controller.selectedId, 'h1');
        assert.equal(controller.areAllHidden(), false);

        // 3. 执行 toggleAllHidden -> 全部隐藏，选中态清除，返回 true
        const hidAll = controller.toggleAllHidden();
        assert.equal(hidAll, true);
        assert.equal(controller.areAllHidden(), true);
        assert.equal(controller.store.get('h1').hidden, true);
        assert.equal(controller.store.get('t1').hidden, true);
        assert.equal(controller.selectedId, null);

        // 4. 再次执行 toggleAllHidden -> 全部恢复显示，返回 false
        const unhidAll = controller.toggleAllHidden();
        assert.equal(unhidAll, false);
        assert.equal(controller.areAllHidden(), false);
        assert.equal(controller.store.get('h1').hidden, false);
        assert.equal(controller.store.get('t1').hidden, false);

        // 5. 单个隐藏时，toggleAllHidden 依然视作"存在可见项"，执行全部隐藏
        controller.select('h1');
        controller.toggleHidden(); // 只有 h1 隐藏，t1 依然显示
        assert.equal(controller.store.get('h1').hidden, true);
        assert.equal(controller.store.get('t1').hidden, false);
        assert.equal(controller.areAllHidden(), false);
        assert.equal(controller.toggleAllHidden(), true);
        assert.equal(controller.store.get('h1').hidden, true);
        assert.equal(controller.store.get('t1').hidden, true);
        assert.equal(controller.areAllHidden(), true);

        // 6. 原子撤销 (updateAll)
        assert.equal(controller.undo(), true);
        assert.equal(controller.store.get('t1').hidden, false);
        """
        completed = run_node(script)
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_drawing_tool_styles_independent_memory(self):
        script = f"""
        const drawing = require({json.dumps(str(DRAWING_TOOLS_PATH))});
        const assert = require('node:assert/strict');

        // Mock localStorage
        const storage = new Map();
        global.localStorage = {{
          getItem: (k) => storage.get(k) || null,
          setItem: (k, v) => storage.set(k, String(v)),
          removeItem: (k) => storage.delete(k),
          clear: () => storage.clear(),
        }};

        class Target {{
          constructor() {{ this.listeners = new Map(); }}
          addEventListener(type, handler) {{ this.listeners.set(type, handler); }}
          removeEventListener(type) {{ this.listeners.delete(type); }}
          dispatch(type, event) {{ this.listeners.get(type)?.({{preventDefault() {{}}, ...event}}); }}
          setPointerCapture() {{}}
          releasePointerCapture() {{}}
          getBoundingClientRect() {{ return {{left: 0, top: 0}}; }}
        }}
        const element = new Target();
        const keyTarget = new Target();
        const chart = {{timeScale: () => ({{timeToCoordinate: v => v, coordinateToTime: v => v}})}};
        const series = {{
          priceToCoordinate: v => v, coordinateToPrice: v => v,
          attachPrimitive() {{}}, detachPrimitive() {{}},
        }};
        const controller = new drawing.DrawingController({{chart, series, element, keyTarget}});

        // 1. 初始各工具默认样式独立
        const hStyle = drawing.loadDrawingToolStyle('horizontal');
        const tStyle = drawing.loadDrawingToolStyle('trend');
        const rStyle = drawing.loadDrawingToolStyle('rectangle');
        const txtStyle = drawing.loadDrawingToolStyle('text');
        assert.equal(hStyle.color, '#2962ff');
        assert.equal(tStyle.color, '#2962ff');
        assert.equal(txtStyle.color, '#f0b90b');

        // 2. 用户在水平线上修改粗细与颜色
        controller.store.add(drawing.createHorizontalModel([{{time: 1, price: 100}}], {{id: 'h1'}}));
        controller.refresh();
        controller.select('h1');
        controller.updateSelectedLineSettings({{ color: '#e02424', lineWidth: 4, lineStyle: 'dashed' }});

        // 3. 验证水平线专属记忆已更新
        const newHStyle = drawing.loadDrawingToolStyle('horizontal');
        assert.equal(newHStyle.color, '#e02424');
        assert.equal(newHStyle.lineWidth, 4);
        assert.equal(newHStyle.lineStyle, 'dashed');

        // 4. 重点验证：趋势线、折线、矩形、文字等绝不继承水平线的改动！
        const trendStillDefault = drawing.loadDrawingToolStyle('trend');
        assert.equal(trendStillDefault.color, '#2962ff');
        assert.equal(trendStillDefault.lineWidth, 1);
        assert.equal(trendStillDefault.lineStyle, 'solid');

        const rectStillDefault = drawing.loadDrawingToolStyle('rectangle');
        assert.equal(rectStillDefault.color, '#2962ff');
        assert.equal(rectStillDefault.lineWidth, 1);

        // 5. 新建一根趋势线，应该继承趋势线自己的样式，而不是水平线的红线粗线
        const newTrendModel = controller._createModelForTool('trend', [{{time: 2, price: 50}}, {{time: 4, price: 60}}], 't_new');
        assert.equal(newTrendModel.options.color, '#2962ff');
        assert.equal(newTrendModel.options.lineWidth, 1);
        assert.equal(newTrendModel.options.lineStyle, 'solid');

        // 6. 新建一根水平线，应该继承水平线自己保存的样式
        const newHorizontalModel = controller._createModelForTool('horizontal', [{{time: 5, price: 80}}], 'h_new');
        assert.equal(newHorizontalModel.options.color, '#e02424');
        assert.equal(newHorizontalModel.options.lineWidth, 4);
        assert.equal(newHorizontalModel.options.lineStyle, 'dashed');

        // 7. 用户修改矩形填充与线条，矩形自己继承自己的
        controller.store.add(drawing.createRectangleModel([{{time: 10, price: 100}}, {{time: 20, price: 200}}], {{id: 'rect1'}}));
        controller.refresh();
        controller.select('rect1');
        controller.updateSelectedLineSettings({{ color: '#059669', fillColor: '#10b981', fillOpacity: 0.35, lineWidth: 2 }});
        const rectMem = drawing.loadDrawingToolStyle('rectangle');
        assert.equal(rectMem.color, '#059669');
        assert.equal(rectMem.fillColor, '#10b981');
        assert.equal(rectMem.fillOpacity, 0.35);
        assert.equal(rectMem.lineWidth, 2);

        // 再次验证水平线与趋势线没有被矩形覆盖
        assert.equal(drawing.loadDrawingToolStyle('horizontal').color, '#e02424');
        assert.equal(drawing.loadDrawingToolStyle('trend').color, '#2962ff');
        """
        completed = run_node(script)
        self.assertEqual(completed.returncode, 0, completed.stderr)


if __name__ == "__main__":
    unittest.main()
