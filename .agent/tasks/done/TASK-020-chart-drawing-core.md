---
id: TASK-020
title: Implement chart drawing core
status: done
priority: P1
owner: Descartes
depends_on: []
write_scope:
  - frontend/js/drawing_tools.js
  - tests/test_drawing_tools_frontend.py
read_scope:
  - docs/superpowers/specs/2026-07-15-drawing-tools-crypto-futures-design.md
  - docs/superpowers/plans/2026-07-15-chart-drawing-tools.md
quality_profiles:
  - full
---

## Goal
Deliver tested drawing models, primitives, hit testing, and controller behavior without application integration.

## Non-Goals
- Do not modify HTML, CSS, main frontend logic, persistence, or backend code.

## Acceptance Criteria
- [x] Approved Fibonacci, ruler, risk/reward, editing, and history behavior are covered.
- [x] Node syntax and owned focused tests pass.

## Required Commands
```powershell
node --check frontend/js/drawing_tools.js
python -m unittest tests.test_drawing_tools_frontend -v
```
