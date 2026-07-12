# KLine Training and Review Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repair persisted report identity and deliver a dark/light adaptive training, report, and history experience.

**Architecture:** The Flask API remains the source of truth for session/report persistence. The existing vanilla JavaScript frontend keeps its current modules but adds small UI state helpers and semantic containers; CSS supplies responsive layout and theme-aware cards.

**Tech Stack:** Flask, SQLite, vanilla JavaScript, CSS, Lightweight Charts, Python unittest.

---

### Task 1: Preserve report session identity

**Files:**
- Modify: `backend/app_enhanced.py`
- Modify: `backend/trade_simulator_enhanced.py`
- Modify: `tests/test_trading_rules.py`

- [ ] Add a regression test that ends a controlled training and asserts the API report and its persisted report data both contain the original session ID.
- [ ] Set `report['session_id'] = training_id` immediately after report generation in the natural-completion and explicit-end code paths, before persistence and JSON response.
- [ ] Run `python -m unittest discover -s tests -v`.

### Task 2: Make summary saving resilient

**Files:**
- Modify: `frontend/js/main_enhanced.js`
- Modify: `backend/history_manager.py`

- [ ] Resolve a report session ID from `report.session_id`, then the active training ID only when it is the same report session.
- [ ] Render an inline success/error status on the review summary card instead of relying solely on browser alerts.
- [ ] Verify the history summary API accepts the saved session ID through Flask test client coverage.

### Task 3: Refactor training workspace

**Files:**
- Modify: `frontend/index_enhanced.html`
- Modify: `frontend/css/style_enhanced.css`
- Modify: `frontend/js/main_enhanced.js`

- [ ] Add semantic workspace/console containers without altering existing IDs used by JavaScript.
- [ ] Group order type, direction, sizing, risk inputs, optional reason entry, account metrics, position data, and pending orders into visually distinct sections.
- [ ] Implement responsive CSS so desktop has a persistent right console and narrow windows stack controls below charts.

### Task 4: Refactor report and history cards

**Files:**
- Modify: `frontend/index_enhanced.html`
- Modify: `frontend/css/style_enhanced.css`
- Modify: `frontend/js/main_enhanced.js`

- [ ] Add report header/metric containers and history filter controls while preserving open/delete APIs.
- [ ] Render report summary data, summary save status, and trade reasons using theme-aware cards.
- [ ] Add history filtering in JavaScript for all/completed/with-summary records with accessible empty states.

### Task 5: Verify end-to-end behavior

**Files:**
- Test: `tests/test_trading_rules.py`

- [ ] Run JavaScript syntax check: `node --check frontend/js/main_enhanced.js`.
- [ ] Run backend compile check: `python -m compileall -q backend`.
- [ ] Run unit tests: `python -m unittest discover -s tests -v`.
- [ ] Start Flask locally and use its test client to verify the history GET, DELETE, and summary POST routes.
- [ ] Inspect `git diff --check` for whitespace errors.
