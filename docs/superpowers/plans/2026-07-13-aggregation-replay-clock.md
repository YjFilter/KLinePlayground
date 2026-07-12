# Phase 2 Aggregation and Replay Clock Implementation Plan

**Goal:** Provide deterministic `30m`, `4h_session`, `daily`, and `weekly` aggregation plus a period-aware replay clock over the canonical real 30-minute timeline, without modifying trading, Flask API, frontend, reports, or persistence.

**Architecture:** `models.py` owns public period and result contracts. `replay_clock.py` owns immutable timeline boundaries and advance plans. `aggregator.py` owns revealed-only OHLCV aggregation and consumes clock boundary knowledge for completion state. Production modules remain independent of Flask and trading state.

## Task 1 - Public contracts (Codex)
- Add `ReplayPeriod`, `PeriodBoundaryIndex`, `ReplayAdvance`, and aggregation column constants to `backend/intraday/models.py`.
- Export contracts through `backend/intraday/__init__.py`.
- Preserve all Phase 1 models.

## Task 2 - Deterministic fixtures (Agent)
- Add a multi-period fixture spanning complete sessions, lunch, a weekend, a short trading week, and an incomplete session.
- Do not modify Python code.

## Task 3 - Replay clock (Agent)
- Implement timeline normalization, session/week boundary indexes, period switching, pure advance planning, and explicit commit.
- Return every underlying timestamp in `(current_time, target_time]`.
- Compute boundaries from actual timestamps, never natural-day arithmetic.

## Task 4 - Aggregator (Agent)
- Implement revealed-only four-period aggregation.
- Never include OHLCV after `current_time`.
- Mark completion using `PeriodBoundaryIndex` and session completeness.

## Task 5 - Integration tests (Codex)
- Add strong no-future-leakage and cross-module tests.
- Add Phase 2 quality profile and include it in full.
- Review agent implementations and repair contract deviations.

## Task 6 - Close phase
- Run Phase 2 and full quality gates.
- Update task lifecycle, state, snapshot, and handoff.
- Commit only after Codex acceptance.
