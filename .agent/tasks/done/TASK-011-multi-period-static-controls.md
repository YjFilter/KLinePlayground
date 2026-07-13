---
id: TASK-011
title: Add multi-period static training controls
status: done
priority: P1
owner: workbuddy-011
depends_on:
  - TASK-005
write_scope:
  - frontend/index_enhanced.html
  - frontend/css/style_enhanced.css
read_scope:
  - frontend/js/main_enhanced.js
  - docs/superpowers/specs/2026-07-12-multi-timeframe-intraday-replay-design.md
quality_profiles:
  - frontend
---

## Goal
Add accessible static HTML/CSS controls for selecting and displaying `30m`, `4h_session`, `daily`, and `weekly` without changing JavaScript behavior yet.

## Required Elements
- Visible setup selector `#kline-period` with all four values and Chinese labels.
- Four `.view-period-btn` buttons with exact `data-period` values.
- Status elements: `#current-replay-time`, `#next-boundary-time`, and `#current-bar-status`.
- An incomplete-candle visual class that JavaScript can toggle later.
- Preserve existing IDs used by JavaScript and preserve daily as the default.

## Acceptance Criteria
- [ ] Setup selector contains all four exact values and daily remains selected.
- [ ] Training header contains four exact period buttons.
- [ ] Three replay status elements exist with readable labels.
- [ ] Incomplete-candle styling is present without altering unrelated layout.
- [ ] Existing JavaScript-dependent IDs are preserved.
- [ ] Frontend syntax/static validation passes.

## Constraints
Do not modify JavaScript, backend, tests, dependencies, agent files, or Git state. Do not redesign unrelated layout. Do not commit.

## Codex Acceptance
- Scope reviewed and accepted.
- Required focused tests or static checks passed.
- Public IDs and session snapshot contract were preserved.
