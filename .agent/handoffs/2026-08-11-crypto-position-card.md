# Session Handoff

## Session Goal
币圈"当前持仓"区升级为 AiCoin 风格持仓卡片：开单后展示方向/杠杆/盈亏/持仓量/开仓均价/保证金/标记价/保证金率/预估强平价/止盈止损，并提供止盈止损、平仓、市价全平三个操作按钮（用户对照 AiCoin 持仓截图提出）。纯前端，未动后端。

## Completed Tasks
- 持仓卡片 `renderCryptoPositionCard`（渲染进 `#current-positions`）：
  - 头部：交易对（如 ETHUSDT）+ 方向徽标（多绿/空红）+ 逐仓 + 杠杆(100x) + 浮动盈亏（金额 + 保证金收益率%，绿涨红跌）。
  - 指标网格（2 列）：持仓量(币)、开仓均价、保证金(USDT)、标记价格、保证金率、预估强平价、止盈(绿)、止损(红)。
  - 止盈/止损值从挂单中的保护单（`parent_order_id` + `protection_type`）读取。
  - 空仓回落"暂无持仓"。
- 卡片操作按钮：
  - 止盈止损 → `focusCryptoTpSlPanel`：开启下单区止盈止损开关并滚动定位聚焦。
  - 平仓 → 切换订单表单为市价平仓方向。
  - 市价全平 → `cryptoMarketCloseAll`：直接 POST `/trade`（action=close, order_type=market, margin=0, leverage=持仓杠杆），复用成交回报/状态提示链路。后端平仓忽略保证金、数量取全部持仓，已核对。
- 清理：加密模式隐藏下单面板内冗余的 `.crypto-position-grid`（卡片已覆盖）；`updatePositionInfo`（A 股持仓渲染器）在加密模式提前返回，避免覆盖卡片。

## Active Tasks
- 无（等待用户确认卡片观感与操作）。

## Blocked Work
- 无。

## Git Status
- 分支 `master`，未创建提交。
- 本会话改动：`frontend/js/main_enhanced.js`、`frontend/css/style_enhanced.css`。
- 既有未提交改动保持原样；`.runtime/`、离线数据、凭证、`.gitignore`、启动脚本未触碰。

## Verification
| Command | Exit Code | Result |
| --- | ---: | --- |
| `node --check frontend/js/main_enhanced.js` | 0 | JS_OK |
| `.venv\Scripts\python.exe -m pytest -q` | 0 | 723 passed, 71 subtests passed in 49.01s |
| `git diff --check` | 0 | DIFF_OK |
| 浏览器 DOM 模拟 | 0 | 多头 payload → 卡片头部 `ETHUSDT 多 逐仓 100x +0.8627 (+22.70%)`，八项指标全对（持仓量 0.203/开仓均价 1,870/保证金 3.8/标记 1,874.25/保证金率 439.25%/强平 1,723.32/止盈 1,888/止损 1,860），操作钮[止盈止损,平仓,市价全平]；空仓 payload → 暂无持仓；控制台无报错 |

## Decisions
- 卡片渲染进既有 `#current-positions` 容器（"当前持仓"区块），不动 HTML 结构，A 股模式行为不变。
- 止盈止损按钮不直接改已开持仓的保护单（后端仅支持随开仓单挂 TP/SL），改为开启并聚焦下单区止盈止损面板；已有保护单在卡片与挂单列表中可见、可撤。
- 市价全平直接走 `/trade`，margin=0（后端平仓忽略保证金），leverage 传持仓杠杆避免触发"持仓中不能改杠杆"。

## Risks
- 卡片在每次账户回报时重建（含按钮监听重绑），频率与 A 股持仓列表一致，性能可接受。
- 浏览器截图仍超时未能自动出图，卡片实际观感需肉眼确认。

## Next Action
开一局币圈训练开多/开空一笔，确认"当前持仓"卡片数据齐全、颜色正确，点三个操作钮验证：止盈止损聚焦下单区、平仓切市价平仓、市价全平一键成交；平仓后卡片回落"暂无持仓"。
