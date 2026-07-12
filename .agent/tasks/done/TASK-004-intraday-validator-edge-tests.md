---
id: TASK-004
title: Expand intraday validator edge-case tests
status: done
priority: P2
owner: test-agent
depends_on:
  - TASK-002
write_scope:
  - tests/fixtures/intraday/validator_edge_cases.csv
  - tests/test_intraday_validator_edge_cases.py
read_scope:
  - backend/intraday/validator.py
  - backend/intraday/models.py
  - tests/test_intraday_validator.py
  - tests/fixtures/intraday/600000_30m_sample.csv
quality_profiles:
  - intraday
---

## Background
The validator has focused unit coverage. Additional black-box edge cases can strengthen confidence without changing production behavior or sharing files with the Phase 2 core implementation.

## Goal
Add deterministic tests covering valid multi-day input and boundary failures that are not already asserted by `tests/test_intraday_validator.py`.

## Non-Goals
- Do not modify anything under `backend/`.
- Do not change existing tests, quality-gate configuration, dependencies, replay, trading, API, or frontend files.
- Do not use live network data.

## Constraints
- Treat files outside `write_scope` as read-only.
- Tests must assert public validation results rather than internal implementation details.
- If a test exposes a likely production defect, leave the failing test clearly identified and report the blocker; do not patch production code.

## Acceptance Criteria
- [ ] Add a reusable deterministic fixture or construct equivalent deterministic rows in the new test file.
- [ ] Cover a valid two-trading-day frame.
- [ ] Cover at least three distinct untested boundaries, such as unsorted timestamps, null numeric values, nonnumeric values, or high/low equality boundaries.
- [ ] Avoid duplicating existing duplicate-time, illegal-session, incomplete-day, invalid-OHLC, and negative-volume assertions unless extending a genuinely different boundary.
- [ ] `python -m unittest tests.test_intraday_validator_edge_cases -v` passes.
- [ ] `python scripts/quality_gate.py intraday` passes.

## Required Commands
```powershell
python -m unittest tests.test_intraday_validator_edge_cases -v
python scripts/quality_gate.py intraday
```

## Result Contract
Move this task to `.agent/tasks/review/` and create a result report from `.agent/templates/result.md`. List changed files, test cases added, commands actually run, and any suspected production defect. Do not mark the task done and do not commit.


## Codex Acceptance
- Accepted after scope review and independent quality-gate verification.
- Codex fixed the reported invalid volume/amount validation defect and updated the edge tests to assert the intended behavior.
- The new edge-case suite is now included in the `intraday` and `full` quality profiles.
