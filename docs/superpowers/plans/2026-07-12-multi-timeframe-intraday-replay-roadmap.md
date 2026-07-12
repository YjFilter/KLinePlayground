# Multi-Timeframe Intraday Replay Delivery Roadmap

**Goal:** Deliver 30-minute, A-share-session 4-hour, daily, and weekly replay with period-dependent time flow, no future leakage, and compatibility with existing daily training.

**Architecture:** Implement five independently testable phases. Each phase passes its quality gate and updates project state before the next begins. The existing uncommitted business redesign must first become an accepted Git baseline or be isolated from feature work.

**Tech Stack:** Python 3.11, Flask, pandas, BaoStock, unittest, Lightweight Charts, repository Agent control plane.

---

## Required Sequence

1. **Phase 0 - Baseline prerequisite**
   - Review the existing uncommitted business redesign.
   - Run the full quality gate.
   - Commit or isolate that baseline so feature work can use a clean branch/worktree.

2. **Phase 1 - Intraday data foundation**
   - Add BaoStock and an isolated `backend/intraday/` package.
   - Normalize, validate, cache, and incrementally synchronize five years of 30-minute data.
   - Add offline unit tests and optional live verification.
   - Detailed plan: `docs/superpowers/plans/2026-07-12-intraday-data-foundation.md`.

3. **Phase 2 - Aggregation and replay clock**
   - Implement `30m`, `4h_session`, `daily`, and `weekly` models.
   - Aggregate incomplete candles from revealed base bars only.
   - Compute next boundaries across lunch, holidays, suspensions, and short weeks.

4. **Phase 3 - Trading engine adaptation**
   - Add full trade timestamps while preserving `trade_date`.
   - Use previous-trading-day close for intraday limit rules.
   - Process hidden 30-minute bars sequentially during large jumps.
   - Preserve T+1 and independent same-day trade ordering.

5. **Phase 4 - API and frontend**
   - Add period selection and switching endpoints.
   - Return current time, next boundary, base interval, and incomplete-candle state.
   - Add four period buttons, intraday formatting, incomplete-candle presentation, and period-aware autoplay.

6. **Phase 5 - Reports and acceptance**
   - Store data mode, intervals, timestamps, and trade times.
   - Keep legacy daily sessions and reports readable.
   - Run real-stock cross-period acceptance scenarios and update packaging/release documentation.

## Phase Gates

- No phase edits files owned by an unreviewed active task.
- New behavior follows test-first development.
- Live BaoStock checks provide optional integration evidence; offline CI remains deterministic.
- Network failure may block synchronization but cannot invalidate usable cache.
- A phase completes only after Codex review, task closure, state update, and handoff.
