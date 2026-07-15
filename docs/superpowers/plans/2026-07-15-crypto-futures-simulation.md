# Crypto Futures Simulation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add isolated-margin one-way USDT perpetual paper trading with market/limit orders, funding, mark-price liquidation, persistence, reports, and integrated browser controls.

**Architecture:** Implement pure decimal-safe simulator and order engine modules inside `backend.crypto`, then adapt them to crypto replay callbacks. Persist crypto events in additive tables and expose them through existing training envelopes while rendering a separate market-specific trading panel.

**Tech Stack:** Python Decimal/dataclasses/SQLite, Flask, JavaScript, HTML/CSS, unittest, browser acceptance.

---

### Task 1: Simulator models and account math

**Files:**
- Create: `backend/crypto/futures_models.py`
- Create: `backend/crypto/futures_simulator.py`
- Create: `tests/test_crypto_futures_simulator.py`

- [ ] Add failing tests for isolated USDT accounts, 1-20x validation, margin-to-quantity rounding, min quantity/notional, long/short unrealized P&L, equity, maintenance margin, margin ratio, average price, partial close, full close, reversal, and leverage changes only while flat.
- [ ] Verify RED.
- [ ] Implement Decimal-based `FuturesAccount`, `FuturesPosition`, `FuturesFill`, `FuturesSimulator`, and deterministic public dictionaries with JSON-safe floats/strings at the API boundary.
- [ ] Verify GREEN and commit `feat: add crypto futures account simulator`.

### Task 2: Orders and fills

**Files:**
- Create: `backend/crypto/futures_orders.py`
- Create: `tests/test_crypto_futures_orders.py`

- [ ] Add failing tests for market open long/open short/close, maker/taker fees, limit eligibility only on subsequent bars, crossing logic, reduce-only close, cancel, opposing-order reduction and reversal, precision, insufficient margin, and exact timestamps.
- [ ] Verify RED.
- [ ] Implement `FuturesOrderBook` and order/fill application APIs. Market fills use current revealed close; limit fills use the configured limit price when a later 5-minute bar crosses it.
- [ ] Verify GREEN and commit `feat: execute crypto futures orders`.

### Task 3: Funding and liquidation engine

**Files:**
- Create: `backend/crypto/futures_engine.py`
- Create: `tests/test_crypto_futures_engine.py`

- [ ] Add failing tests for positive/negative funding, long/short transfer signs, flat-position no-op, duplicate-event protection, funding-triggered liquidation, long low/short high mark-price checks, solved trigger price, liquidation priority, fee application, order cancellation, and nonnegative equity.
- [ ] Verify RED.
- [ ] Implement the per-base-bar event order from the approved spec. Use the source funding timestamp/rate and mark-price bar extremes; record every event.
- [ ] Verify GREEN and commit `feat: process funding and liquidation`.

### Task 4: Replay integration and equivalence

**Files:**
- Modify: `backend/crypto/session.py`
- Create: `backend/crypto/trading.py`
- Create: `tests/test_crypto_futures_replay.py`

- [ ] Add failing tests that join crypto advance plans, trade/mark bars, funding, order book, simulator, and clock commits. Compare large `1h/4h/daily/weekly` advances with repeated 5-minute advances.
- [ ] Verify RED.
- [ ] Implement replay callbacks and one sequential executor; snapshots include position, account, orders, funding/liquidation events, and markers.
- [ ] Verify GREEN and commit `feat: integrate futures trading with replay`.

### Task 5: Additive persistence and reports

**Files:**
- Create: `backend/crypto/persistence.py`
- Modify: `backend/history_manager.py`
- Modify: `backend/user_manager_enhanced.py`
- Create: `tests/test_crypto_futures_persistence.py`
- Create: `tests/test_crypto_futures_reports.py`

- [ ] Add failing migration tests for nullable session market metadata and new futures fills/orders/funding/liquidations/equity tables, repeatability, legacy rows, and rollback compatibility.
- [ ] Add failing report tests for realized/unrealized P&L, return, drawdown, fees, funding paid/received, liquidation metrics, win rate, leverage, source, and history rehydration after restart.
- [ ] Verify RED.
- [ ] Implement idempotent schema additions, event repositories, crypto report generation, and legacy defaults without changing A-share integer trade tables.
- [ ] Verify GREEN and commit `feat: persist crypto futures sessions`.

### Task 6: Flask order/account integration

**Files:**
- Modify: `backend/app_enhanced.py`
- Modify: `tests/test_crypto_api.py`
- Create: `tests/test_crypto_futures_api.py`

- [ ] Add failing API tests for `open_long/open_short/close`, market/limit bodies, leverage/margin validation, account, orders, cancellation, next-bar fills, funding, liquidation responses, marker semantics, reset/end, and legacy A-share route compatibility.
- [ ] Verify RED.
- [ ] Branch existing training trade/account/order/end routes by stored market type and return normalized crypto envelopes.
- [ ] Verify GREEN and commit `feat: expose crypto futures trading APIs`.

### Task 7: Frontend market setup and trading panel

**Files:**
- Modify: `frontend/index_enhanced.html`
- Modify: `frontend/css/style_enhanced.css`
- Modify: `frontend/js/main_enhanced.js`
- Create: `tests/test_crypto_frontend_static.py`

- [ ] Add failing static tests for A股/币圈 setup selector, async symbol search, seven periods, UTC+8 label, market-specific helper text, USDT capital, leverage/margin/order controls, 25/50/75/100 shortcuts, position/risk fields, pending orders, and explicit market-type branching.
- [ ] Verify RED.
- [ ] Implement setup payloads and active crypto trading panel without symbol-text inference. Preserve shared charts, drawings, indicators, replay controls, history windows, and report navigation.
- [ ] Render `L/S/X` markers separately from A-share `B/S` semantics and show all funding/liquidation messages.
- [ ] Run frontend/static tests, JS syntax checks, crypto APIs, and existing frontend suites; commit `feat: add crypto futures training interface`.

### Task 8: Final browser and regression acceptance

**Files:**
- Create: `docs/testing/crypto-futures-browser-acceptance.md`
- Modify: `scripts/quality_gate.py`
- Modify: `tests/test_quality_gate.py`
- Modify: `.agent/STATE.md`
- Create: `.agent/handoffs/2026-07-15-drawing-crypto-futures-complete.md`

- [ ] Add a `crypto` quality profile covering all crypto and drawing tests plus JS syntax checks.
- [ ] Browser-test BTCUSDT and ETHUSDT specified sessions, one blind-box session, market and limit long/short/close flows, positive or fixture-driven funding, forced liquidation, all seven periods, drawing tools, report completion, and history reload after Flask restart.
- [ ] Record console errors, HTTP 4xx/5xx, stale requests, concurrent `/next`, future leakage, and `.runtime/` exclusion.
- [ ] Run focused profiles, `python scripts/quality_gate.py full`, full unittest discovery, JS syntax checks, and `git diff --check`.
- [ ] Update state/handoff and commit `test: accept drawing and crypto futures training`.
