---
id: TASK-001
title: Bootstrap repository-native Agent control plane
status: done
priority: P0
owner: codex
depends_on: []
write_scope:
  - AGENTS.md
  - .agent
  - scripts/agent_status.py
  - scripts/project_snapshot.py
  - scripts/quality_gate.py
  - tests/test_agent_status.py
  - tests/test_project_snapshot.py
  - tests/test_quality_gate.py
  - .github/workflows/quality.yml
  - .gitignore
read_scope:
  - backend
  - frontend
  - webview_app
  - tests/test_trading_rules.py
quality_profiles:
  - control-plane
  - backend
  - frontend
  - full
---

## Background
The project needs a repository-native control plane so Codex can restore context, delegate bounded tasks to external AI workers, validate ownership, and accept work using repeatable evidence.

## Goal
Establish the first usable collaboration foundation without changing pre-existing business code.

## Non-Goals
- Refactor Flask, frontend, market data, trading, persistence, or packaging behavior.
- Commit, push, release, or discard existing changes.

## Constraints
- Preserve all pre-existing user changes.
- Keep business files read-only.
- Use only Python standard library for control scripts.

## Acceptance Criteria
- [x] Repository roles, safety, workflow, project state, roadmap, architecture, domain rules, and quality gates are documented.
- [x] Standard task, result, handoff, and ADR templates exist.
- [x] Task metadata and overlapping active write scopes are validated automatically.
- [x] A generated snapshot restores project state, task counts, latest handoff, and Git status.
- [x] Named quality profiles execute deterministic commands and propagate failures.
- [x] Full local quality profile passes.
- [x] Codex reviews the result and moves this task to done.

## Required Commands
```powershell
python scripts/quality_gate.py full
python scripts/agent_status.py .agent/tasks
git diff --check
```

## Result Contract
Codex records exact verification results in the final handoff and moves this task to done only after all mandatory checks pass.

