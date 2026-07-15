# Chart Drawing Tools Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add session-only TradingView-style drawing tools to active and historical charts, matching the approved Fibonacci, ruler, and risk/reward visuals.

**Architecture:** Implement a standalone `KLineDrawingTools` browser module with pure geometry/statistics helpers, Lightweight Charts Series Primitives, and one controller for input/history/selection. Keep DOM integration thin in `main_enhanced.js`; drawings use timestamp/price anchors and are never persisted.

**Tech Stack:** JavaScript, Lightweight Charts v5.0.8 Series Primitive API, HTML/CSS, Python unittest static/runtime tests, browser acceptance.

---

### Task 1: Pure drawing models and calculations

**Files:**
- Create: `frontend/js/drawing_tools.js`
- Create: `tests/test_drawing_tools_frontend.py`

- [ ] Write failing Node-backed tests for the approved Fibonacci defaults and color groups, interpolation and reverse mode, ruler delta/percent/bar/bull/bear/duration metrics, three-point long/short risk-reward metrics, immutable command history, and timestamp/price anchor serialization.
- [ ] Run `python -m unittest tests.test_drawing_tools_frontend.DrawingMathRuntimeTests -v`; expect failures because the module does not exist.
- [ ] Implement a UMD module exporting `DEFAULT_FIBONACCI_LEVELS`, `calculateFibonacciLevels`, `calculateRulerMetrics`, `calculateRiskReward`, `DrawingStore`, and model factories. Reject non-finite coordinates and invalid long/short point ordering.
- [ ] Re-run the focused tests and `node --check frontend/js/drawing_tools.js`; expect PASS.
- [ ] Commit `test: define drawing tool models and metrics`.

### Task 2: Primitive rendering and hit testing

**Files:**
- Modify: `frontend/js/drawing_tools.js`
- Modify: `tests/test_drawing_tools_frontend.py`

- [ ] Add failing tests with a fake chart/series API for primitive attach/detach, coordinate projection, z-order, clipping, anchor handles, hit regions, selected/locked/hidden state, and update requests.
- [ ] Run the primitive test class and confirm expected missing-renderer failures.
- [ ] Implement primitive adapters and pane renderers for trend, horizontal, ray, rectangle, text, Fibonacci, ruler, and long/short risk-reward drawings. Use `timeToCoordinate`, `priceToCoordinate`, pixel-ratio-aware canvas rendering, and no autoscale expansion.
- [ ] Re-run runtime tests and syntax checks; expect PASS.
- [ ] Commit `feat: render chart drawing primitives`.

### Task 3: Drawing controller and editing

**Files:**
- Modify: `frontend/js/drawing_tools.js`
- Modify: `tests/test_drawing_tools_frontend.py`

- [ ] Add failing tests for tool activation, two-point and three-point creation, select/body drag/anchor drag, lock/hide/delete, `Escape`, `Delete`, undo/redo, clear-all, and touch-pointer normalization.
- [ ] Verify RED with the controller test class.
- [ ] Implement `DrawingController` with one active gesture, one selected drawing, command snapshots, pointer capture cleanup, keyboard guards for inputs, and explicit `destroy()`.
- [ ] Verify GREEN and run all drawing tests.
- [ ] Commit `feat: add drawing interaction controller`.

### Task 4: Toolbar, settings, and chart lifecycle integration

**Files:**
- Modify: `frontend/index_enhanced.html`
- Modify: `frontend/css/style_enhanced.css`
- Modify: `frontend/js/main_enhanced.js`
- Modify: `tests/test_drawing_tools_frontend.py`

- [ ] Add failing static tests for script order, left toolbar buttons, accessible labels/tooltips, selected state, Fibonacci settings panel, edit actions, and explicit drawing-controller hooks in chart initialization, period changes, chart-window merges, resize, report view, and teardown.
- [ ] Run static tests and confirm failures.
- [ ] Load `drawing_tools.js` before `main_enhanced.js`; add the compact left toolbar and settings panel. Initialize one controller after candlestick creation, feed current rendered bars to it, notify it after chart data changes, and destroy it when the chart is recreated. Do not clear drawings on period changes; clear on page refresh/new training/history exit.
- [ ] Add CSS matching the current dark/light themes without increasing the compact top bars. Ensure the toolbar does not cover price-axis labels and collapses to an expandable rail on narrow screens.
- [ ] Run drawing tests plus existing chart-workspace/frontend tests and both JS syntax checks.
- [ ] Commit `feat: integrate chart drawing toolbar`.

### Task 5: Browser acceptance

**Files:**
- Create: `docs/testing/chart-drawing-tools-browser-acceptance.md`
- Modify: `.agent/STATE.md`
- Create: `.agent/handoffs/2026-07-15-chart-drawing-tools-complete.md`

- [ ] Start or reuse `http://127.0.0.1:5000/` and exercise active A-share training plus completed history.
- [ ] Verify every tool creates, selects, moves, locks, hides, deletes, undoes, and redoes without console errors.
- [ ] Compare Fibonacci labels/colors/handles/guide and ruler geometry/statistics to the two approved screenshots at desktop size; capture exact dimensions and values in the report.
- [ ] Switch periods and paginate history, confirming timestamp/price anchors persist and counts recalculate.
- [ ] Run focused tests, `python -m unittest discover -s tests -v`, JS syntax checks, and `git diff --check`.
- [ ] Update state/handoff and commit `test: accept chart drawing tools`.
