---
id: TASK-000
title: Replace with a concrete outcome
status: ready
priority: P2
owner: unassigned
depends_on: []
write_scope:
  - path/to/owned-file
read_scope:
  - path/to/reference-file
quality_profiles:
  - control-plane
---

## Background
Explain why this task matters and what current behavior or project goal it supports.

## Goal
State one observable outcome.

## Non-Goals
- State what must not change.

## Constraints
- Preserve pre-existing user changes.
- Treat files outside `write_scope` as read-only.
- Stop and report a blocker if the required solution exceeds this scope.

## Acceptance Criteria
- [ ] State verifiable behavior.
- [ ] Required quality profiles pass.
- [ ] Result report lists commands actually executed.

## Required Commands
```powershell
python scripts/quality_gate.py control-plane
```

## Result Contract
Move the task to `.agent/tasks/review/` and attach a result report using `.agent/templates/result.md`. Do not mark the task done.
