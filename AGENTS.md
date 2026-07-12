# AI Collaboration Rules

## Source of Truth
`.agent/STATE.md`, `.agent/ROADMAP.md`, active task packets, Git state, and automated test output are authoritative. Chat history is supplementary only.

## Roles
Codex owns architecture, planning, complex implementation, integration, review, global state, and final acceptance. External workers execute only task packets in `.agent/tasks/ready/`.

## File Ownership
Every active task declares an exclusive `write_scope`. Files outside that scope are read-only. Two active tasks may not own the same file or overlapping directory trees.

## Existing Changes
Never discard, overwrite, move, reformat, stage, or commit pre-existing user changes unless the current task explicitly owns them and the project owner approves the action.

## Safety
Never delete user data. Never change persistence formats, public APIs, trading invariants, release state, or secrets handling without explicit approval and a migration and rollback plan.

## Task Execution
Read the assigned task packet, relevant project memory, and applicable nested `AGENTS.md` files before editing. Stop and report a blocker when the required solution exceeds the declared scope.

## Verification
Run every command listed in the task packet. Record commands actually executed and their results. Natural-language claims are not verification evidence.

## Completion
Workers move completed work to review and attach a result report. Only Codex may mark a task done after checking the diff, acceptance criteria, and required quality gates.

## Required Handoff
Every substantial work session updates `.agent/STATE.md` and writes a handoff with completed work, active or blocked tasks, Git status, verification, decisions, risks, and the next action.
