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

    def test_ruler_metrics_cover_delta_percent_bars_direction_and_duration(self):
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
              {{time: 1000, open: 10, close: 11}},
              {{time: 1060, open: 11, close: 10}},
              {{time: 1120, open: 10, close: 10}},
              {{time: 1180, open: 10, close: 12}},
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
        assert.ok(operations.some(operation => operation[0] === 'fillText' && String(operation[1]).includes('盈亏比')));
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

    def test_ruler_renderer_uses_bars_duration_direction_color_and_arrow(self):
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
            {{time: 1000, open: 10, close: 11}},
            {{time: 1060, open: 11, close: 10}},
            {{time: 1180, open: 10, close: endPrice}},
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
        assert.ok(bull.some(op => op[0] === 'set' && op[1] === 'fillStyle' && op[2].includes('38, 166, 154')));
        assert.ok(bear.some(op => op[0] === 'set' && op[1] === 'fillStyle' && op[2].includes('239, 83, 80')));
        assert.ok(bull.some(op => op[0] === 'fillText' && String(op[1]).includes('3m')));
        assert.ok(bull.some(op => op[0] === 'setLineDash'));
        assert.ok(bull.filter(op => op[0] === 'lineTo').length >= 5);
        """
        completed = run_node(script)
        self.assertEqual(completed.returncode, 0, completed.stderr)


    def test_risk_renderer_uses_chinese_colored_account_position_and_ratio_labels(self):
        script = f"""
        const drawing = require({json.dumps(str(DRAWING_TOOLS_PATH))});
        const assert = require('node:assert/strict');
        const operations = [];
        const context = new Proxy({{measureText: text => ({{width: text.length * 7}})}}, {{
          get(target, key) {{ if (key in target) return target[key]; return (...args) => operations.push([key, ...args]); }},
          set(target, key, value) {{ operations.push(['set', key, value]); target[key] = value; return true; }}
        }});
        const model = drawing.createDrawingModel('long-position', [
          {{time: 10, price: 100}}, {{time: 20, price: 90}}, {{time: 20, price: 115}}
        ], {{accountSize: 10000, accountRiskAmount: 200, positionSize: 2}});
        const primitive = new drawing.DrawingPrimitive(model);
        primitive.attached({{
          chart: {{timeScale: () => ({{timeToCoordinate: value => value}})}},
          series: {{priceToCoordinate: value => 200 - value}}, requestUpdate() {{}},
        }});
        primitive.paneViews()[0].renderer().draw({{useBitmapCoordinateSpace(callback) {{
          callback({{context, horizontalPixelRatio: 1, verticalPixelRatio: 1,
            bitmapSize: {{width: 400, height: 300}}, mediaSize: {{width: 400, height: 300}}}});
        }}}});
        const labels = operations.filter(op => op[0] === 'fillText').map(op => op[1]);
        for (const text of ['入场', '止损', '止盈', '账户 10000.00', '仓量 2', '盈亏比 1.50']) {{
          assert.ok(labels.some(label => String(label).includes(text)), text);
        }}
        assert.ok(operations.filter(op => op[0] === 'fillRect').length >= 6);
        assert.ok(operations.some(op => op[0] === 'set' && op[1] === 'fillStyle' && op[2] === '#ef5350'));
        assert.ok(operations.some(op => op[0] === 'set' && op[1] === 'fillStyle' && op[2] === '#26a69a'));
        """
        completed = run_node(script)
        self.assertEqual(completed.returncode, 0, completed.stderr)

class DrawingControllerRuntimeTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
