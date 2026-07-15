---
id: TASK-021
title: Implement crypto data and replay core
status: done
priority: P1
owner: Dirac
depends_on: []
write_scope:
  - backend/crypto/
  - tests/fixtures/crypto/
  - tests/test_crypto_sources.py
  - tests/test_crypto_cache.py
  - tests/test_crypto_service.py
  - tests/test_crypto_universe.py
  - tests/test_crypto_aggregator.py
  - tests/test_crypto_replay_clock.py
  - tests/test_crypto_session.py
  - tests/test_crypto_no_future_leakage.py
  - tests/test_crypto_chart_window.py
read_scope:
  - backend/intraday/
  - docs/superpowers/specs/2026-07-15-drawing-tools-crypto-futures-design.md
  - docs/superpowers/plans/2026-07-15-crypto-data-replay.md
quality_profiles:
  - full
---

## Goal
Deliver fixture-tested Binance/Bybit normalization, monthly cache, universe, aggregation, chart windows, and 24x7 replay core.

## Non-Goals
- Do not modify Flask application integration, frontend, persistence, reports, or futures trading.

## Acceptance Criteria
- [x] All owned tests pass without live network access.
- [x] No A-share calendar or trading-rule dependency exists.

## Required Commands
```powershell
python -m unittest tests.test_crypto_sources tests.test_crypto_cache tests.test_crypto_service tests.test_crypto_universe tests.test_crypto_aggregator tests.test_crypto_replay_clock tests.test_crypto_session tests.test_crypto_no_future_leakage tests.test_crypto_chart_window -v
```
