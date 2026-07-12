# Intraday Data Foundation Start Handoff

## Session Goal
Implement Phase 1 of the approved multi-timeframe replay design on an isolated feature branch.

## Git Status
- Branch: `feature/intraday-data-foundation`.
- Worktree: `C:\Users\1111\.config\superpowers\worktrees\KLinePlayground\intraday-data-foundation`.
- Baseline commit: `aa45f69`.
- Baseline working tree was clean.

## Verification
- `python scripts/quality_gate.py full`: exit 0, 20 tests passed, frontend syntax passed.

## Live Evidence Before Implementation
- BaoStock 0.9.3 returned 9,688 rows and 1,211 trading days for each of `600000`, `600519`, and `300750` over five years.
- Each observed complete trading day contained eight 30-minute rows.

## Scope
Only intraday data source, validation, cache, service, tests, quality profile, and control-plane state may change.

## Next Action
Write the failing model and BaoStock source tests.
