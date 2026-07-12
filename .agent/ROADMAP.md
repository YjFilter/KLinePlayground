# Product and Engineering Roadmap

## M0 - Stable Baseline
Completion criteria:
- Existing dirty working tree is inventoried and protected.
- Existing tests have a recorded baseline result.
- Dependencies, startup, tests, and packaging commands are documented.
- Temporary and sensitive local artifacts are ignored.

## M1 - Agent Control Plane
Completion criteria:
- Repository collaboration constitution and project memory exist.
- Task lifecycle and templates are usable.
- Task metadata and write-scope conflicts are automatically validated.
- A generated project snapshot restores current context.
- One real task completes the ready-to-review-to-done lifecycle.

## M2 - Quality and CI
Completion criteria:
- Core trading rules and critical Flask APIs have regression coverage.
- Frontend syntax and startup smoke checks are automated.
- GitHub Actions runs required quality profiles.
- Packaging, release notes, rollback, and versioning are documented and repeatable.

## M3 - Modular Architecture
Completion criteria:
- Frontend state, API, charts, training, trading, reports, users, and settings have explicit module boundaries.
- Flask routes are separated into blueprints and application services.
- Market data sources, caching, synchronization, and storage are separated.
- Public request and response contracts are documented and tested.

## M4 - Continuous Product Progress
Completion criteria:
- Saying “continue” reliably restores state and selects the next valuable work.
- Codex delegates low-risk ready tasks and retains complex integration ownership.
- Every session closes with updated state, evidence, risks, and next action.
- Product milestones advance without relying on chat history.
