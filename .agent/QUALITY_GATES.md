# Quality Gates

## Profiles

### control-plane
Run:
```powershell
python -m unittest tests.test_agent_status tests.test_project_snapshot tests.test_quality_gate -v
python scripts/agent_status.py .agent/tasks
```
Required for changes under `.agent/`, `scripts/`, collaboration tests, or CI workflow files.

### backend
Run:
```powershell
python -m unittest discover -s tests -v
```
Required for Python backend, trading rules, persistence, reports, data, and API changes.

### frontend
Run:
```powershell
node --check frontend/js/main_enhanced.js
```
Required for frontend JavaScript changes. Future module files must be added to this profile.

### app-smoke
Run the documented desktop or Flask startup long enough to confirm that the application loads without an immediate exception. Record the exact command and observed endpoint or window.

### full
Runs control-plane, backend, frontend, and applicable startup or packaging checks.

## Conditional Rules
- Documentation-only tasks run control-plane validation and content-specific checks.
- Core trading changes always run focused domain tests plus backend.
- Frontend behavior changes run frontend plus relevant API/backend tests.
- Packaging or release changes run full plus the packaging command.

## Evidence Contract
Record commands actually executed, exit codes, test counts, failures, warnings, skipped checks, and reasons. A suggested command is not evidence.

## Failure Policy
A mandatory gate failure keeps the task in review or returns it to ready. A pre-existing failure must be reproduced, documented, and approved before it can be excluded.

### intraday
Run:
```powershell
python -m unittest discover -s tests -p test_intraday_source.py -v
python -m unittest discover -s tests -p test_intraday_validator.py -v
python -m unittest discover -s tests -p test_intraday_cache.py -v
python -m unittest discover -s tests -p test_intraday_service.py -v
```
Required for BaoStock source, intraday validation, cache, synchronization, or live verification changes. Live network verification is separate and optional for CI:

```powershell
python scripts/verify_baostock_30m.py --years 5 600000 600519 300750
```


## Phase 2
```powershell
python scripts/quality_gate.py phase2
```
Runs aggregation, replay-clock, and no-future-leakage tests. It is included in `full`.


## Phase 3
```powershell
python scripts/quality_gate.py phase3
```
Runs previous-close, sequential advance, trade metadata, integration adapter, and large-step equivalence tests. It is included in `full`.
