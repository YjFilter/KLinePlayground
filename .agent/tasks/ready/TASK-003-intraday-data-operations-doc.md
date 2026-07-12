---
id: TASK-003
title: Document intraday data operations
status: ready
priority: P2
owner: unassigned
depends_on:
  - TASK-002
write_scope:
  - docs/intraday-data-operations.md
read_scope:
  - backend/intraday
  - scripts/verify_baostock_30m.py
  - .agent/QUALITY_GATES.md
quality_profiles:
  - control-plane
---

## Background
Phase 1 added a BaoStock-backed five-year 30-minute data foundation, but operators need a concise guide for verification, optional cache creation, cache layout, failure handling, and the Beijing Exchange limitation.

## Goal
Create one practical operations guide that lets a user verify and maintain intraday data without reading implementation code.

## Non-Goals
- Do not modify Python, JavaScript, dependencies, tests, or existing agent-control files.
- Do not design aggregation, replay-clock, API, or UI behavior.

## Constraints
- Treat files outside `write_scope` as read-only.
- Document only commands and behavior confirmed by the repository.
- Stop and report a blocker instead of changing implementation when documentation and code disagree.

## Acceptance Criteria
- [ ] Explain the canonical 30-minute columns and supported Shanghai/Shenzhen symbols.
- [ ] Document live verification for one stock and the three representative stocks.
- [ ] Document `--save-cache`, `--cache-root`, cache-first behavior, and validation failure behavior.
- [ ] State the Beijing Exchange prefix limitation and current safe response.
- [ ] Include troubleshooting for network failure, insufficient coverage, and invalid data.
- [ ] `python scripts/quality_gate.py control-plane` passes.

## Required Commands
```powershell
python scripts/verify_baostock_30m.py --help
python scripts/quality_gate.py control-plane
```

## Result Contract
Move this task to `.agent/tasks/review/` and create a result report from `.agent/templates/result.md`. List the exact file changed and commands actually run. Do not mark the task done and do not commit.
