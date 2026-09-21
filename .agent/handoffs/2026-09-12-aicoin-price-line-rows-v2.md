# Session Handoff

## Session Goal
用户否掉了上一版价格线浮层（"做太差了，哪些字体等"），并给出**详细规格**要求做成 AICoin 一样：

> 1. 挂单时候：线上有**止盈 / 止损的药丸**，点击即可拖动止盈止损线（附拖动后效果图）
> 2. 订单进入后：止盈止损已挂上，都有✕可快速取消，止盈止损可拖动
> 3. 订单进去**没有设置**止盈止损的，可以像 1 那样拖动设置
> 4. 如果是**平仓订单线**，其实就是止盈止损线一样的逻辑即可

并额外抱怨两点：字体/样式差；**"我刚刚试的是市价进的为什么会有止盈止损线？我都没设置"**。

## 用户否掉 v1 的真正原因（本轮已修）
1. **线上有全宽彩色文字带**：v1 把 `title` 写在价格线上（Lightweight Charts 会把它渲染成横贯整条线的文字），视觉上非常脏。
   → AICoin 的线上**没有任何文字**，信息全在右侧浮层 + 轴上的价格框里。
2. **凭空出现的虚线**：v1 在"持仓没设止盈止损"时**自动画了两条 ±2% 的虚线占位线**，
   用户看到就以为"我没设置怎么有线" → 这正是他的疑问来源。
   → 改为**不画任何线**，只在浮层上给「止盈 / 止损」徽标作为入口。

## 本轮改动（`frontend/js/main_enhanced.js` + `style_enhanced.css`）

### A. 线上不再写字
- 持仓线 / 止盈止损线 / 挂单线 / 兜底保护线的 `title` 一律置空；
- **拖动过程中也不再往线上写文字**（原来会临时写"修改挂单: xxx"），提示只留在跟随光标的气泡里。
- 修 bug：删掉 `const title = ...` 后漏改了一处 `title: title` → `ReferenceError: title is not defined`
  （**由既有测试抓到**，见下）。

### B. AICoin 风格分段浮层（`buildChartTradeLinePill` 重写）
按角色渲染不同分段，统一贴价格轴左侧：

| 行类型 | 内容 |
| --- | --- |
| 持仓 | `多 0.003 @ 61,704.8 │ +0 USDT (+0.02%) │ [止盈][止损]`（徽标仅在缺该保护时出现） |
| 止盈/止损 | `止盈 │ 市价 │ 预估收益 +25.96 (+140.25%) │ 距当前价 +14.02% │ 0.003 │ ✕` |
| 挂单 | `[止盈][止损] │ 限价卖出平仓 │ 0.003 │ ✕` |

- 配色对齐 AICoin：**止盈绿 `#0ecb81`、止损琥珀 `#f0a020`**（v1 的止损是红色，AICoin 是橙色）。
- 字体/排版重写：11px、`tabular-nums`、分段之间 1px 分隔线、20px 行高、✕ 占满行高。

### C. 「止盈 / 止损」徽标 = 拖动放置的入口（对应规格 1 与 3）
- `buildProtectivePlacementChip()` 渲染虚线小徽标；
- `beginProtectiveLinePlacement()`：按下徽标 → 按默认 ±2% 建一条临时线并**立即接管拖动**
  （复用既有挂单拖拽状态机）→ 松手由 `finishDrag` 走"创建保护单"分支；
- `finishDrag` 中把占位线分支**提到"未移动就回滚"判断之前**：
  点一下 = 按默认 ±2% 放置，拖动了 = 按拖到的价位；失败则 `removeProtectivePlaceholderLine()` 清理干净。

### D. 平仓单按"相对成本价的位置"判定角色（对应规格 4）
引擎里手工挂的平仓单没有 `protection_type`，因此不会被识别成止盈/止损。
现在按它落在成本价的哪一侧判定：**多头在上=止盈、在下=止损（空头相反）**，
于是"平仓订单线"自动获得与止盈止损线完全一致的浮层/配色/拖动/✕ 行为。

### E. 修一个盈亏符号 bug
`computeProtectiveLinePnl()` 原来用 **`item.side`** 判断多空，但平仓单的 side 是 `sell/buy`，
导致**多头的止盈被算成亏损**（实测显示 `预估收益 -25.96 (-140.25%)`）。
改为读取 `currentTraining.position.side`（真正的持仓方向）后显示 `+25.96 (+140.25%)` ✓。

## Verification

| Command | Result |
| --- | --- |
| `node --check frontend/js/main_enhanced.js` | Pass |
| `pytest -q` | **838 passed, 89 subtests passed** |

### 浏览器实测（CDP + 真实 Chromium，BTCUSDT 61704.8，市价开多 0.003）
| 检查 | 结果 |
| --- | --- |
| 开仓后（未设保护） | 只有 1 条持仓线，`lineTitles: [""]`（**线上无文字**）；浮层 `多 0.003 @ 61,704.8 +0 USDT (+0.02%) 止盈 止损`（300px）；`chips: 2`；**`hasDashedPlaceholder: false`**（不再有凭空虚线） |
| 按住「止盈」徽标拖动 | 按下即建临时线并进入拖动态；松手发出 `POST /trade {"action":"close","order_type":"limit","limit_price":70358.85}` → **200**，`pendingCount: 1` |
| 生成的行 | `trade-line-pill is-tp` → `止盈 市价 预估收益 +25.96 (+140.25%) 距当前价 +14.02% 0.003 ✕` |
| 持仓行联动 | 止盈挂上后，持仓行的「止盈」徽标自动消失，只剩「止损」 |

## 两个测试基建坑（值得记住）

1. **`node -e <整段脚本>` 会撞 Windows 命令行长度上限（约 32KB）**，报
   `FileNotFoundError: [WinError 206] 文件名或扩展名太长`。本仓库多个前端测试用这种方式执行抽取的代码，
   代码一变长就会炸。已把 `test_chart_workspace_frontend.py::ChartTradePriceLinesTests` 改为
   **写临时文件后 `node <file>`**（并补 `import tempfile`）。
   → 如果以后还有其他测试报 WinError 206，同样处理。
2. 该测试的断言写死了旧设计（线上含"止盈/止损/限价"文字、止损红色 `#f6465d`），
   已按新设计更新为：**线上 title 必须为空** + 止损颜色 `#f0a020`。

> 这两个坑都由既有测试主动暴露（其中 `title is not defined` 是**真 bug**，浏览器里也会抛），
> 说明这套 `pytest` 门禁确实在兜底，改前端后必跑。

## 未完成 / 待确认

### 1. 规格 1 的"挂单时"设置止盈止损 → 需要后端小改动
现状：引擎 `modify_order_price()` 只支持改价；挂单的 `tp_price / sl_price` **只能在提交时**给定，
成交时由引擎据此生成保护子单（`futures_orders.py:554-590`）。
所以**未成交的挂单**目前无法事后补挂止盈止损 —— 前端徽标点了也会被后端忽略。

需要的改动（小）：
- `modify_order_price()` 增加可选 `tp_price / sl_price` 参数并写入目标挂单；
- 路由 `PUT /orders/{id}` 透传这两个字段；
- 补校验（多头 tp 需高于、sl 需低于委托价等，可复用 `_validate_pending_direction` 思路）。
**待用户确认后实施**（属于后端语义改动，想先对齐）。

### 2. 持仓行的「平 / 市 / 反」快捷按钮（AICoin 图里有）
用户描述里提到但未明确要求；且「反」（反向开仓）是新下单流程。可后续再加。

## 涉及文件
- 修改：`frontend/js/main_enhanced.js`、`frontend/css/style_enhanced.css`、
  `tests/test_chart_workspace_frontend.py`

## 备注
- 未执行 git 提交与推送；未清理既有未提交改动；未触碰 `.runtime/`、`.gitignore`、`启动项目.bat`。
- **后端仍由 Agent 于本会话临时启动**（`flask --app backend.app_enhanced run --port 8000`）：
  若 8000 打不开，重跑 `启动项目.bat` 即可（8000 被占用时 bat 会自动改用 5000）。
