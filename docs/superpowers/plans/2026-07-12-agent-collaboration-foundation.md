# Agent Collaboration Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Build the first usable repository-native control plane so Codex can restore project context, create safe task packets for external AI workers, validate task metadata, and run a repeatable baseline quality gate.

**Architecture:** Keep orchestration state as versionable Markdown and YAML-like front matter under `.agent/`, with small Python standard-library scripts for validation and snapshots. Do not refactor current Flask or frontend business code in this plan; first protect the dirty working tree, document the existing architecture and domain rules, then prove one complete task lifecycle.

**Tech Stack:** Markdown, Python 3 standard library, `unittest`, existing Flask application and test suite, GitHub Actions YAML.

---

## Scope Boundary

This plan implements design milestones M0 and M1 plus a minimal CI entry point. It intentionally defers large JavaScript/Flask/data-manager decomposition and broad test expansion to separate plans after the current working tree becomes a reviewed baseline.

## File Map

- Create `AGENTS.md`: repository-wide AI collaboration constitution and safety rules.
- Create `.agent/PROJECT.md`: product purpose, users, scope, success metrics, and non-goals.
- Create `.agent/STATE.md`: current baseline, dirty-tree warning, active milestone, blockers, and next actions.
- Create `.agent/ROADMAP.md`: M0-M4 milestones and completion criteria.
- Create `.agent/ARCHITECTURE.md`: current runtime entry points, modules, data flow, and hotspots.
- Create `.agent/DOMAIN_RULES.md`: protected A-share trading invariants.
- Create `.agent/QUALITY_GATES.md`: conditional and mandatory verification commands.
- Create `.agent/WORKFLOW.md`: task lifecycle, ownership, delegation, review, and handoff rules.
- Create `.agent/templates/task.md`: standard task packet.
- Create `.agent/templates/result.md`: worker result report.
- Create `.agent/templates/handoff.md`: session handoff record.
- Create `.agent/templates/adr.md`: architecture decision record.
- Create `.agent/tasks/{backlog,ready,active,review,done,blocked}/.gitkeep`: persistent task-state directories.
- Create `.agent/handoffs/.gitkeep` and `.agent/decisions/.gitkeep`: persistent record directories.
- Create `scripts/agent_status.py`: validate task metadata, lifecycle location, ownership, and write-scope collisions.
- Create `scripts/project_snapshot.py`: generate a concise Markdown restoration snapshot from control-plane files and Git state.
- Create `scripts/quality_gate.py`: run named verification profiles with deterministic exit codes.
- Create `tests/test_agent_status.py`: unit tests for valid tasks, missing metadata, filename/state mismatch, and overlapping ownership.
- Create `tests/test_project_snapshot.py`: snapshot-content tests using a temporary repository fixture.
- Create `tests/test_quality_gate.py`: profile selection and subprocess result aggregation tests.
- Create `.github/workflows/quality.yml`: execute control-plane tests and the baseline test suite on pushes and pull requests.
- Modify `.gitignore`: ignore `.superpowers/`, generated snapshots, Python caches, local secrets, and build output without hiding source data required by the app.

### Task 1: Capture and Protect the Existing Baseline

**Files:**
- Create: `.agent/STATE.md`
- Create: `.agent/handoffs/2026-07-12-initial-baseline.md`
- Modify: `.gitignore`

- [x] **Step 1: Record the exact working-tree inventory**

Run:

```powershell
git status --short --branch
git diff --stat
git diff --name-status
python -m unittest discover -s tests -v
```

Expected: Git reports the current modified/untracked files; the test command produces a reproducible pass/fail baseline without changing files.

- [x] **Step 2: Write the initial state document**

Create `.agent/STATE.md` with these exact sections:

```markdown
# Current Project State

## Active Milestone
M0 - Stabilize the current working baseline.

## Working Tree
The repository contains a large uncommitted training-review redesign. Treat every pre-existing modification as user-owned and do not overwrite, discard, move, or reformat it without explicit review.

## Current Priorities
1. Verify the existing uncommitted behavior and tests.
2. Establish the repository-native Agent control plane.
3. Create repeatable quality commands.
4. Delegate only low-risk tasks after the baseline is understood.

## Blockers
- The current uncommitted changes do not yet have a recorded acceptance result.
- Frontend and backend hotspots are too large for safe overlapping ownership.

## Next Action
Run the M0 baseline review, then activate the Agent collaboration foundation plan.
```

- [x] **Step 3: Write the initial handoff**

Create `.agent/handoffs/2026-07-12-initial-baseline.md` containing the command outputs from Step 1, the list of pre-existing modified files, any failing tests, and the rule that these changes are not owned by the control-plane implementation.

- [x] **Step 4: Extend ignore rules narrowly**

Append only missing entries to `.gitignore`:

```gitignore
.superpowers/
.agent/generated/
__pycache__/
*.py[cod]
.env
.env.*
!.env.example
build/
dist/
```

Verify with:

```powershell
git check-ignore -v .superpowers/brainstorm/example
```

Expected: the path is ignored by the new `.superpowers/` rule.

- [x] **Step 5: Review the baseline diff**

Run:

```powershell
git diff -- .gitignore .agent/STATE.md .agent/handoffs/2026-07-12-initial-baseline.md
```

Expected: only control-plane baseline documentation and narrow ignore additions appear. Do not commit unless the project owner explicitly requests a commit.

### Task 2: Create the Collaboration Constitution and Project Memory

**Files:**
- Create: `AGENTS.md`
- Create: `.agent/PROJECT.md`
- Create: `.agent/ROADMAP.md`
- Create: `.agent/ARCHITECTURE.md`
- Create: `.agent/DOMAIN_RULES.md`
- Create: `.agent/QUALITY_GATES.md`
- Create: `.agent/WORKFLOW.md`

- [x] **Step 1: Create `AGENTS.md` with enforceable repository rules**

The file must define:

```markdown
# AI Collaboration Rules

## Source of Truth
`.agent/STATE.md`, `.agent/ROADMAP.md`, active task packets, Git state, and automated test output are authoritative. Chat history is supplementary only.

## Roles
Codex owns architecture, planning, complex implementation, integration, review, global state, and final acceptance. External workers execute only ready task packets.

## File Ownership
Every active task declares an exclusive write scope. Files outside that scope are read-only. Two active tasks may not own the same file.

## Safety
Never discard pre-existing changes. Never delete user data. Never change persistence formats, public APIs, trading invariants, release state, or secrets handling without explicit approval and a migration/rollback plan.

## Completion
Workers submit to review. Only Codex may mark a task done after checking the diff and required quality gates.

## Required Handoff
Every substantial work session updates `.agent/STATE.md` and writes a handoff with completed work, commands run, results, risks, and next action.
```

- [x] **Step 2: Write project direction documents**

Populate `.agent/PROJECT.md` and `.agent/ROADMAP.md` from the approved design. `PROJECT.md` must identify A-share replay/training users, core product value, supported workflows, success metrics, and non-goals. `ROADMAP.md` must define M0 through M4 with observable completion criteria.

- [x] **Step 3: Write the current architecture map**

Document these verified entry points and hotspots in `.agent/ARCHITECTURE.md`:

```text
Desktop entry: webview_app/main_pywebview.py
HTTP application: backend/app_enhanced.py
Trading domain: backend/trade_simulator_enhanced.py, backend/market_rules.py, backend/order_manager.py
Market data: backend/data_manager.py, backend/kline_processor_enhanced.py
Persistence/history: backend/user_manager_enhanced.py, backend/history_manager.py
Frontend: frontend/index_enhanced.html, frontend/js/main_enhanced.js, frontend/css/style_enhanced.css
Existing regression tests: tests/test_trading_rules.py
```

Include the current main data flow: user action -> frontend fetch -> Flask route -> manager/simulator -> JSON response -> chart/account/report render.

- [x] **Step 4: Write protected domain rules**

`.agent/DOMAIN_RULES.md` must state that changes to T+1 sellability, limit-up/down handling, commission/minimum commission, stamp tax, pending-order execution, adjustment behavior, account totals, session identity, and report calculations require focused regression tests.

- [x] **Step 5: Write workflow and quality policy**

`.agent/WORKFLOW.md` must define `backlog -> ready -> active -> review -> done`, blocked/return paths, exclusive write ownership, worker result requirements, and Codex acceptance. `.agent/QUALITY_GATES.md` must define `control-plane`, `backend`, `frontend`, `app-smoke`, and `full` profiles with exact commands available in this repository.

- [x] **Step 6: Verify document consistency**

Run:

```powershell
rg -n "PLACEHOLDER_MARKER" AGENTS.md .agent
rg -n "backlog|ready|active|review|done|blocked" .agent/WORKFLOW.md
rg -n "T\+1|涨跌停|佣金|印花税|复权|session" .agent/DOMAIN_RULES.md
```

Expected: placeholder search returns no matches; lifecycle and domain searches return the intended policy lines.

### Task 3: Create Task and Handoff Templates

**Files:**
- Create: `.agent/templates/task.md`
- Create: `.agent/templates/result.md`
- Create: `.agent/templates/handoff.md`
- Create: `.agent/templates/adr.md`
- Create: `.agent/tasks/backlog/.gitkeep`
- Create: `.agent/tasks/ready/.gitkeep`
- Create: `.agent/tasks/active/.gitkeep`
- Create: `.agent/tasks/review/.gitkeep`
- Create: `.agent/tasks/done/.gitkeep`
- Create: `.agent/tasks/blocked/.gitkeep`
- Create: `.agent/decisions/.gitkeep`

- [x] **Step 1: Create persistent state directories**

Create each directory listed above and add an empty `.gitkeep` where necessary.

- [x] **Step 2: Create the task template**

Use parseable front matter:

```markdown
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
Explain why this task matters.

## Goal
State one observable outcome.

## Non-Goals
- State what must not change.

## Constraints
- Preserve pre-existing user changes.

## Acceptance Criteria
- [x] State verifiable behavior.

## Required Commands
```powershell
python -m unittest discover -s tests -v
```

## Result Contract
Move the task to `review` and attach a result report using `.agent/templates/result.md`.
```

- [x] **Step 3: Create result, handoff, and ADR templates**

`result.md` must require changed files, summary, commands actually run, outputs, risks, and unresolved items. `handoff.md` must require session goal, completed tasks, active/blocked work, Git status, verification, decisions, and next action. `adr.md` must require context, decision, alternatives, consequences, rollback, and status.

- [x] **Step 4: Validate templates manually**

Run:

```powershell
rg -n "write_scope|Acceptance Criteria|Required Commands|Result Contract" .agent/templates/task.md
rg -n "Commands Run|Risks|Unresolved" .agent/templates/result.md
rg -n "Git Status|Next Action" .agent/templates/handoff.md
```

Expected: each required contract field is present.

### Task 4: Implement Task-State Validation with TDD

**Files:**
- Create: `scripts/agent_status.py`
- Create: `tests/test_agent_status.py`

- [x] **Step 1: Write failing validator tests**

Create tests using `tempfile.TemporaryDirectory` for:

```python
class AgentStatusTests(unittest.TestCase):
    def test_valid_ready_task_has_no_errors(self): ...
    def test_missing_owner_is_reported_for_active_task(self): ...
    def test_directory_must_match_declared_status(self): ...
    def test_overlapping_active_write_scope_is_reported(self): ...
    def test_missing_acceptance_criteria_is_reported(self): ...
```

Each fixture writes Markdown with the exact front matter from `.agent/templates/task.md`.

- [x] **Step 2: Run tests and verify failure**

Run:

```powershell
python -m unittest tests.test_agent_status -v
```

Expected: FAIL because `scripts.agent_status` does not exist.

- [x] **Step 3: Implement the minimum parser and validator**

`scripts/agent_status.py` must use only the standard library and expose:

```python
def parse_front_matter(path: Path) -> dict[str, object]: ...
def validate_task(path: Path, task_root: Path) -> list[str]: ...
def find_write_scope_conflicts(task_root: Path) -> list[str]: ...
def validate_repository(task_root: Path) -> list[str]: ...
def main(argv: list[str] | None = None) -> int: ...
```

The parser only needs scalars and bracket/list values used by the template. Validation must require `id`, `title`, `status`, `priority`, `owner`, `write_scope`, `quality_profiles`, an `Acceptance Criteria` section, directory/status agreement, assigned owner for `active` and `review`, and unique active write paths.

- [x] **Step 4: Run focused tests**

Run:

```powershell
python -m unittest tests.test_agent_status -v
```

Expected: all `AgentStatusTests` pass.

- [x] **Step 5: Run validator against the repository**

Run:

```powershell
python scripts/agent_status.py .agent/tasks
```

Expected: exit code 0 and `Agent task validation passed.` because only `.gitkeep` files exist.

### Task 5: Implement Project Snapshot Generation with TDD

**Files:**
- Create: `scripts/project_snapshot.py`
- Create: `tests/test_project_snapshot.py`
- Create: `.agent/generated/.gitkeep`

- [x] **Step 1: Write failing snapshot tests**

Test that the generated Markdown contains the active milestone, next action, task counts by status, recent handoff name, and Git summary. Patch `subprocess.run` so tests do not depend on the real repository.

- [x] **Step 2: Run tests and verify failure**

Run:

```powershell
python -m unittest tests.test_project_snapshot -v
```

Expected: FAIL because `scripts.project_snapshot` does not exist.

- [x] **Step 3: Implement snapshot generation**

Expose:

```python
def read_text(path: Path) -> str: ...
def task_counts(task_root: Path) -> dict[str, int]: ...
def latest_handoff(handoff_root: Path) -> Path | None: ...
def git_summary(repo_root: Path) -> str: ...
def build_snapshot(repo_root: Path) -> str: ...
def main(argv: list[str] | None = None) -> int: ...
```

The CLI writes `.agent/generated/project-snapshot.md` by default and prints its path.

- [x] **Step 4: Run focused tests**

Run:

```powershell
python -m unittest tests.test_project_snapshot -v
```

Expected: all snapshot tests pass.

- [x] **Step 5: Generate a real snapshot**

Run:

```powershell
python scripts/project_snapshot.py
```

Expected: `.agent/generated/project-snapshot.md` includes M0, current blockers, zero task counts, latest handoff, and the current dirty Git summary.

### Task 6: Implement Unified Quality Profiles with TDD

**Files:**
- Create: `scripts/quality_gate.py`
- Create: `tests/test_quality_gate.py`

- [x] **Step 1: Write failing quality-gate tests**

Test these behaviors:

```python
class QualityGateTests(unittest.TestCase):
    def test_unknown_profile_returns_usage_error(self): ...
    def test_control_plane_profile_runs_expected_commands(self): ...
    def test_first_failure_produces_nonzero_exit(self): ...
    def test_all_successful_commands_return_zero(self): ...
```

Patch the command runner so unit tests are deterministic.

- [x] **Step 2: Run tests and verify failure**

Run:

```powershell
python -m unittest tests.test_quality_gate -v
```

Expected: FAIL because `scripts.quality_gate` does not exist.

- [x] **Step 3: Implement profile execution**

Define profiles as command arrays, not shell strings:

```python
PROFILES = {
    "control-plane": [
        [sys.executable, "-m", "unittest", "tests.test_agent_status", "tests.test_project_snapshot", "tests.test_quality_gate", "-v"],
        [sys.executable, "scripts/agent_status.py", ".agent/tasks"],
    ],
    "backend": [[sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]],
    "full": [],
}
```

Build `full` by concatenating de-duplicated commands from the available profiles. Print each command, duration, and pass/fail result. Stop on the first failure unless `--keep-going` is supplied.

- [x] **Step 4: Run focused and repository tests**

Run:

```powershell
python -m unittest tests.test_quality_gate -v
python scripts/quality_gate.py control-plane
python scripts/quality_gate.py backend
```

Expected: focused tests pass; control-plane passes; backend matches the recorded M0 baseline or exposes a pre-existing failure without hiding it.

### Task 7: Add CI and Prove One Task Lifecycle

**Files:**
- Create: `.github/workflows/quality.yml`
- Create: `.agent/tasks/done/TASK-001-agent-control-plane-bootstrap.md`
- Create: `.agent/handoffs/2026-07-12-agent-control-plane-bootstrap.md`
- Modify: `.agent/STATE.md`

- [x] **Step 1: Add the GitHub Actions workflow**

Create a Windows workflow because the packaged application targets Windows:

```yaml
name: quality

on:
  push:
  pull_request:

jobs:
  control-plane:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
      - run: pip install -r requirements.txt
      - run: python scripts/quality_gate.py control-plane
      - run: python scripts/quality_gate.py backend
```

- [x] **Step 2: Create the completed bootstrap task record**

Move a real `TASK-001` packet through the lifecycle in repository history, ending at `.agent/tasks/done/TASK-001-agent-control-plane-bootstrap.md`. Record Codex as owner, the exact write scope from this plan, acceptance criteria, commands run, and final result.

- [x] **Step 3: Run the complete local gate**

Run:

```powershell
python scripts/quality_gate.py full
```

Expected: all newly created control-plane tests pass. Any pre-existing backend failure is documented explicitly in the handoff and keeps the task out of `done` until resolved or reclassified by the project owner.

- [x] **Step 4: Update state and write handoff**

Set `.agent/STATE.md` to M1 complete only if Task 3 through Task 6 pass. The handoff must include changed files, exact commands, results, remaining dirty-tree risk, CI status, and recommended next plan.

- [x] **Step 5: Review final scope**

Run:

```powershell
git status --short
git diff --check
git diff --stat
python scripts/agent_status.py .agent/tasks
```

Expected: no whitespace errors; validator passes; only planned control-plane, tests, documentation, workflow, and ignore changes are new. Do not commit unless the project owner explicitly requests a commit.

## Plan Self-Review

- Spec coverage: M0 baseline protection, repository control plane, roles, task lifecycle, templates, quality evidence, CI, handoff, and success criteria are covered.
- Deferred by design: large business-module refactors, broader API tests, frontend module conversion, packaging stabilization, and release automation each require separate plans after M0/M1.
- Placeholder scan: no unresolved placeholder markers, deferred implementation instructions, or undefined cross-task references remain.
- Type consistency: script entry points and function names are consistent across tests, implementation steps, and commands.
- Commit steps are intentionally omitted because repository commits require explicit project-owner authorization.


