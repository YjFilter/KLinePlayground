# Initial Baseline Handoff

## Session Goal
Record and protect the pre-existing working tree before adding the Agent collaboration control plane.

## Git Status
Branch: `master`, tracking `origin/master`.

Pre-existing modified files:
- `backend/app_enhanced.py`
- `backend/history_manager.py`
- `backend/kline_processor_enhanced.py`
- `backend/trade_simulator_enhanced.py`
- `backend/user_manager_enhanced.py`
- `frontend/css/style_enhanced.css`
- `frontend/index_enhanced.html`
- `frontend/js/main_enhanced.js`

Pre-existing untracked business and test files:
- `backend/market_rules.py`
- `backend/order_manager.py`
- `tests/test_trading_rules.py`
- Existing documents under `docs/`

The tracked business diff contains 2,036 insertions and 79 deletions across eight tracked files. These changes are user-owned and outside the write scope of the control-plane implementation.

## Verification
Command: `python -m unittest discover -s tests -v`

Result: 8 tests passed in 30.262 seconds, 0 failures.

Covered baseline behaviors include market limit rules, pending orders, sell blocking, training-bar limits, and report session identity.

## Risks
- The current business redesign has not yet received a complete product-level acceptance review.
- Large frontend and Flask files create overlapping-write risk for parallel agents.
- Line-ending warnings indicate Git may convert LF to CRLF when tracked business files are touched.

## Decisions
- Implement the control plane in new documentation, scripts, tests, and CI files only.
- Do not modify, discard, stage, commit, or reformat the pre-existing business changes.
- Do not delegate overlapping business-code tasks until module boundaries are improved.

## Next Action
Create the repository collaboration constitution, memory documents, task templates, and validation scripts.
