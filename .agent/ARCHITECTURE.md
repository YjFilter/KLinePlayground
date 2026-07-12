# Current Architecture

## Runtime Entry Points
- Desktop host: `webview_app/main_pywebview.py`
- HTTP application: `backend/app_enhanced.py`
- Browser shell: `frontend/index_enhanced.html`
- Frontend controller: `frontend/js/main_enhanced.js`

## Module Map
- Trading domain: `backend/trade_simulator_enhanced.py`, `backend/market_rules.py`, `backend/order_manager.py`
- Market data: `backend/data_manager.py`, `backend/kline_processor_enhanced.py`
- Users and settings: `backend/user_manager_enhanced.py`
- Session history and reports: `backend/history_manager.py`
- Styling: `frontend/css/style_enhanced.css`
- Regression baseline: `tests/test_trading_rules.py`
- Standalone AI tester: `ai_assistant_tester.py`

## Main Data Flow
1. The user acts in the frontend.
2. `main_enhanced.js` sends an HTTP request to a Flask route.
3. The route coordinates a manager, K-line processor, order manager, or simulator.
4. The backend returns JSON containing market, account, order, trade, or report state.
5. The frontend updates charts, controls, account panels, history, or reports.

## Persistence
- User-specific settings, statistics, and history are managed under `backend/user_manager_enhanced.py` and `backend/history_manager.py`.
- Offline market data is managed by `backend/data_manager.py` and stored under project data directories.
- Persistence-format changes require migration and rollback design.

## Hotspots
- `frontend/js/main_enhanced.js` is approximately 3,500 lines and combines state, API, charts, training, trading, reports, users, and settings.
- `backend/app_enhanced.py` is approximately 1,000 lines and combines routes, coordination, response mapping, and active-session state.
- `backend/data_manager.py` is approximately 1,200 lines and combines data-source, synchronization, caching, and storage concerns.

## Parallel Work Constraint
Until stable boundaries exist, tasks that touch the same hotspot must be serialized. Prefer extracting and testing one boundary at a time over assigning overlapping edits.
