# Crypto Data and Replay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Binance-primary/Bybit-fallback USDT perpetual data, monthly 5-minute caching, dynamic top-50 instruments, seven-period no-future-leakage aggregation, and 24x7 replay.

**Architecture:** Create an isolated `backend.crypto` domain with normalized source protocols and fixtures, compressed monthly cache, source router, universe selector, UTC aggregation, replay clock/session, and chart-window service. Flask integration remains thin and A-share modules remain unchanged.

**Tech Stack:** Python 3.11, dataclasses, pandas, requests, gzip CSV, Flask, unittest.

---

### Task 1: Contracts and source adapters

**Files:**
- Create: `backend/crypto/__init__.py`
- Create: `backend/crypto/models.py`
- Create: `backend/crypto/source.py`
- Create: `backend/crypto/binance_source.py`
- Create: `backend/crypto/bybit_source.py`
- Create: `tests/fixtures/crypto/binance_*.json`
- Create: `tests/fixtures/crypto/bybit_*.json`
- Create: `tests/test_crypto_sources.py`

- [ ] Write failing fixture-only tests for normalized instruments, trade bars, mark bars, funding events, pagination direction, UTC timestamps, decimal precision, and actionable HTTP/schema failures.
- [ ] Run `python -m unittest tests.test_crypto_sources -v`; expect import failures.
- [ ] Implement immutable models `CryptoInstrument`, `CryptoBar`, `FundingEvent`, `SourceStatus`, a `CryptoMarketSource` protocol, and request-injected Binance/Bybit adapters. Never call live APIs in tests.
- [ ] Re-run tests and commit `feat: add crypto market source adapters`.

### Task 2: Monthly cache and validation

**Files:**
- Create: `backend/crypto/validator.py`
- Create: `backend/crypto/cache.py`
- Create: `tests/test_crypto_cache.py`

- [ ] Add failing tests for required columns, 5-minute UTC alignment, ordering, duplicates, non-finite/invalid OHLC, monthly segmentation, compressed atomic save, merge, coverage, source isolation, corruption, and missing ranges.
- [ ] Verify RED.
- [ ] Implement validation and `CryptoMonthlyCache` under `data/crypto/{source}/{symbol}/{kind}/{YYYY-MM}.csv.gz` with JSON metadata and same-directory temp replacement.
- [ ] Verify GREEN and commit `feat: cache normalized crypto candles`.

### Task 3: Source routing and synchronization

**Files:**
- Create: `backend/crypto/service.py`
- Create: `tests/test_crypto_service.py`

- [ ] Add failing tests for Binance preference, Bybit fallback before session creation, no mixed-source ranges, complete trade/mark coverage requirements, cache-only success, partial-cache rejection, bounded pagination, and funding deduplication.
- [ ] Verify RED.
- [ ] Implement `CryptoDataService` returning a source-pinned `CryptoDataBundle` containing aligned trade bars, mark bars, funding, and instrument rules.
- [ ] Verify GREEN and commit `feat: synchronize crypto replay data`.

### Task 4: Dynamic universe and blind-box selection

**Files:**
- Create: `backend/crypto/universe.py`
- Create: `tests/test_crypto_universe.py`

- [ ] Add failing tests for active USDT perpetual filtering, 180-day minimum age, turnover ranking/top-50 truncation, search outside top 50, deterministic injected randomness, bounded retries, and useful empty-universe errors.
- [ ] Verify RED.
- [ ] Implement cached instrument snapshots and `CryptoUniverse.select_random()` using dependency-injected time and RNG.
- [ ] Verify GREEN and commit `feat: add crypto perpetual universe`.

### Task 5: Aggregation, clock, and session

**Files:**
- Create: `backend/crypto/aggregator.py`
- Create: `backend/crypto/replay_clock.py`
- Create: `backend/crypto/session.py`
- Create: `tests/test_crypto_aggregator.py`
- Create: `tests/test_crypto_replay_clock.py`
- Create: `tests/test_crypto_session.py`
- Create: `tests/test_crypto_no_future_leakage.py`

- [ ] Add failing tests for `5m/15m/30m/1h/4h/daily/weekly`, UTC day/week boundaries, partial bars, 24x7 midnight/weekend/year transitions, pure advance plans, stale-plan rejection, period switching, calendar-day cutoff, and future OHLCV mutation invariance.
- [ ] Verify RED for each focused class before implementation.
- [ ] Implement revealed-only aggregation and a canonical 5-minute replay clock/session modeled on intraday public contracts but without trading calendars.
- [ ] Verify focused and combined crypto tests; commit `feat: add 24x7 crypto replay engine`.

### Task 6: Chart windows and Flask data APIs

**Files:**
- Create: `backend/crypto/chart_window.py`
- Modify: `backend/app_enhanced.py`
- Create: `tests/test_crypto_api.py`
- Create: `tests/test_crypto_chart_window.py`

- [ ] Add failing tests for `/api/crypto/instruments`, `/api/crypto/sources/status`, crypto `POST /api/training/start`, data/next/period/reset/chart-window, specified and random starts, market metadata, source pinning, future caps, completed read-only windows, and A-share compatibility.
- [ ] Verify RED.
- [ ] Add lazy crypto service construction, constants `crypto_perpetual`/`crypto_5m`, thin market-discriminated route branches, and crypto session storage in `active_trainings`.
- [ ] Verify focused APIs, all intraday APIs, and commit `feat: expose crypto replay APIs`.

### Task 7: Data/replay acceptance

**Files:**
- Create: `docs/testing/crypto-data-replay-acceptance.md`
- Modify: `.agent/STATE.md`
- Create: `.agent/handoffs/2026-07-15-crypto-data-replay-complete.md`

- [ ] Run live smoke fetches for BTCUSDT and ETHUSDT against Binance and Bybit, recording status/latency without checking data into Git.
- [ ] Start specified BTCUSDT and blind-box sessions, switch all seven periods, advance across UTC midnight/weekend, and verify no future data.
- [ ] Run all crypto data tests, the existing intraday quality profile, full suite, and `git diff --check`.
- [ ] Update state/handoff and commit `test: accept crypto data replay`.
