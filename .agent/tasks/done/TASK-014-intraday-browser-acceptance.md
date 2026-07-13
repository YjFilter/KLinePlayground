---
id: TASK-014
title: Perform independent intraday browser acceptance
status: done
priority: P0
owner: codex
depends_on:
  - TASK-013
write_scope:
  - docs/testing/phase4-intraday-browser-acceptance.md
read_scope:
  - frontend/index_enhanced.html
  - frontend/js/main_enhanced.js
  - frontend/css/style_enhanced.css
  - backend/app_enhanced.py
  - backend/intraday/session.py
quality_profiles:
  - frontend
---

## Goal
Independently exercise the completed intraday UI and API as a user, without modifying production code.

## Required Scenarios
- Open the enhanced frontend served by the project.
- Use specified mode with an A-share code supported by BaoStock and a date covered by available data/cache.
- Start each of 30m, 4h_session, daily, and weekly at least once, or clearly document any external data limitation.
- Confirm start shows the initial real timestamp without automatic advancement.
- Confirm Continue advances exactly one active-period unit.
- Confirm switching periods does not change current replay time.
- Confirm switching from 30m to daily shows the partial daily candle at the same time.
- Confirm current time, next boundary, and complete/incomplete status update.
- Confirm a market buy uses the currently displayed base close and account/pending-order panels remain usable.
- Confirm reset restores initial time and period.
- Confirm playback stops when paused and does not issue duplicate /next requests.
- Confirm random/box daily mode still starts through the legacy path.
- Inspect browser console and network failures.

## Evidence
Write docs/testing/phase4-intraday-browser-acceptance.md containing:
- Environment and exact server URL.
- Test data/code/date used.
- A pass/fail table for every required scenario.
- Before/after timestamps for Continue and period switching.
- Relevant HTTP status codes and response-shape observations.
- Browser console errors, if any.
- Any blocker caused by external BaoStock/network availability.

## Acceptance Criteria
- [x] All required scenarios have explicit evidence.
- [x] No production files were modified.
- [x] Any failure includes reproducible steps.
- [x] Browser and API observations are separated from assumptions.

## Constraints
Modify only the acceptance report. Do not modify frontend, backend, tests, dependencies, agent files, or Git state. Do not commit.


## Codex Acceptance
- No-patch production-entry browser retest completed on 2026-07-14.
- A-I scenarios: 9 Pass / 0 Fail / 0 Blocked.
- Intraday Console errors: 0; HTTP 4xx: 0; HTTP 5xx: 0.
- `/next` maximum concurrency: 1; stale replay plan: 0; post-pause requests: 0.
- Original FAIL evidence remains preserved in the acceptance report.
