---
id: TASK-022
title: Implement crypto futures simulation core
status: done
priority: P1
owner: Noether
depends_on:
  - TASK-021
write_scope:
  - backend/crypto/futures_models.py
  - backend/crypto/futures_simulator.py
  - backend/crypto/futures_orders.py
  - backend/crypto/futures_engine.py
  - backend/crypto/trading.py
  - backend/crypto/persistence.py
  - tests/test_crypto_futures_simulator.py
  - tests/test_crypto_futures_orders.py
  - tests/test_crypto_futures_engine.py
  - tests/test_crypto_futures_replay.py
  - tests/test_crypto_futures_persistence.py
  - tests/test_crypto_futures_reports.py
read_scope:
  - backend/crypto/
  - docs/superpowers/specs/2026-07-15-drawing-tools-crypto-futures-design.md
  - docs/superpowers/plans/2026-07-15-crypto-futures-simulation.md
quality_profiles:
  - full
---

## Goal
Deliver tested isolated-margin long/short simulation, orders, funding, liquidation, replay adapter, and crypto event persistence.

## Non-Goals
- Do not modify Flask routes, frontend, A-share simulator tables, docs, or state.

## Acceptance Criteria
- [x] Decimal-safe simulator and deterministic event ordering pass focused tests.
- [x] Persistence is additive and legacy-compatible.

## Required Commands
```powershell
python -m unittest tests.test_crypto_futures_simulator tests.test_crypto_futures_orders tests.test_crypto_futures_engine tests.test_crypto_futures_replay tests.test_crypto_futures_persistence tests.test_crypto_futures_reports -v
```
