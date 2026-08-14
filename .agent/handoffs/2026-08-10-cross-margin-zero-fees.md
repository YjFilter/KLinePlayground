# Session Handoff

## Session Goal
修复用户反馈"币圈一下单就自动平仓"：引擎强平按逐仓（Isolated）语义计算，账户剩余余额不参与风险支撑，100x 杠杆下 1% 波动即被强平。用户要求改为全仓（Cross）语义——只要账户还有钱就不该强平；同时把全部手续费默认归零，用户以后自行设置。

## Completed Tasks
- **全仓强平语义**（`backend/crypto/futures_engine.py`、`futures_simulator.py`）：
  - `liquidation_price()`：公式中的 `position.isolated_margin` 全部替换为 `simulator.account.balance`（多空两方向）。
  - `margin_ratio()`：改为 `维持保证金 ÷ 账户总权益`（`equity = balance + unrealized_pnl`），不再用单仓 `isolated_equity`。
  - 效果：余额充足时强平价远离现价甚至为 0（价格触及不到，不会强平）；保证金率反映整个账户的真实风险占比。
- **手续费默认归零**：
  - `backend/crypto/futures_orders.py`：`maker_fee_rate`/`taker_fee_rate` 默认 `"0.0002"/"0.0005"` → `"0"/"0"`。
  - `backend/crypto/futures_engine.py`：`liquidation_fee_rate` 默认 `"0.005"` → `"0"`。
  - `backend/app_enhanced.py`：`DEFAULT_CRYPTO_MAKER_FEE_RATE`/`DEFAULT_CRYPTO_TAKER_FEE_RATE` → `"0"/"0"`。
  - `frontend/index_enhanced.html`：手续费表单默认值 `0.02/0.05` → `0`。
  - 上限 `MAX_CRYPTO_FEE_RATE = 0.01` 与"应用费率"设置入口保留，用户可自行设置。
- **测试同步更新**：
  - `tests/test_crypto_futures_engine.py`：强平价测试 `make_engine()` → `make_engine(balance="100")`（全仓语义下 balance=100=保证金时与原逐仓断言值一致）；liquidation priority 测试同改为 balance=100。
  - `tests/test_crypto_futures_api.py`：默认费率断言 `0.0002/0.0005` → `0.0`；`max_market_margin`/`max_limit_margin` 断言 `<10000` → `<=10000`（fee=0 时 max=available）；unaffordable 用例 margin `10000` → `10001`（fee=0 时 10000 恰好可用，超过才拒绝）。
  - `tests/test_crypto_futures_simulator.py`：`margin_ratio("110")` 断言 `1.8333` → `0.2619`（27.5/10500）。

## Active Tasks
- 无。

## Blocked Work
- 无。

## Git Status
- 分支 `main`，未创建提交（既有未提交改动保持原样）。
- 本会话改动：`backend/crypto/futures_engine.py`、`backend/crypto/futures_simulator.py`、`backend/crypto/futures_orders.py`、`backend/app_enhanced.py`、`frontend/index_enhanced.html`、`tests/test_crypto_futures_api.py`、`tests/test_crypto_futures_engine.py`、`tests/test_crypto_futures_simulator.py`。
- `.runtime/`、离线数据、凭证、`.gitignore`、启动脚本未触碰。

## Verification
| Command | Exit Code | Result |
| --- | ---: | --- |
| `node --check frontend/js/main_enhanced.js` | 0 | JS_OK |
| `.venv\Scripts\python.exe -m compileall -q backend` | 0 | PY_COMPILE_OK |
| `.venv\Scripts\python.exe -m pytest -q` | 0 | 723 passed, 71 subtests passed |
| `git diff --check` | 0 | DIFF_OK |

## Decisions
- 全仓强平价 = 用账户余额反推：多仓 `(q*entry - balance)/(q*(1-reserve))`、空仓 `(balance + q*entry)/(q*(1+reserve))`（reserve = 维持保证金率 + 强平手续费率）。与原逐仓公式仅差一个分子量（balance vs isolated_margin），改动最小、语义正确。
- 手续费全零是"教学/复盘工具"定位下的合理默认：训练者不想让费用干扰 K 线复盘结论；设置入口保留，费用仍完整进入下单流程与报表。
- 测试用 balance=100 等价构造全仓场景，保留原断言数值，避免重写强平公式的数学期望。

## Risks
- 全仓语义下，若用户反复加仓且浮亏逼近账户总余额，仍会强平（这是正确行为）；UI 强平价/保证金率展示与逐仓时期数值不同，属预期变化。
- 既有持久化的训练状态（`futures_executor` 快照）若含旧 fee/杠杆配置，重载后按新默认显示；无迁移逻辑（训练会话为临时状态，非长期数据）。
- 前端"预计手续费"与 max_margin 预览在 fee=0 时全部为 0/可用余额，功能正常。

## Next Action
硬刷新 `http://127.0.0.1:8000/` 开一局币圈训练（可用 100x 杠杆）确认：下单后不再"秒强平"（余额充足时强平价应远离现价）、保证金率按账户总权益计算、手续费显示 0 且可自行设置修改。
