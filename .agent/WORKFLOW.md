# Agent Workflow

## Lifecycle
`backlog -> ready -> active -> review -> done`

A task may move to `blocked` from any non-final state. A rejected review returns to `ready` with explicit rework instructions.

## Backlog
The idea is relevant but priority, scope, dependency, or acceptance details are incomplete.

## Ready
The task has one observable goal, non-goals, owner policy, exclusive write scope, dependencies, acceptance criteria, required commands, and result contract.

## Active
The task has one assigned owner. Its write scope is locked. Files outside the scope are read-only.

## Review
The worker has supplied changed files, summary, commands actually run, results, risks, and unresolved items. Codex checks scope, diff, architecture impact, and quality evidence.

## Done
Only Codex may mark a task done. Acceptance criteria and mandatory quality profiles must pass.

## Blocked
The task states the blocking condition, evidence, attempted actions, required decision or dependency, and safe next step.

## Delegation Rules
- Delegate low-risk, bounded work with minimal cross-module context.
- Codex retains architecture, core trading rules, persistence changes, integration, and final acceptance.
- Do not assign two active tasks overlapping write paths.
- A worker must stop rather than edit outside scope.

## Result and Handoff
Use `.agent/templates/result.md` for task results and `.agent/templates/handoff.md` at the end of substantial sessions. Update `.agent/STATE.md` whenever milestone, blocker, active work, or recommended next action changes.
