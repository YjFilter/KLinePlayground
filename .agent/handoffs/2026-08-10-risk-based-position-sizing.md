# Session Handoff

## Session Goal
币圈下单区新增"以损定仓"功能：输入开仓价、止损价、最大亏损额，自动反推下单数量并填入保证金（含杠杆因素）；同时把杠杆上限从 20x 提升到 100x。前后端 + 测试。

## Completed Tasks
- 新模块 `frontend/js/risk_calc.js`（UMD，可被 node require，仿 indicator_math.js）：`RiskCalc.computeRiskPosition({entryPrice, stopPrice, maxLoss, leverage, action})`。
  - 核心公式：数量 = 最大亏损 ÷ |开仓价 − 止损价|（杠杆不影响数量，只影响保证金）；名义价值 = 数量 × 开仓价；保证金 = 名义价值 ÷ 杠杆。
  - 返回 quantity/notional/margin/stopRate/marginLossRate/directionOk；非法输入返回 `missing-inputs`，开仓价=止损价返回 `stop-too-close`，杠杆钳制 1–100。
- 下单区 UI：止盈止损区块下方新增"以损定仓"折叠区（复用 crypto-tpsl 样式类）——开仓价、止损价、最大亏损三个输入 + "计算并填入"按钮 + 实时结果行。
  - 开仓价留空→用当前计算价格；止损价留空→同步上方止盈止损的止损价；方向取当前订单方向（平仓视为开多）。
  - 输入即实时刷新结果行；点"计算并填入"把所需保证金写入 `#crypto-margin`（并清除仓位比例按钮选中态），止损价自动回填到止盈止损区并开启该开关；方向不符给出警示文案。
  - 结果行展示：数量、名义价值、保证金(Lx)、止损幅度%、触发止损时保证金亏损率%。
  - 杠杆切换、止损价联动变化时自动重算。
- 杠杆上限 1→100x：后端 `futures_simulator._validate_leverage` 改 `1 <= leverage <= 100`（含报错文案）；前端两处下拉（训练设置 `#crypto-leverage`、下单 `#crypto-order-leverage`）增加 50x/100x 选项。
- 新测试 `tests/test_crypto_risk_calc.py`：node 运行时校验公式四象限/方向警示/非法输入/杠杆钳制 + 静态契约（脚本加载顺序、DOM id、100x 选项、后端范围）。

## Active Tasks
- 无（等待用户实际下单体验确认）。

## Blocked Work
- 无。注：验证期间发现 8000 端口 Flask 服务已停，已按启动脚本同款命令后台重新拉起（PID 32712）。

## Git Status
- 分支 `master`，未创建提交。
- 本会话改动：`frontend/js/risk_calc.js`（新增）、`frontend/js/main_enhanced.js`、`frontend/index_enhanced.html`、`frontend/css/style_enhanced.css`、`backend/crypto/futures_simulator.py`、`tests/test_crypto_futures_simulator.py`（21→101 边界、20→100 有效值，业务规则变更）、`tests/test_crypto_risk_calc.py`（新增）。
- 既有未提交改动保持原样；`.runtime/`、离线数据、凭证、`.gitignore`、启动脚本未触碰。

## Verification
| Command | Exit Code | Result |
| --- | ---: | --- |
| `node --check`（main_enhanced.js、risk_calc.js） | 0 | JS_OK |
| `.venv\Scripts\python.exe -m compileall backend/crypto/futures_simulator.py` | 0 | PY_COMPILE_OK |
| `.venv\Scripts\python.exe -m pytest -q` | 0 | 723 passed, 71 subtests passed in 33.28s（新增 6 个测试全过） |
| `git diff --check` | 0 | DIFF_OK |
| 浏览器 DOM 校验 | 0 | RiskCalc 已加载；7 个 riskcalc 元素齐全；两处杠杆下拉均含 1–100 选项；模拟完整流程：2500/2450/100/10x → 数量 2、名义 5000、保证金 500 自动填入、止损价同步止盈止损区；控制台无报错；localStorage 未污染 |

## Decisions
- 下单表单是"保证金驱动"（后端按 margin×leverage 折算数量），因此以损定仓反推出数量后换算成保证金回填，预览数量≈目标数量（手续费会使实际成交略小，属预期）。
- 杠杆计入"所需保证金"与"保证金亏损率"展示，满足用户"加上杠杆因素"的诉求；数量本身按风险额与止损距离决定（标准以损定仓语义）。
- 独立 UMD 模块便于 node 单测，延续 indicator_math.js 架构。

## Risks
- 市价单实际成交价与输入的开仓价可能有偏差，止损触发时的真实亏损会与估算略有出入（UI 文案用"≈"提示）。
- 100x 高杠杆下保证金亏损率展示可能超过 100%（止损幅度×杠杆），仅提示用，不阻断。

## Next Action
开一局币圈训练硬刷新，勾选"以损定仓"，输入开仓价/止损价/最大亏损点"计算并填入"，确认保证金自动填入、预览数量≈目标、提交订单流程正常；试试 50x/100x 杠杆开仓。
